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
        out = llm.chat(messages, temperature=0.7, max_tokens=320).strip()
        return out if len(out.split()) >= 60 else None
    except Exception:  # noqa: BLE001
        return None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--per-class", type=int, default=40)
    args = ap.parse_args()

    print(f"[train] mengambil {args.per_class} sampel manusia dari korpus…")
    humans = _human_samples(args.per_class)
    print(f"[train] dapat {len(humans)} sampel manusia; membuat sampel AI via LLM…")

    llm = get_llm()
    X: list[list[float]] = []
    y: list[int] = []
    for title, body in humans:
        X.append(feature_vector(_statistical_signals(body)))
        y.append(0)  # manusia
        ai = _ai_sample(llm, title)
        if ai:
            X.append(feature_vector(_statistical_signals(ai)))
            y.append(1)  # AI
    pos = sum(y)
    print(f"[train] total {len(X)} sampel (AI={pos}, manusia={len(y) - pos}); melatih…")

    if pos < 5 or (len(y) - pos) < 5:
        raise SystemExit("[train] sampel terlalu sedikit untuk melatih model.")

    model = train(X, y)
    save(model)
    print(f"[train] selesai. akurasi latih={model.meta.get('train_accuracy')} n={model.meta.get('n')}")


if __name__ == "__main__":
    main()
