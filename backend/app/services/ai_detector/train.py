"""Latih model AI Detector: manusia (korpus) vs AI (MULTI-MODEL, skema GELOMBANG).

Contoh:
    python -m app.services.ai_detector.train --per-class 5000

Sampel manusia = teks nyata dari korpus akses-terbuka. Sampel AI dibuat oleh
BANYAK model LLM dari DUA endpoint:
  * instance khusus milik user (GPU1, port 11500) — Qwen, Llama, Mistral, Phi, Gemma2
  * Ollama bersama (port 11434) — gemma4, gpt-oss, dll.
Memakai banyak arsitektur membuat detektor tidak sekadar menghafal satu gaya.

SKEMA GELOMBANG (sesuai permintaan): tiap gelombang menjalankan
  - N_LOCAL model serentak di instance user, DAN
  - N_SHARED model serentak di Ollama bersama
Setelah satu gelombang selesai (kuota sampel gelombang tercapai / batas waktu),
sistem MENDINGINKAN beberapa detik, lalu menjalankan gelombang berikutnya
dengan ROTASI set model lain. Begitu seterusnya hingga target tercapai.
Ini menjaga beban terkendali (tidak semua model sekaligus) & sopan ke GPU
bersama, sambil tetap mengumpulkan diversitas model yang kaya.

Fitur tiap sampel di-cache ke JSONL bertahap → aman terhadap gangguan (resume).
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

_LOCAL = os.environ.get("ICALORA_AI_ENDPOINT", "http://127.0.0.1:11500")
_SHARED = os.environ.get("ICALORA_SHARED_ENDPOINT", "http://127.0.0.1:11434")

# Kolam model per endpoint (dirotasi antar-gelombang).
_LOCAL_MODELS = ["qwen2.5:7b-instruct", "llama3.2:latest", "mistral:7b", "phi3:mini", "gemma2:9b"]
_SHARED_MODELS = ["gemma4:latest", "gpt-oss:latest", "gemma3:27b"]


def _pool(env: str, default: list[str]) -> list[str]:
    raw = os.environ.get(env)
    if raw:
        try:
            v = json.loads(raw)
            if isinstance(v, list) and v:
                return v
        except json.JSONDecodeError:
            pass
    return default


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
        "options": {"temperature": temp, "num_predict": 300, "num_ctx": _NUM_CTX},
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


def _run_wave(wave_lanes: list[tuple[str, str]], wave_quota: int, titles: list[str],
              ti_box: list[int], fh, X, y, lock: threading.Lock, total_box: list[int],
              target: int, wave_max_seconds: int) -> int:
    """Jalankan satu gelombang: tiap lane (endpoint,model) satu worker serentak.
    Berhenti saat kuota gelombang tercapai, judul habis, target total tercapai,
    atau melewati batas waktu. Kembalikan jumlah sampel yang dihasilkan gelombang."""
    wave_count = [0]
    deadline = time.time() + wave_max_seconds

    def next_title() -> str | None:
        with lock:
            if ti_box[0] >= len(titles):
                return None
            t = titles[ti_box[0]]
            ti_box[0] += 1
            return t

    def worker(endpoint: str, model: str, wid: int) -> None:
        rng = random.Random(10_000 + wid + int(time.time()) % 1000)
        fails = 0
        with httpx.Client() as client:
            while True:
                with lock:
                    if wave_count[0] >= wave_quota or total_box[0] >= target:
                        return
                if time.time() > deadline:
                    return
                title = next_title()
                if title is None:
                    return
                txt = _generate(client, endpoint, model, title, rng)
                if not txt:
                    fails += 1
                    if fails >= 15:
                        print(f"[train]   lane {model}@{endpoint} berhenti (15 gagal)", flush=True)
                        return
                    continue
                fails = 0
                feat = feature_vector(_statistical_signals(txt))
                with lock:
                    if wave_count[0] >= wave_quota or total_box[0] >= target:
                        return
                    X.append(feat)
                    y.append(1)
                    fh.write(json.dumps({"label": 1, "feat": feat, "src_id": None, "gen": model}) + "\n")
                    fh.flush()
                    wave_count[0] += 1
                    total_box[0] += 1
                    c = total_box[0]
                if c % 25 == 0:
                    print(f"[train]   sampel AI: {c}/{target}", flush=True)

    threads = []
    for wid, (endpoint, model) in enumerate(wave_lanes):
        t = threading.Thread(target=worker, args=(endpoint, model, wid), daemon=True)
        t.start()
        threads.append(t)
    for t in threads:
        t.join()
    return wave_count[0]


def _generate_ai(target: int, start_count: int, titles: list[str], fh, X, y, lock: threading.Lock,
                 n_local: int, n_shared: int, wave_size: int, cooldown: int, wave_max_seconds: int) -> None:
    """Loop gelombang: tiap gelombang = n_local model lokal + n_shared model bersama,
    serentak; lalu dinginkan `cooldown` detik; rotasi set model berikutnya."""
    local_pool = _pool("ICALORA_LOCAL_MODELS", _LOCAL_MODELS)
    shared_pool = _pool("ICALORA_SHARED_MODELS", _SHARED_MODELS)
    total_box = [start_count]
    ti_box = [0]
    li = si = 0
    wave_no = 0
    while total_box[0] < target and ti_box[0] < len(titles):
        wave_no += 1
        lanes: list[tuple[str, str]] = []
        picked_local, picked_shared = [], []
        for _ in range(n_local):
            if local_pool:
                m = local_pool[li % len(local_pool)]; li += 1
                lanes.append((_LOCAL, m)); picked_local.append(m)
        for _ in range(n_shared):
            if shared_pool:
                m = shared_pool[si % len(shared_pool)]; si += 1
                lanes.append((_SHARED, m)); picked_shared.append(m)
        print(f"[train] === GELOMBANG {wave_no}: saya={picked_local} | ollama={picked_shared} "
              f"(kuota {wave_size}) ===", flush=True)
        made = _run_wave(lanes, wave_size, titles, ti_box, fh, X, y, lock, total_box, target, wave_max_seconds)
        print(f"[train] gelombang {wave_no} selesai: +{made} (total AI={total_box[0]}/{target})", flush=True)
        if total_box[0] >= target or ti_box[0] >= len(titles):
            break
        print(f"[train] mendinginkan {cooldown}s…", flush=True)
        time.sleep(cooldown)


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


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--per-class", type=int, default=5000)
    ap.add_argument("--test-frac", type=float, default=0.2)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--n-local", type=int, default=2, help="model lokal serentak per gelombang")
    ap.add_argument("--n-shared", type=int, default=2, help="model Ollama bersama serentak per gelombang")
    ap.add_argument("--wave-size", type=int, default=200, help="sampel AI per gelombang")
    ap.add_argument("--cooldown", type=int, default=120, help="jeda pendingin antar-gelombang (detik)")
    ap.add_argument("--wave-max-seconds", type=int, default=1800, help="batas waktu satu gelombang")
    ap.add_argument("--fresh", action="store_true", help="abaikan cache, mulai dari nol")
    args = ap.parse_args()
    rng = random.Random(args.seed)

    if args.fresh and _CACHE_PATH.exists():
        _CACHE_PATH.unlink()

    X, y, used_ids = _load_cache()
    n_h = sum(1 for v in y if v == 0)
    n_a = sum(1 for v in y if v == 1)
    print(f"[train] cache awal: manusia={n_h} AI={n_a} (target {args.per_class}/kelas)", flush=True)

    fh = _CACHE_PATH.open("a", encoding="utf-8")
    try:
        if n_h < args.per_class:
            need = args.per_class - n_h
            print(f"[train] mengambil {need} sampel manusia tambahan…", flush=True)
            humans = _human_samples(need, used_ids)
            for doc_id, _title, body in humans:
                feat = feature_vector(_statistical_signals(body))
                X.append(feat)
                y.append(0)
                used_ids.add(doc_id)
                fh.write(json.dumps({"label": 0, "feat": feat, "src_id": doc_id}) + "\n")
                fh.flush()
            n_h = sum(1 for v in y if v == 0)
            print(f"[train] sampel manusia kini={n_h}", flush=True)

        if n_a < args.per_class:
            topics = [t for _id, t, _b in _human_samples(args.per_class + 2000, set())]
            lock = threading.Lock()
            _generate_ai(args.per_class, n_a, topics, fh, X, y, lock,
                         args.n_local, args.n_shared, args.wave_size, args.cooldown, args.wave_max_seconds)
    finally:
        fh.close()

    pos = sum(y)
    print(f"[train] total {len(X)} sampel (AI={pos}, manusia={len(y) - pos})", flush=True)
    if pos < 10 or (len(y) - pos) < 10:
        raise SystemExit("[train] sampel terlalu sedikit untuk melatih + validasi.")

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
    print(f"[train] split: latih={len(Xtr)} held-out={len(Xte)}; melatih…", flush=True)

    model = train(Xtr, ytr)
    metrics = _evaluate(model, Xte, yte)
    model.meta["validation"] = metrics
    model.meta["per_class"] = args.per_class
    model.meta["n_human"] = len(y) - pos
    model.meta["n_ai"] = pos
    model.meta["ai_models"] = _pool("ICALORA_LOCAL_MODELS", _LOCAL_MODELS) + _pool("ICALORA_SHARED_MODELS", _SHARED_MODELS)
    save(model)

    print("[train] === VALIDASI (held-out) ===", flush=True)
    print(f"  akurasi            : {metrics['accuracy']}")
    print(f"  false-positive rate: {metrics['false_positive_rate']}  (manusia dituduh AI)")
    print(f"  false-negative rate: {metrics['false_negative_rate']}  (AI lolos)")
    print(f"  precision / recall : {metrics['precision']} / {metrics['recall']}")
    print(f"  confusion          : {metrics['confusion']}")
    print(f"[train] selesai. akurasi latih={model.meta.get('train_accuracy')} n={model.meta.get('n')}", flush=True)


if __name__ == "__main__":
    main()
