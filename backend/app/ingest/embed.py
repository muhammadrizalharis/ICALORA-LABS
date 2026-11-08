"""Stage-2: embedder semantik GPU untuk korpus.

Membaca corpus_documents yang belum punya embedding, menghitung vektor
bge-m3 (1024-dim) via Ollama (GPU), menyimpan ke corpus_embeddings, lalu
menandai has_embedding=TRUE. Resumable lewat flag tersebut.

GPU-first: Ollama menjalankan bge-m3 di GPU. Batch kecil + jeda singkat agar
tetap "tetangga baik" di GPU bersama.

Jalankan:
    python -m app.ingest.embed --target 1000000 --batch 16
"""

from __future__ import annotations

import argparse
import signal
import sys
import time

from sqlalchemy import text

from app.core.clients import engine
from app.ingest.common import decompress_text, ensure_schema
from app.services.llm.provider import get_llm

EMBED_CHARS = 4000  # potong teks panjang (cukup untuk sinyal semantik dok-level)
_STOP = False


def _handle_stop(signum, frame):  # noqa: ARG001
    global _STOP
    _STOP = True
    print(f"\n[embed] sinyal {signum} diterima — berhenti setelah batch ini…", flush=True)


signal.signal(signal.SIGTERM, _handle_stop)
signal.signal(signal.SIGINT, _handle_stop)

_SELECT_BATCH = text(
    """
    SELECT id, title, text_zstd
    FROM corpus_documents
    WHERE has_embedding = FALSE
    ORDER BY id
    LIMIT :lim
    """
)
_INSERT_EMB = text(
    "INSERT INTO corpus_embeddings (doc_id, embedding) "
    "VALUES (:doc_id, CAST(:embedding AS halfvec(1024))) ON CONFLICT (doc_id) DO NOTHING"
)
_MARK_DONE = text("UPDATE corpus_documents SET has_embedding = TRUE WHERE id = ANY(:ids)")


def _prep_text(title: str | None, text_zstd: bytes | None) -> str:
    body = decompress_text(text_zstd) if text_zstd else ""
    combined = f"{title or ''}\n{body}".strip()
    return combined[:EMBED_CHARS]


def _vec_literal(vec: list[float]) -> str:
    return "[" + ",".join(f"{x:.6f}" for x in vec) + "]"


def run(target: int, batch: int, pause: float) -> None:
    ensure_schema()
    llm = get_llm()
    done = 0
    while not _STOP and done < target:
        with engine.connect() as conn:
            rows = conn.execute(_SELECT_BATCH, {"lim": batch}).all()
        if not rows:
            print("[embed] tidak ada dokumen tersisa — selesai.")
            break
        ids = [r[0] for r in rows]
        texts = [_prep_text(r[1], r[2]) for r in rows]
        try:
            vectors = llm.embed_batch(texts)
        except Exception as exc:  # noqa: BLE001
            print(f"[embed] gagal batch (akan dicoba lagi): {exc}", file=sys.stderr, flush=True)
            time.sleep(5)
            continue
        payload = [
            {"doc_id": did, "embedding": _vec_literal(vec)}
            for did, vec in zip(ids, vectors, strict=True)
        ]
        with engine.begin() as conn:
            conn.execute(_INSERT_EMB, payload)
            conn.execute(_MARK_DONE, {"ids": ids})
        done += len(ids)
        print(f"[embed] +{len(ids)} (total sesi {done})", flush=True)
        if pause:
            time.sleep(pause)
    print(f"[embed] berhenti pada {done} dokumen terproses (sesi ini).")


def main() -> None:
    ap = argparse.ArgumentParser(description="Embedder semantik GPU korpus (bge-m3)")
    ap.add_argument("--target", type=int, default=1_000_000)
    ap.add_argument("--batch", type=int, default=16)
    ap.add_argument(
        "--pause", type=float, default=0.2, help="jeda antar-batch (detik), tetangga baik GPU"
    )
    args = ap.parse_args()
    run(args.target, args.batch, args.pause)


if __name__ == "__main__":
    main()
