"""Latih model AI Detector: manusia (abstrak korpus) vs AI (ditulis LLM).

Contoh:
    python -m app.services.ai_detector.train --per-class 1500

Sampel manusia diambil dari korpus akses-terbuka (teks nyata manusia). Sampel
AI dibuat dengan meminta LLM lokal menulis teks akademik pada topik yang sama
(judul) dalam BERAGAM gaya & temperatur, sehingga kontras gaya—bukan topik—
yang dipelajari model, dan model tidak overfit pada satu pola tunggal.

Fitur tiap sampel di-cache ke JSONL secara bertahap sehingga proses panjang
(ribuan sampel) aman terhadap gangguan: menjalankan ulang akan melanjutkan,
bukan mengulang dari nol.
"""

from __future__ import annotations

import argparse
import json
import random
from pathlib import Path

from sqlalchemy import text

from app.core.clients import engine
from app.ingest.common import decompress_text
from app.services.ai_detector import _statistical_signals
from app.services.ai_detector.model import feature_vector, save, train
from app.services.llm.provider import get_llm

_WORD_MIN, _WORD_MAX = 80, 400
_CACHE_PATH = Path(__file__).resolve().parent / "train_features.jsonl"

# Variasi gaya penulisan AI (register akademik berbeda) agar dataset realistis
# dan model tidak belajar satu pola tunggal.
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
    """Ambil (id, judul, teks) acak dari korpus. Mengembalikan hingga n sampel."""
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


def _ai_sample(llm, title: str, rng: random.Random) -> str | None:
    """Hasilkan satu teks akademik gaya AI dengan gaya & temperatur acak."""
    topic = title.strip() or "sebuah topik penelitian umum"
    style = rng.choice(_AI_STYLES)
    temp = rng.choice(_AI_TEMPS)
    messages = [
        {
            "role": "system",
            "content": f"{style} Jangan menyebut bahwa teks ini dibuat AI. Keluarkan HANYA teksnya.",
        },
        {"role": "user", "content": f"Topik/judul: {topic}"},
    ]
    try:
        out = llm.chat(messages, temperature=temp, max_tokens=300).strip()
        return out if len(out.split()) >= 60 else None
    except Exception:  # noqa: BLE001
        return None


def _load_cache() -> tuple[list[list[float]], list[int], set[int]]:
    """Muat fitur yang sudah di-cache: (X, y, human_ids_terpakai)."""
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


def _append_cache(fh, label: int, feat: list[float], src_id: int | None) -> None:
    fh.write(json.dumps({"label": label, "feat": feat, "src_id": src_id}) + "\n")
    fh.flush()


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
    ap.add_argument("--per-class", type=int, default=1500)
    ap.add_argument("--test-frac", type=float, default=0.2)
    ap.add_argument("--seed", type=int, default=42)
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
        # 1) Lengkapi sampel MANUSIA (murah: langsung dari korpus).
        if n_h < args.per_class:
            need = args.per_class - n_h
            print(f"[train] mengambil {need} sampel manusia tambahan…", flush=True)
            humans = _human_samples(need, used_ids)
            for doc_id, _title, body in humans:
                feat = feature_vector(_statistical_signals(body))
                X.append(feat)
                y.append(0)
                used_ids.add(doc_id)
                _append_cache(fh, 0, feat, doc_id)
            n_h = sum(1 for v in y if v == 0)
            print(f"[train] sampel manusia kini={n_h}", flush=True)

        # 2) Lengkapi sampel AI (mahal: generate LLM, satu per satu, di-cache).
        if n_a < args.per_class:
            llm = get_llm()
            # Pakai judul dokumen manusia sebagai topik agar kontras GAYA, bukan topik.
            topics = _human_samples(args.per_class + 300, set())
            ti = 0
            while n_a < args.per_class and ti < len(topics):
                title = topics[ti][1]
                ti += 1
                ai = _ai_sample(llm, title, rng)
                if not ai:
                    continue
                feat = feature_vector(_statistical_signals(ai))
                X.append(feat)
                y.append(1)
                _append_cache(fh, 1, feat, None)
                n_a += 1
                if n_a % 25 == 0:
                    print(f"[train]   sampel AI: {n_a}/{args.per_class}", flush=True)
    finally:
        fh.close()

    pos = sum(y)
    print(f"[train] total {len(X)} sampel (AI={pos}, manusia={len(y) - pos})", flush=True)
    if pos < 10 or (len(y) - pos) < 10:
        raise SystemExit("[train] sampel terlalu sedikit untuk melatih + validasi.")

    # Split train/held-out terstratifikasi agar kedua kelas ada di test set.
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
