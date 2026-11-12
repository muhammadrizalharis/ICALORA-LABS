"""Latih model AI Detector: manusia (korpus) vs AI (MULTI-MODEL, hemat disk).

Dua mode:
  * generate  : hasilkan sampel AI memakai model tertentu sampai cache mencapai
                --target-ai, lalu KELUAR (tanpa melatih). Dipakai driver yang
                memuat model SATU PER SATU (pull -> generate -> rm) agar disk
                tidak membengkak.
  * finalize  : latih model logistik dari cache, validasi held-out, simpan
                model.json.
  * full      : (default) perilaku lama — isi human, generate, lalu latih.

Contoh:
    python -m app.services.ai_detector.train generate \
        --local-models qwen2.5:7b-instruct --shared-models gemma4:latest,gpt-oss:latest \
        --target-ai 2600 --per-class 5000
    python -m app.services.ai_detector.train finalize --test-frac 0.2

Sampel manusia = teks nyata korpus akses-terbuka. Sampel AI dibuat BANYAK model
(beragam arsitektur) dalam beragam gaya & temperatur, supaya detektor general.
Fitur di-cache ke JSONL bertahap -> aman terhadap gangguan (resume).
"""

from __future__ import annotations

import argparse
import json
import os
import random
import re
import threading
import time
from pathlib import Path

import httpx
from sqlalchemy import text

from app.core.clients import engine
from app.ingest.common import decompress_text
from app.services.ai_detector import _statistical_signals
from app.services.ai_detector.embed import EMB_DIM, EMB_ENDPOINT, embed_text
from app.services.ai_detector.model import (
    EMB_MODEL_PATH,
    FEATURES,
    LogisticModel,
    feature_vector,
    save,
    train,
)

_WORD_MIN, _WORD_MAX = 80, 400
_CACHE_PATH = Path(__file__).resolve().parent / "train_features.jsonl"
_EMB_CACHE_PATH = Path(__file__).resolve().parent / "train_emb.jsonl"
_NUM_CTX = 4096
_NUM_PREDICT = int(os.environ.get("ICALORA_NUM_PREDICT", "300"))

_LOCAL = os.environ.get("ICALORA_AI_ENDPOINT", "http://127.0.0.1:11500")
_SHARED = os.environ.get("ICALORA_SHARED_ENDPOINT", "http://127.0.0.1:11434")

_AI_STYLES = [
    "Tulis satu abstrak akademik (120-200 kata) gaya formal baku.",
    "Tulis satu paragraf tinjauan pustaka (literature review) akademik (120-200 kata).",
    "Tulis satu paragraf metodologi penelitian (120-200 kata) gaya ilmiah.",
    "Tulis satu paragraf hasil dan pembahasan (120-200 kata) gaya ilmiah.",
    "Tulis satu paragraf pendahuluan artikel jurnal (120-200 kata).",
    "Write one academic abstract (120-200 words) in formal scholarly style.",
    "Write one literature review paragraph (120-200 words) in academic English.",
    "Write one methodology paragraph (120-200 words) for a research paper.",
]
_AI_TEMPS = [0.5, 0.7, 0.85, 1.0]

# Gaya akademik Indonesia saja — dipakai mode `--lang id` untuk menambah
# keseimbangan bahasa (kelas AI punya prosa Indonesia; kelas manusia dulu nyaris
# tak punya sehingga teks akademik Indonesia manusia salah dituduh AI).
_AI_STYLES_ID = [
    "Tulis satu abstrak akademik (120-200 kata) gaya formal baku bahasa Indonesia.",
    "Tulis satu paragraf tinjauan pustaka akademik (120-200 kata) bahasa Indonesia.",
    "Tulis satu paragraf metodologi penelitian (120-200 kata) gaya ilmiah bahasa Indonesia.",
    "Tulis satu paragraf hasil dan pembahasan (120-200 kata) gaya ilmiah bahasa Indonesia.",
    "Tulis satu paragraf pendahuluan artikel jurnal (120-200 kata) bahasa Indonesia.",
    "Tulis satu paragraf simpulan penelitian (120-200 kata) gaya ilmiah bahasa Indonesia.",
    "Tulis satu paragraf kerangka teori (120-200 kata) gaya akademik bahasa Indonesia.",
]

# Deteksi teks berbahasa Indonesia via densitas kata fungsi khas ID.
_ID_RE = re.compile(
    r"\b(yang|dengan|dari|untuk|pada|adalah|dan|ini|penelitian|dalam|tidak|dapat|"
    r"akan|telah|secara|terhadap|berdasarkan|menggunakan|hasil|metode|tujuan|atau|"
    r"juga|sebagai|oleh|karena|serta|antara|lebih|sangat|bahwa|sehingga|merupakan|"
    r"adanya|dilakukan|diperoleh|penelitian|pembelajaran|data)\b",
    re.I,
)


def _looks_indonesian(text: str, min_hits: int = 6) -> bool:
    return len(_ID_RE.findall(text[:1000])) >= min_hits


def _human_samples(n: int, exclude_ids: set[int]) -> list[tuple[int, str, str]]:
    with engine.connect() as conn:
        max_id = conn.execute(text("SELECT max(id) FROM corpus_documents")).scalar() or 0
        out: list[tuple[int, str, str]] = []
        seen: set[int] = set(exclude_ids)
        attempts = 0
        while len(out) < n and attempts < n * 30:
            attempts += 1
            start = random.randint(1, max(1, max_id))
            row = conn.execute(
                text(
                    """
                    SELECT id, title, text_zstd, word_count
                    FROM corpus_documents
                    WHERE id >= :start AND text_zstd IS NOT NULL
                      AND word_count BETWEEN :lo AND :hi
                    ORDER BY id LIMIT 1
                    """
                ),
                {"start": start, "lo": _WORD_MIN, "hi": _WORD_MAX},
            ).first()
            if not row or row.id in seen:
                continue
            seen.add(row.id)
            try:
                body = decompress_text(row.text_zstd)
            except Exception:  # noqa: BLE001
                continue
            if body and len(body.split()) >= 60:
                out.append((row.id, row.title or "", body))
        return out


def _indonesian_human_samples(need: int, exclude_ids: set[int], scan_cap: int = 2_000_000):
    """Yield (id, title, body) dokumen korpus berbahasa Indonesia (manusia).

    Korpus didominasi Inggris (~0.14% Indonesia), jadi kita pindai blok id acak
    dan saring dengan heuristik kata fungsi Indonesia sampai `need` terpenuhi
    atau `scan_cap` dokumen terlampaui.
    """
    with engine.connect() as conn:
        max_id = conn.execute(text("SELECT max(id) FROM corpus_documents")).scalar() or 0
        seen: set[int] = set(exclude_ids)
        found = scanned = 0
        while found < need and scanned < scan_cap:
            start = random.randint(1, max(1, max_id - 200))
            rows = conn.execute(
                text(
                    """
                    SELECT id, title, text_zstd
                    FROM corpus_documents
                    WHERE id >= :start AND text_zstd IS NOT NULL
                      AND word_count BETWEEN :lo AND :hi
                    ORDER BY id LIMIT 60
                    """
                ),
                {"start": start, "lo": _WORD_MIN, "hi": _WORD_MAX},
            ).fetchall()
            for row in rows:
                scanned += 1
                if row.id in seen:
                    continue
                try:
                    body = decompress_text(row.text_zstd)
                except Exception:  # noqa: BLE001
                    continue
                if not body or len(body.split()) < 60:
                    continue
                if not _looks_indonesian(body):
                    continue
                seen.add(row.id)
                found += 1
                yield row.id, row.title or "", body
                if found >= need:
                    break
            if scanned % 50_000 < 60:
                print(f"[id] dipindai={scanned} ditemukan={found}/{need}", flush=True)


def _harvest_id_humans(target: int) -> int:
    """Tambah sampel manusia Indonesia ke KEDUA cache (feat + feat/emb)."""
    _Xe, ye, used_emb = _load_emb_cache()
    _Xf, yf, used_feat = _load_cache()
    used = used_emb | used_feat
    print(f"[id] memanen {target} sampel manusia Indonesia…", flush=True)
    fe = _EMB_CACHE_PATH.open("a", encoding="utf-8")
    ff = _CACHE_PATH.open("a", encoding="utf-8")
    n = 0
    try:
        with httpx.Client() as client:
            for doc_id, _title, body in _indonesian_human_samples(target, used):
                emb = embed_text(body, client, EMB_ENDPOINT)
                if emb is None:
                    continue
                feat = feature_vector(_statistical_signals(body))
                fe.write(json.dumps({"label": 0, "feat": feat, "emb": emb, "src_id": doc_id, "lang": "id"}) + "\n")
                ff.write(json.dumps({"label": 0, "feat": feat, "src_id": doc_id, "lang": "id"}) + "\n")
                fe.flush()
                ff.flush()
                n += 1
                if n % 100 == 0:
                    print(f"[id]   manusia-id: {n}/{target}", flush=True)
    finally:
        fe.close()
        ff.close()
    print(f"[id] selesai; manusia Indonesia ditambah={n}", flush=True)
    return n


def _generate_id(client: httpx.Client, endpoint: str, model: str, title: str, rng: random.Random) -> str | None:
    """Seperti _generate tetapi khusus prompt akademik Indonesia."""
    topic = title.strip() or "sebuah topik penelitian umum"
    style = rng.choice(_AI_STYLES_ID)
    temp = rng.choice(_AI_TEMPS)
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": f"{style} Jangan menyebut bahwa teks ini dibuat AI. Keluarkan HANYA teksnya dalam bahasa Indonesia."},
            {"role": "user", "content": f"Topik/judul: {topic}"},
        ],
        "stream": False,
        "keep_alive": "10m",
        "think": False,
        "options": {"temperature": temp, "num_predict": _NUM_PREDICT, "num_ctx": _NUM_CTX},
    }
    try:
        resp = client.post(f"{endpoint}/api/chat", json=payload, timeout=240)
        resp.raise_for_status()
        out = (resp.json()["message"]["content"] or "").strip()
        if len(out.split()) < 60 or not _looks_indonesian(out, min_hits=5):
            return None
        return out
    except Exception:  # noqa: BLE001
        return None


def _gen_id_ai(target: int, lanes: list[tuple[str, str]], titles: list[str],
               max_seconds: int, concurrency: int) -> int:
    """Generate sampel AI Indonesia ke KEDUA cache (feat + feat/emb)."""
    _Xe, ye, _ = _load_emb_cache()
    start_ai = sum(1 for v in ye if v == 1)
    fe = _EMB_CACHE_PATH.open("a", encoding="utf-8")
    ff = _CACHE_PATH.open("a", encoding="utf-8")
    lock = threading.Lock()
    state = {"n": 0, "ti": 0}
    deadline = time.time() + max_seconds

    def next_title() -> str | None:
        with lock:
            if state["ti"] >= len(titles):
                return None
            t = titles[state["ti"]]
            state["ti"] += 1
            return t

    def worker(wid: int) -> None:
        rng = random.Random(30_000 + wid + int(time.time()) % 1000)
        fails = 0
        with httpx.Client() as client:
            while True:
                with lock:
                    if state["n"] >= target:
                        return
                if time.time() > deadline:
                    return
                title = next_title()
                if title is None:
                    return
                endpoint, model = rng.choice(lanes)
                txt = _generate_id(client, endpoint, model, title, rng)
                if not txt:
                    fails += 1
                    if fails >= 40:
                        print(f"[id-ai]   worker {wid} berhenti (40 gagal)", flush=True)
                        return
                    continue
                emb = embed_text(txt, client, EMB_ENDPOINT)
                if emb is None:
                    fails += 1
                    continue
                fails = 0
                feat = feature_vector(_statistical_signals(txt))
                with lock:
                    if state["n"] >= target:
                        return
                    fe.write(json.dumps({"label": 1, "feat": feat, "emb": emb, "src_id": None, "gen": model, "lang": "id"}) + "\n")
                    ff.write(json.dumps({"label": 1, "feat": feat, "src_id": None, "gen": model, "lang": "id"}) + "\n")
                    fe.flush()
                    ff.flush()
                    state["n"] += 1
                    c = state["n"]
                if c % 25 == 0:
                    print(f"[id-ai]   AI-id: {c}/{target}", flush=True)

    threads = [threading.Thread(target=worker, args=(w,), daemon=True) for w in range(max(1, concurrency))]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    fe.close()
    ff.close()
    print(f"[id-ai] selesai; AI Indonesia ditambah={state['n']} (AI emb-cache awal={start_ai})", flush=True)
    return state["n"]


def cmd_harvest_id(args) -> None:
    random.seed(args.seed)
    _harvest_id_humans(args.target)


def cmd_gen_id(args) -> None:
    random.seed(args.seed)
    lanes = _lanes_from_args(args.local_models, args.shared_models)
    if not lanes:
        print("[id-ai] tidak ada model; batal.", flush=True)
        return
    print(f"[id-ai] lanes={[m for _e, m in lanes]} target={args.target}", flush=True)
    # Judul topik dari dokumen Indonesia agar tema relevan.
    titles = [t for _id, t, _b in _indonesian_human_samples(args.target + 400, set())]
    random.shuffle(titles)
    _gen_id_ai(args.target, lanes, titles, args.max_seconds, args.concurrency)


def _generate(client: httpx.Client, endpoint: str, model: str, title: str, rng: random.Random) -> str | None:
    topic = title.strip() or "sebuah topik penelitian umum"
    style = rng.choice(_AI_STYLES)
    temp = rng.choice(_AI_TEMPS)
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": f"{style} Jangan menyebut bahwa teks ini dibuat AI. Keluarkan HANYA teksnya."},
            {"role": "user", "content": f"Topik/judul: {topic}"},
        ],
        "stream": False,
        "keep_alive": "10m",
        "think": False,
        "options": {"temperature": temp, "num_predict": _NUM_PREDICT, "num_ctx": _NUM_CTX},
    }
    try:
        resp = client.post(f"{endpoint}/api/chat", json=payload, timeout=240)
        resp.raise_for_status()
        out = (resp.json()["message"]["content"] or "").strip()
        return out if len(out.split()) >= 60 else None
    except Exception:  # noqa: BLE001
        return None


def _load_cache() -> tuple[list[list[float]], list[int], set[int]]:
    X: list[list[float]] = []
    y: list[int] = []
    used_ids: set[int] = set()
    if not _CACHE_PATH.exists():
        return X, y, used_ids
    for line in _CACHE_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
            X.append([float(v) for v in rec["feat"]])
            y.append(int(rec["label"]))
            if rec.get("src_id") is not None:
                used_ids.add(int(rec["src_id"]))
        except (json.JSONDecodeError, KeyError, ValueError):
            continue
    return X, y, used_ids


def _count_ai() -> int:
    """Hitung sampel AI (label 1) yang sudah ada di cache tanpa memuat semua fitur."""
    if not _CACHE_PATH.exists():
        return 0
    n = 0
    for line in _CACHE_PATH.read_text(encoding="utf-8").splitlines():
        if '"label": 1' in line:
            n += 1
    return n


def _fill_humans(target: int, fh) -> int:
    """Pastikan cache punya `target` sampel manusia. Kembalikan jumlah akhir."""
    _X, y, used_ids = _load_cache()
    n_h = sum(1 for v in y if v == 0)
    if n_h >= target:
        return n_h
    need = target - n_h
    print(f"[gen] mengambil {need} sampel manusia…", flush=True)
    for doc_id, _title, body in _human_samples(need, used_ids):
        feat = feature_vector(_statistical_signals(body))
        fh.write(json.dumps({"label": 0, "feat": feat, "src_id": doc_id}) + "\n")
        fh.flush()
        n_h += 1
    print(f"[gen] sampel manusia kini={n_h}", flush=True)
    return n_h


def _generate_ai(lanes: list[tuple[str, str]], target_ai: int, titles: list[str],
                 fh, lock: threading.Lock, max_seconds: int, concurrency: int) -> int:
    """Pool `concurrency` worker; tiap worker memilih lane (endpoint,model) ACAK
    per permintaan. Membatasi beban server (sopan) sekaligus menjaga diversitas
    model. Berhenti saat cache AI >= target_ai, judul habis, atau lewat waktu.
    Kembalikan jumlah AI akhir."""
    state = {"ai": _count_ai(), "ti": 0}
    deadline = time.time() + max_seconds

    def next_title() -> str | None:
        with lock:
            if state["ti"] >= len(titles):
                return None
            t = titles[state["ti"]]
            state["ti"] += 1
            return t

    def worker(wid: int) -> None:
        rng = random.Random(10_000 + wid + int(time.time()) % 1000)
        fails = 0
        with httpx.Client() as client:
            while True:
                with lock:
                    if state["ai"] >= target_ai:
                        return
                if time.time() > deadline:
                    return
                title = next_title()
                if title is None:
                    return
                endpoint, model = rng.choice(lanes)
                txt = _generate(client, endpoint, model, title, rng)
                if not txt:
                    fails += 1
                    if fails >= 30:
                        print(f"[gen]   worker {wid} berhenti (30 gagal beruntun)", flush=True)
                        return
                    continue
                fails = 0
                feat = feature_vector(_statistical_signals(txt))
                with lock:
                    if state["ai"] >= target_ai:
                        return
                    fh.write(json.dumps({"label": 1, "feat": feat, "src_id": None, "gen": model}) + "\n")
                    fh.flush()
                    state["ai"] += 1
                    c = state["ai"]
                if c % 25 == 0:
                    print(f"[gen]   sampel AI: {c}/{target_ai}", flush=True)

    threads = []
    for wid in range(max(1, concurrency)):
        t = threading.Thread(target=worker, args=(wid,), daemon=True)
        t.start()
        threads.append(t)
    for t in threads:
        t.join()
    return state["ai"]


def _evaluate(model, X: list[list[float]], y: list[int]) -> dict:
    tp = tn = fp = fn = 0
    for xi, yi in zip(X, y):
        pred = 1 if model.predict_proba(xi) >= 0.5 else 0
        if yi == 1 and pred == 1:
            tp += 1
        elif yi == 0 and pred == 0:
            tn += 1
        elif yi == 0 and pred == 1:
            fp += 1
        else:
            fn += 1
    n = tp + tn + fp + fn
    humans = tn + fp
    ai = tp + fn
    return {
        "n": n,
        "accuracy": round((tp + tn) / n, 3) if n else None,
        "false_positive_rate": round(fp / humans, 3) if humans else None,
        "false_negative_rate": round(fn / ai, 3) if ai else None,
        "precision": round(tp / (tp + fp), 3) if (tp + fp) else None,
        "recall": round(tp / (tp + fn), 3) if (tp + fn) else None,
        "confusion": {"tp": tp, "tn": tn, "fp": fp, "fn": fn},
    }


def _parse_models(s: str) -> list[str]:
    return [m.strip() for m in s.split(",") if m.strip()]


def _lanes_from_args(local: str, shared: str) -> list[tuple[str, str]]:
    lanes: list[tuple[str, str]] = []
    for m in _parse_models(local):
        lanes.append((_LOCAL, m))
    for m in _parse_models(shared):
        lanes.append((_SHARED, m))
    return lanes


def cmd_generate(args) -> None:
    random.seed(args.seed)
    fh = _CACHE_PATH.open("a", encoding="utf-8")
    try:
        _fill_humans(args.per_class, fh)
        lanes = _lanes_from_args(args.local_models, args.shared_models)
        if not lanes:
            print("[gen] tidak ada model; lewati generate.", flush=True)
            return
        print(f"[gen] lanes={[m for _e,m in lanes]} target_ai={args.target_ai}", flush=True)
        topics = [t for _id, t, _b in _human_samples(args.target_ai + 2000, set())]
        lock = threading.Lock()
        final = _generate_ai(lanes, args.target_ai, topics, fh, lock, args.max_seconds, args.concurrency)
        print(f"[gen] selesai. AI di cache={final}", flush=True)
    finally:
        fh.close()


def cmd_finalize(args) -> None:
    rng = random.Random(args.seed)
    X, y, _ = _load_cache()
    pos = sum(y)
    print(f"[fin] total {len(X)} sampel (AI={pos}, manusia={len(y) - pos})", flush=True)
    if pos < 10 or (len(y) - pos) < 10:
        raise SystemExit("[fin] sampel terlalu sedikit untuk melatih + validasi.")

    idx0 = [i for i, v in enumerate(y) if v == 0]
    idx1 = [i for i, v in enumerate(y) if v == 1]
    rng.shuffle(idx0)
    rng.shuffle(idx1)
    n_test0 = max(1, int(len(idx0) * args.test_frac))
    n_test1 = max(1, int(len(idx1) * args.test_frac))
    test_idx = set(idx0[:n_test0] + idx1[:n_test1])
    Xtr = [X[i] for i in range(len(X)) if i not in test_idx]
    ytr = [y[i] for i in range(len(y)) if i not in test_idx]
    Xte = [X[i] for i in sorted(test_idx)]
    yte = [y[i] for i in sorted(test_idx)]
    print(f"[fin] split: latih={len(Xtr)} held-out={len(Xte)}; melatih…", flush=True)

    model = train(Xtr, ytr)
    metrics = _evaluate(model, Xte, yte)
    model.meta["validation"] = metrics
    model.meta["n_human"] = len(y) - pos
    model.meta["n_ai"] = pos
    save(model)

    print("[fin] === VALIDASI (held-out) ===", flush=True)
    print(f"  akurasi            : {metrics['accuracy']}")
    print(f"  false-positive rate: {metrics['false_positive_rate']}  (manusia dituduh AI)")
    print(f"  false-negative rate: {metrics['false_negative_rate']}  (AI lolos)")
    print(f"  precision / recall : {metrics['precision']} / {metrics['recall']}")
    print(f"  confusion          : {metrics['confusion']}")
    print(f"[fin] selesai. akurasi latih={model.meta.get('train_accuracy')} n={model.meta.get('n')}", flush=True)


# ─────────────────────────── EMBEDDING (1024-dim bge-m3) ───────────────────────────

def _emb_count_ai() -> int:
    if not _EMB_CACHE_PATH.exists():
        return 0
    n = 0
    for line in _EMB_CACHE_PATH.read_text(encoding="utf-8").splitlines():
        if '"label": 1' in line:
            n += 1
    return n


def _load_emb_cache() -> tuple[list[list[float]], list[int], set[int]]:
    """Muat cache embedding; tiap X = feat(6) + emb(1024) = 1030 dim."""
    X: list[list[float]] = []
    y: list[int] = []
    used_ids: set[int] = set()
    if not _EMB_CACHE_PATH.exists():
        return X, y, used_ids
    for line in _EMB_CACHE_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
            feat = [float(v) for v in rec["feat"]]
            emb = [float(v) for v in rec["emb"]]
            if len(emb) != EMB_DIM:
                continue
            X.append(feat + emb)
            y.append(int(rec["label"]))
            if rec.get("src_id") is not None:
                used_ids.add(int(rec["src_id"]))
        except (json.JSONDecodeError, KeyError, ValueError):
            continue
    return X, y, used_ids


def _fill_humans_emb(target: int, fh, client: httpx.Client) -> int:
    """Pastikan cache embedding punya `target` sampel manusia (feat + emb)."""
    _X, y, used_ids = _load_emb_cache()
    n_h = sum(1 for v in y if v == 0)
    if n_h >= target:
        return n_h
    need = target - n_h
    print(f"[emb] mengambil+meng-embed {need} sampel manusia…", flush=True)
    for doc_id, _title, body in _human_samples(need, used_ids):
        emb = embed_text(body, client, EMB_ENDPOINT)
        if emb is None:
            continue
        feat = feature_vector(_statistical_signals(body))
        fh.write(json.dumps({"label": 0, "feat": feat, "emb": emb, "src_id": doc_id}) + "\n")
        fh.flush()
        n_h += 1
        if n_h % 100 == 0:
            print(f"[emb]   manusia: {n_h}/{target}", flush=True)
    print(f"[emb] sampel manusia kini={n_h}", flush=True)
    return n_h


def _generate_ai_emb(lanes: list[tuple[str, str]], target_ai: int, titles: list[str],
                     fh, lock: threading.Lock, max_seconds: int, concurrency: int) -> int:
    """Seperti _generate_ai tetapi tiap teks AI juga di-embed (feat + emb)."""
    state = {"ai": _emb_count_ai(), "ti": 0}
    deadline = time.time() + max_seconds

    def next_title() -> str | None:
        with lock:
            if state["ti"] >= len(titles):
                return None
            t = titles[state["ti"]]
            state["ti"] += 1
            return t

    def worker(wid: int) -> None:
        rng = random.Random(20_000 + wid + int(time.time()) % 1000)
        fails = 0
        with httpx.Client() as client:
            while True:
                with lock:
                    if state["ai"] >= target_ai:
                        return
                if time.time() > deadline:
                    return
                title = next_title()
                if title is None:
                    return
                endpoint, model = rng.choice(lanes)
                txt = _generate(client, endpoint, model, title, rng)
                if not txt:
                    fails += 1
                    if fails >= 30:
                        print(f"[emb]   worker {wid} berhenti (30 gagal beruntun)", flush=True)
                        return
                    continue
                emb = embed_text(txt, client, EMB_ENDPOINT)
                if emb is None:
                    fails += 1
                    continue
                fails = 0
                feat = feature_vector(_statistical_signals(txt))
                with lock:
                    if state["ai"] >= target_ai:
                        return
                    fh.write(json.dumps({"label": 1, "feat": feat, "emb": emb, "src_id": None, "gen": model}) + "\n")
                    fh.flush()
                    state["ai"] += 1
                    c = state["ai"]
                if c % 25 == 0:
                    print(f"[emb]   sampel AI: {c}/{target_ai}", flush=True)

    threads = []
    for wid in range(max(1, concurrency)):
        t = threading.Thread(target=worker, args=(wid,), daemon=True)
        t.start()
        threads.append(t)
    for t in threads:
        t.join()
    return state["ai"]


def cmd_build_emb(args) -> None:
    random.seed(args.seed)
    fh = _EMB_CACHE_PATH.open("a", encoding="utf-8")
    try:
        with httpx.Client() as client:
            _fill_humans_emb(args.per_class, fh, client)
        lanes = _lanes_from_args(args.local_models, args.shared_models)
        if not lanes:
            print("[emb] tidak ada model; lewati generate.", flush=True)
            return
        print(f"[emb] lanes={[m for _e, m in lanes]} target_ai={args.target_ai}", flush=True)
        topics = [t for _id, t, _b in _human_samples(args.target_ai + 2000, set())]
        lock = threading.Lock()
        final = _generate_ai_emb(lanes, args.target_ai, topics, fh, lock, args.max_seconds, args.concurrency)
        print(f"[emb] selesai. AI di cache={final}", flush=True)
    finally:
        fh.close()


def cmd_finalize_emb(args) -> None:
    rng = random.Random(args.seed)
    X, y, _ = _load_emb_cache()
    pos = sum(y)
    print(f"[fin-emb] total {len(X)} sampel (AI={pos}, manusia={len(y) - pos}), dim={len(X[0]) if X else 0}", flush=True)
    if pos < 10 or (len(y) - pos) < 10:
        raise SystemExit("[fin-emb] sampel terlalu sedikit untuk melatih + validasi.")

    idx0 = [i for i, v in enumerate(y) if v == 0]
    idx1 = [i for i, v in enumerate(y) if v == 1]
    rng.shuffle(idx0)
    rng.shuffle(idx1)
    n_test0 = max(1, int(len(idx0) * args.test_frac))
    n_test1 = max(1, int(len(idx1) * args.test_frac))
    test_idx = set(idx0[:n_test0] + idx1[:n_test1])
    Xtr = [X[i] for i in range(len(X)) if i not in test_idx]
    ytr = [y[i] for i in range(len(y)) if i not in test_idx]
    Xte = [X[i] for i in sorted(test_idx)]
    yte = [y[i] for i in sorted(test_idx)]
    print(f"[fin-emb] split: latih={len(Xtr)} held-out={len(Xte)}; melatih (1030-dim, L2 kuat)…", flush=True)

    names = list(FEATURES) + [f"emb_{i}" for i in range(EMB_DIM)]
    model = train(Xtr, ytr, epochs=args.epochs, lr=args.lr, l2=args.l2, feature_names=names)
    metrics = _evaluate(model, Xte, yte)
    model.meta["validation"] = metrics
    model.meta["n_human"] = len(y) - pos
    model.meta["n_ai"] = pos
    model.meta["kind"] = "stat+emb"
    model.meta["emb_dim"] = EMB_DIM
    save(model, EMB_MODEL_PATH)

    print("[fin-emb] === VALIDASI (held-out) ===", flush=True)
    print(f"  akurasi            : {metrics['accuracy']}")
    print(f"  false-positive rate: {metrics['false_positive_rate']}  (manusia dituduh AI)")
    print(f"  false-negative rate: {metrics['false_negative_rate']}  (AI lolos)")
    print(f"  precision / recall : {metrics['precision']} / {metrics['recall']}")
    print(f"  confusion          : {metrics['confusion']}")
    print(f"[fin-emb] selesai → {EMB_MODEL_PATH.name}", flush=True)


# ─────────────────────────── STREAMING (tanpa cache disk) ───────────────────────────

def _unload_models(lanes: list[tuple[str, str]], timeout: int = 20) -> None:
    """Lepaskan model generator dari VRAM (keep_alive=0). bge-m3 TIDAK disentuh."""
    seen: set[tuple[str, str]] = set()
    with httpx.Client() as client:
        for endpoint, model in lanes:
            if (endpoint, model) in seen:
                continue
            seen.add((endpoint, model))
            try:
                client.post(
                    f"{endpoint}/api/chat",
                    json={
                        "model": model,
                        "messages": [{"role": "user", "content": "ok"}],
                        "stream": False, "keep_alive": 0, "think": False,
                        "options": {"num_predict": 1},
                    },
                    timeout=timeout,
                )
                print(f"[stream] VRAM dilepas: {model} @ {endpoint}", flush=True)
            except Exception:  # noqa: BLE001
                pass


def _collect_humans_stream(target_en: int, target_id: int, client: httpx.Client,
                           X: list[list[float]], y: list[int], used: set[int]) -> None:
    """Embed sampel manusia korpus (EN + ID) langsung ke RAM; tanpa tulis disk."""
    n = 0
    if target_en > 0:
        for doc_id, _title, body in _human_samples(target_en, used):
            emb = embed_text(body, client, EMB_ENDPOINT)
            if emb is None:
                continue
            used.add(doc_id)
            X.append(feature_vector(_statistical_signals(body)) + emb)
            y.append(0)
            n += 1
            if n % 100 == 0:
                print(f"[stream] manusia EN: {n}/{target_en}", flush=True)
        print(f"[stream] manusia EN terkumpul={n}", flush=True)
    if target_id > 0:
        m = 0
        for doc_id, _title, body in _indonesian_human_samples(target_id, used):
            emb = embed_text(body, client, EMB_ENDPOINT)
            if emb is None:
                continue
            used.add(doc_id)
            X.append(feature_vector(_statistical_signals(body)) + emb)
            y.append(0)
            m += 1
            if m % 50 == 0:
                print(f"[stream] manusia ID: {m}/{target_id}", flush=True)
        print(f"[stream] manusia ID terkumpul={m}", flush=True)


def _generate_ai_stream(lanes: list[tuple[str, str]], target_ai: int,
                        titles_en: list[str], titles_id: list[str], id_frac: float,
                        X: list[list[float]], y: list[int], lock: threading.Lock,
                        max_seconds: int, concurrency: int) -> int:
    """Generate teks AI (EN + ID) via model modern, embed, simpan ke RAM. Tanpa disk."""
    state = {"ai": 0, "ei": 0, "ii": 0}
    deadline = time.time() + max_seconds

    def next_task() -> tuple[str, str] | None:
        with lock:
            want_id = (random.random() < id_frac) and state["ii"] < len(titles_id)
            if want_id:
                t = titles_id[state["ii"]]
                state["ii"] += 1
                return ("id", t)
            if state["ei"] < len(titles_en):
                t = titles_en[state["ei"]]
                state["ei"] += 1
                return ("en", t)
            if state["ii"] < len(titles_id):
                t = titles_id[state["ii"]]
                state["ii"] += 1
                return ("id", t)
            return None

    def worker(wid: int) -> None:
        rng = random.Random(30_000 + wid + int(time.time()) % 1000)
        fails = 0
        with httpx.Client() as client:
            while True:
                with lock:
                    if state["ai"] >= target_ai:
                        return
                if time.time() > deadline:
                    return
                task = next_task()
                if task is None:
                    return
                kind, title = task
                endpoint, model = rng.choice(lanes)
                txt = (_generate_id(client, endpoint, model, title, rng) if kind == "id"
                       else _generate(client, endpoint, model, title, rng))
                if not txt:
                    fails += 1
                    if fails >= 30:
                        print(f"[stream]   worker {wid} berhenti (30 gagal beruntun)", flush=True)
                        return
                    continue
                emb = embed_text(txt, client, EMB_ENDPOINT)
                if emb is None:
                    fails += 1
                    continue
                fails = 0
                vec = feature_vector(_statistical_signals(txt)) + emb
                with lock:
                    if state["ai"] >= target_ai:
                        return
                    X.append(vec)
                    y.append(1)
                    state["ai"] += 1
                    c = state["ai"]
                if c % 25 == 0:
                    print(f"[stream]   sampel AI: {c}/{target_ai}", flush=True)

    threads = []
    for wid in range(max(1, concurrency)):
        t = threading.Thread(target=worker, args=(wid,), daemon=True)
        t.start()
        threads.append(t)
    for t in threads:
        t.join()
    return state["ai"]


def cmd_stream_emb(args) -> None:
    """Retrain model_emb TANPA menyimpan korpus: embed di RAM lalu latih.

    Opsional memuat cache lama (--seed-cache) agar keragaman generator lama tetap
    terjaga, lalu MENAMBAH positif AI dari model modern. Hanya model_emb.json (94K)
    yang ditulis; tidak ada file embedding besar yang dibuat."""
    random.seed(args.seed)
    rng = random.Random(args.seed)
    lanes = _lanes_from_args(args.local_models, args.shared_models)
    if not lanes:
        raise SystemExit("[stream] tidak ada model; beri --shared-models/--local-models")

    X: list[list[float]] = []
    y: list[int] = []
    used: set[int] = set()

    if args.seed_cache:
        Xc, yc, uc = _load_emb_cache()
        X.extend(Xc)
        y.extend(yc)
        used |= uc
        print(f"[stream] seed cache lama: {len(Xc)} sampel "
              f"(AI={sum(yc)}, manusia={len(yc) - sum(yc)})", flush=True)

    target_id_h = int(args.extra_humans * args.id_frac)
    target_en_h = args.extra_humans - target_id_h
    with httpx.Client() as client:
        if args.extra_humans > 0:
            print(f"[stream] kumpulkan manusia baru: EN={target_en_h} ID={target_id_h}", flush=True)
            _collect_humans_stream(target_en_h, target_id_h, client, X, y, used)

    titles_en = [t for _id, t, _b in _human_samples(args.target_ai + 1000, set())]
    titles_id: list[str] = []
    if args.id_frac > 0:
        n_id = int(args.target_ai * args.id_frac) + 200
        titles_id = [t for _id, t, _b in _indonesian_human_samples(n_id, set())]

    lock = threading.Lock()
    print(f"[stream] generate AI modern target={args.target_ai} lanes={[m for _e, m in lanes]} "
          f"id_frac={args.id_frac}", flush=True)
    final = _generate_ai_stream(lanes, args.target_ai, titles_en, titles_id, args.id_frac,
                                X, y, lock, args.max_seconds, args.concurrency)
    print(f"[stream] AI modern terkumpul={final}", flush=True)

    if not args.keep_vram:
        _unload_models(lanes)

    pos = sum(y)
    print(f"[stream] total {len(X)} sampel (AI={pos}, manusia={len(y) - pos}), "
          f"dim={len(X[0]) if X else 0}", flush=True)
    if pos < 10 or (len(y) - pos) < 10:
        raise SystemExit("[stream] sampel terlalu sedikit untuk melatih + validasi.")

    idx0 = [i for i, v in enumerate(y) if v == 0]
    idx1 = [i for i, v in enumerate(y) if v == 1]
    rng.shuffle(idx0)
    rng.shuffle(idx1)
    n_test0 = max(1, int(len(idx0) * args.test_frac))
    n_test1 = max(1, int(len(idx1) * args.test_frac))
    test_idx = set(idx0[:n_test0] + idx1[:n_test1])
    Xtr = [X[i] for i in range(len(X)) if i not in test_idx]
    ytr = [y[i] for i in range(len(y)) if i not in test_idx]
    Xte = [X[i] for i in sorted(test_idx)]
    yte = [y[i] for i in sorted(test_idx)]
    print(f"[stream] split: latih={len(Xtr)} held-out={len(Xte)}; melatih (1030-dim)…", flush=True)

    names = list(FEATURES) + [f"emb_{i}" for i in range(EMB_DIM)]
    model = train(Xtr, ytr, epochs=args.epochs, lr=args.lr, l2=args.l2, feature_names=names)
    metrics = _evaluate(model, Xte, yte)
    model.meta["validation"] = metrics
    model.meta["n_human"] = len(y) - pos
    model.meta["n_ai"] = pos
    model.meta["kind"] = "stat+emb"
    model.meta["emb_dim"] = EMB_DIM
    model.meta["source"] = "stream"
    model.meta["ai_modern"] = final
    model.meta["generators"] = sorted({m for _e, m in lanes})

    if args.dry_run:
        print("[stream] DRY-RUN: model TIDAK disimpan.", flush=True)
    else:
        if EMB_MODEL_PATH.exists():
            bak = EMB_MODEL_PATH.with_suffix(".json.bak")
            bak.write_text(EMB_MODEL_PATH.read_text(encoding="utf-8"), encoding="utf-8")
            print(f"[stream] cadangan model lama → {bak.name}", flush=True)
        save(model, EMB_MODEL_PATH)
        print(f"[stream] tersimpan → {EMB_MODEL_PATH.name}", flush=True)

    print("[stream] === VALIDASI (held-out) ===", flush=True)
    print(f"  akurasi            : {metrics['accuracy']}")
    print(f"  false-positive rate: {metrics['false_positive_rate']}  (manusia dituduh AI)")
    print(f"  false-negative rate: {metrics['false_negative_rate']}  (AI lolos)")
    print(f"  precision / recall : {metrics['precision']} / {metrics['recall']}")
    print(f"  confusion          : {metrics['confusion']}")


def main() -> None:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="mode")

    g = sub.add_parser("generate", help="hasilkan sampel AI lalu keluar")
    g.add_argument("--local-models", default="", help="daftar model instance user (koma)")
    g.add_argument("--shared-models", default="", help="daftar model Ollama bersama (koma)")
    g.add_argument("--target-ai", type=int, required=True, help="hentikan saat cache AI >= nilai ini")
    g.add_argument("--per-class", type=int, default=5000, help="jumlah sampel manusia yang diinginkan")
    g.add_argument("--max-seconds", type=int, default=7200)
    g.add_argument("--concurrency", type=int, default=3, help="jumlah worker paralel (beban ke server)")
    g.add_argument("--seed", type=int, default=42)

    f = sub.add_parser("finalize", help="latih dari cache + simpan model.json")
    f.add_argument("--test-frac", type=float, default=0.2)
    f.add_argument("--seed", type=int, default=42)

    be = sub.add_parser("build-emb", help="hasilkan sampel AI + embed (feat+emb) lalu keluar")
    be.add_argument("--local-models", default="", help="daftar model instance user (koma)")
    be.add_argument("--shared-models", default="", help="daftar model Ollama bersama (koma)")
    be.add_argument("--target-ai", type=int, required=True, help="hentikan saat cache-emb AI >= nilai ini")
    be.add_argument("--per-class", type=int, default=3000, help="jumlah sampel manusia yang diinginkan")
    be.add_argument("--max-seconds", type=int, default=7200)
    be.add_argument("--concurrency", type=int, default=4, help="jumlah worker paralel")
    be.add_argument("--seed", type=int, default=42)

    fe = sub.add_parser("finalize-emb", help="latih model stat+emb (1030-dim) → model_emb.json")
    fe.add_argument("--test-frac", type=float, default=0.2)
    fe.add_argument("--seed", type=int, default=42)
    fe.add_argument("--epochs", type=int, default=1200)
    fe.add_argument("--lr", type=float, default=0.2)
    fe.add_argument("--l2", type=float, default=1e-2)

    se = sub.add_parser("stream-emb", help="retrain model_emb TANPA simpan korpus (embed di RAM)")
    se.add_argument("--local-models", default="", help="model instance user (koma)")
    se.add_argument("--shared-models", default="", help="model Ollama bersama (koma)")
    se.add_argument("--target-ai", type=int, required=True, help="jumlah positif AI modern baru")
    se.add_argument("--extra-humans", type=int, default=0,
                    help="sampel manusia baru (di luar seed-cache)")
    se.add_argument("--id-frac", type=float, default=0.3, help="porsi sampel berbahasa Indonesia")
    se.add_argument("--seed-cache", dest="seed_cache", action="store_true", default=True,
                    help="muat cache lama agar keragaman generator lama terjaga (default)")
    se.add_argument("--no-seed-cache", dest="seed_cache", action="store_false",
                    help="abaikan cache lama; latih hanya dari sampel streaming")
    se.add_argument("--keep-vram", action="store_true",
                    help="jangan lepas VRAM generator usai latih")
    se.add_argument("--dry-run", action="store_true", help="jangan simpan model (uji saja)")
    se.add_argument("--max-seconds", type=int, default=7200)
    se.add_argument("--concurrency", type=int, default=4)
    se.add_argument("--test-frac", type=float, default=0.2)
    se.add_argument("--seed", type=int, default=42)
    se.add_argument("--epochs", type=int, default=1200)
    se.add_argument("--lr", type=float, default=0.2)
    se.add_argument("--l2", type=float, default=1e-2)

    hi = sub.add_parser("harvest-id", help="panen sampel manusia Indonesia → kedua cache")
    hi.add_argument("--target", type=int, required=True)
    hi.add_argument("--seed", type=int, default=42)

    gi = sub.add_parser("gen-id", help="generate sampel AI Indonesia → kedua cache")
    gi.add_argument("--local-models", default="")
    gi.add_argument("--shared-models", default="")
    gi.add_argument("--target", type=int, required=True)
    gi.add_argument("--max-seconds", type=int, default=7200)
    gi.add_argument("--concurrency", type=int, default=4)
    gi.add_argument("--seed", type=int, default=42)

    args = ap.parse_args()
    if args.mode == "generate":
        cmd_generate(args)
    elif args.mode == "finalize":
        cmd_finalize(args)
    elif args.mode == "build-emb":
        cmd_build_emb(args)
    elif args.mode == "finalize-emb":
        cmd_finalize_emb(args)
    elif args.mode == "stream-emb":
        cmd_stream_emb(args)
    elif args.mode == "harvest-id":
        cmd_harvest_id(args)
    elif args.mode == "gen-id":
        cmd_gen_id(args)
    else:
        ap.error(
            "pilih mode: generate | finalize | build-emb | finalize-emb | "
            "stream-emb | harvest-id | gen-id"
        )


if __name__ == "__main__":
    main()
