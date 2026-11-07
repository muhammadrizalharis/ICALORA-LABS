"""Latih model AI Detector: manusia (abstrak korpus) vs AI (ditulis LLM).

Contoh:
    python -m app.services.ai_detector.train --per-class 40

Sampel manusia diambil dari korpus akses-terbuka (teks nyata manusia). Sampel
AI dibuat dengan meminta LLM lokal menulis abstrak akademik pada topik yang
sama (judul), sehingga kontras gaya—bukan topik—yang dipelajari model.
"""

from __future__ import annotations

import argparse
import random
import re

from sqlalchemy import text

from app.core.clients import engine
from app.ingest.common import decompress_text
from app.services.ai_detector import _statistical_signals
from app.services.ai_detector.model import feature_vector, save, train
from app.services.llm.provider import get_llm

_WORD_MIN, _WORD_MAX = 80, 400


def _human_samples(n: int) -> list[tuple[str, str]]:
    """Ambil (judul, teks) acak dari korpus. Mengembalikan hingga n sampel."""
    with engine.connect() as conn:
        max_id = conn.execute(text("SELECT max(id) FROM corpus_documents")).scalar() or 0
        out: list[tuple[str, str]] = []
        seen: set[int] = set()
        attempts = 0
        while len(out) < n and attempts < n * 20:
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
                out.append((row.title or "", body))
        return out


_DELIM = "#####"


def _ai_sample(llm, title: str) -> str | None:
    topic = title.strip() or "sebuah topik penelitian umum"
    messages = [
        {
            "role": "system",
            "content": (
                "Tulis satu abstrak akademik (120-200 kata) dalam gaya formal baku, "
                "tanpa menyebut bahwa ini dibuat AI. Hanya keluarkan teks abstrak."
            ),
        },
        {"role": "user", "content": f"Topik/judul: {topic}"},
    ]
    try:
        out = llm.chat(messages, temperature=0.7, max_tokens=256).strip()
        return out if len(out.split()) >= 60 else None
    except Exception:  # noqa: BLE001
        return None


def _ai_samples_batch(llm, titles: list[str]) -> list[str | None]:
    """Hasilkan banyak abstrak dalam SATU panggilan LLM (kurangi antre server).

    Mengembalikan daftar sejajar dgn titles (None bila gagal/terlalu pendek).
    """
    topics = [t.strip() or "sebuah topik penelitian umum" for t in titles]
    numbered = "\n".join(f"{i + 1}. {t}" for i, t in enumerate(topics))
    messages = [
        {
            "role": "system",
            "content": (
                "Untuk SETIAP topik bernomor, tulis satu abstrak akademik 100-180 kata "
                "dalam gaya formal baku. Pisahkan tiap abstrak dengan baris berisi "
                f"'{_DELIM}'. Keluarkan HANYA teks abstrak dalam urutan yang sama, "
                "tanpa nomor, judul, atau catatan tambahan."
            ),
        },
        {"role": "user", "content": f"Topik:\n{numbered}"},
    ]
    try:
        raw = llm.chat(messages, temperature=0.7, max_tokens=240 * len(titles)).strip()
    except Exception:  # noqa: BLE001
        return [None] * len(titles)
    parts = [p.strip() for p in raw.split(_DELIM)]
    # Buang penomoran sisa di awal tiap bagian.
    cleaned = [re.sub(r"^\s*\d+[.)]\s*", "", p).strip() for p in parts if p.strip()]
    out: list[str | None] = []
    for i in range(len(titles)):
        if i < len(cleaned) and len(cleaned[i].split()) >= 60:
            out.append(cleaned[i])
        else:
            out.append(None)
    return out


def _evaluate(model, X: list[list[float]], y: list[int]) -> dict:
    """Metrik pada data held-out (threshold 0.5). Fokus: false-positive rate."""
    tp = tn = fp = fn = 0
    for xi, yi in zip(X, y):
        pred = 1 if model.predict_proba(xi) >= 0.5 else 0
        if yi == 1 and pred == 1:
            tp += 1
        elif yi == 0 and pred == 0:
            tn += 1
        elif yi == 0 and pred == 1:
            fp += 1  # manusia salah dituduh AI (paling berbahaya)
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
    ap.add_argument("--per-class", type=int, default=40)
    ap.add_argument("--test-frac", type=float, default=0.25)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--batch", type=int, default=1, help="abstrak AI per panggilan LLM (1=andal)")
    args = ap.parse_args()

    print(f"[train] mengambil {args.per_class} sampel manusia dari korpus…")
    humans = _human_samples(args.per_class)
    print(f"[train] dapat {len(humans)} sampel manusia; membuat sampel AI via LLM (batch)…")

    llm = get_llm()
    X: list[list[float]] = []
    y: list[int] = []
    for title, body in humans:
        X.append(feature_vector(_statistical_signals(body)))
        y.append(0)  # manusia

    titles = [t for t, _ in humans]
    bs = max(1, args.batch)
    done = 0
    for i in range(0, len(titles), bs):
        chunk = titles[i : i + bs]
        samples = (
            [_ai_sample(llm, chunk[0])] if bs == 1 else _ai_samples_batch(llm, chunk)
        )
        for ai in samples:
            if ai:
                X.append(feature_vector(_statistical_signals(ai)))
                y.append(1)  # AI
        done += len(chunk)
        print(f"[train]   sampel AI: {done}/{len(titles)} topik diproses", flush=True)
    pos = sum(y)
    print(f"[train] total {len(X)} sampel (AI={pos}, manusia={len(y) - pos})")

    if pos < 8 or (len(y) - pos) < 8:
        raise SystemExit("[train] sampel terlalu sedikit untuk melatih + validasi.")

    # Split train/held-out terstratifikasi agar kedua kelas ada di test set.
    rng = random.Random(args.seed)
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
    print(f"[train] split: latih={len(Xtr)} held-out={len(Xte)}; melatih…")

    model = train(Xtr, ytr)
    metrics = _evaluate(model, Xte, yte)
    model.meta["validation"] = metrics
    model.meta["per_class"] = args.per_class
    save(model)

    print("[train] === VALIDASI (held-out) ===")
    print(f"  akurasi            : {metrics['accuracy']}")
    print(f"  false-positive rate: {metrics['false_positive_rate']}  (manusia dituduh AI)")
    print(f"  false-negative rate: {metrics['false_negative_rate']}  (AI lolos)")
    print(f"  precision / recall : {metrics['precision']} / {metrics['recall']}")
    print(f"  confusion          : {metrics['confusion']}")
    print(f"[train] selesai. akurasi latih={model.meta.get('train_accuracy')} n={model.meta.get('n')}")


if __name__ == "__main__":
    main()
