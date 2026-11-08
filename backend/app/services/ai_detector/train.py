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
import threading
import time
from pathlib import Path

import httpx
from sqlalchemy import text

from app.core.clients import engine
from app.ingest.common import decompress_text
from app.services.ai_detector import _statistical_signals
from app.services.ai_detector.model import feature_vector, save, train

_WORD_MIN, _WORD_MAX = 80, 400
_CACHE_PATH = Path(__file__).resolve().parent / "train_features.jsonl"
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

    args = ap.parse_args()
    if args.mode == "generate":
        cmd_generate(args)
    elif args.mode == "finalize":
        cmd_finalize(args)
    else:
        ap.error("pilih mode: generate | finalize")


if __name__ == "__main__":
    main()
