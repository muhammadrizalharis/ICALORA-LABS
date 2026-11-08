"""Helper umum untuk pipeline ingest korpus."""

from __future__ import annotations

import os
import re
from pathlib import Path

import numpy as np
import zstandard as zstd
from datasketch import MinHash
from sqlalchemy import text

from app.core.clients import engine

NUM_PERM = 128
_SHINGLE = 5  # word n-gram untuk MinHash
_WORD_RE = re.compile(r"\b[\w'-]+\b", re.UNICODE)

_zc = zstd.ZstdCompressor(level=19)
_zd = zstd.ZstdDecompressor()


def ensure_schema(skip_emb_index: bool | None = None) -> None:
    """Terapkan schema.sql.

    skip_emb_index: jika True, LEWATI pembuatan index HNSW embedding. Dipakai
    saat bulk-load embedding paralel — index HNSW mahal di-maintain per-insert
    dan sebaiknya dibangun sekali di akhir, bukan dibuat ulang tiap worker
    (yang justru saling mengunci). Jika None, dibaca dari env
    ICALORA_SKIP_EMB_INDEX (1/true untuk lewati).
    """
    if skip_emb_index is None:
        skip_emb_index = os.environ.get("ICALORA_SKIP_EMB_INDEX", "").lower() in ("1", "true", "yes")
    sql = (Path(__file__).parent / "schema.sql").read_text(encoding="utf-8")
    with engine.begin() as conn:
        for stmt in [s.strip() for s in sql.split(";") if s.strip()]:
            if skip_emb_index and "hnsw" in stmt.lower():
                continue
            conn.execute(text(stmt))


# Plafon total dokumen korpus. Mencegah korpus membengkak tak terkendali
# (beban disk). 0 = tanpa batas. Default dibuat moderat ("jangan berlebihan").
_DEFAULT_CORPUS_MAX_DOCS = 25_000_000


def corpus_cap() -> int:
    """Plafon total dokumen korpus dari env ICALORA_CORPUS_MAX_DOCS. 0 = tak terbatas."""
    try:
        cap = int(os.getenv("ICALORA_CORPUS_MAX_DOCS", str(_DEFAULT_CORPUS_MAX_DOCS)))
    except ValueError:
        cap = _DEFAULT_CORPUS_MAX_DOCS
    return max(0, cap)


def corpus_doc_count(exact: bool = True) -> int:
    """Jumlah dokumen korpus. exact=False memakai estimasi pg_class (instan)."""
    with engine.connect() as conn:
        if exact:
            return int(conn.execute(text("SELECT count(*) FROM corpus_documents")).scalar() or 0)
        est = conn.execute(
            text("SELECT reltuples::bigint FROM pg_class WHERE relname = 'corpus_documents'")
        ).scalar()
        return int(est or 0)


def corpus_cap_reached(exact: bool = True) -> bool:
    cap = corpus_cap()
    if cap <= 0:
        return False
    return corpus_doc_count(exact=exact) >= cap


# Lisensi yang mengizinkan penyimpanan & pemakaian full-text pada produk
# deteksi plagiarisme. Hanya yang benar-benar permisif.
# NC (non-komersial) & ND (tanpa turunan) DIKECUALIKAN demi aman hukum.
_FULLTEXT_OK = {
    "cc0",
    "ccby",
    "ccbysa",
    "pd",
    "publicdomain",
    "cczero",
    "ccpublicdomain",
}


def license_allows_fulltext(code: str | None) -> bool:
    """True bila lisensi mengizinkan simpan full-text untuk layanan komersial.

    Normalisasi 'CC BY', 'cc-by', 'CC-BY 4.0' → 'ccby'. NC/ND/tidak diketahui → False.
    """
    if not code:
        return False
    norm = re.sub(r"[^a-z0-9]", "", code.lower())
    # buang penanda versi seperti '40', '30' di belakang
    norm = re.sub(r"(by|sa|nc|nd|zero|cc0|publicdomain)\d+$", r"\1", norm)
    if "nc" in norm or "nd" in norm:
        return False
    return norm in _FULLTEXT_OK


def reconstruct_abstract(inverted_index: dict | None) -> str:
    """Bangun ulang abstrak dari abstract_inverted_index OpenAlex."""
    if not inverted_index:
        return ""
    positions: list[tuple[int, str]] = []
    for word, idxs in inverted_index.items():
        for i in idxs:
            positions.append((i, word))
    positions.sort(key=lambda t: t[0])
    return " ".join(w for _, w in positions)


def text_metrics(s: str) -> tuple[int, int]:
    return len(_WORD_RE.findall(s)), len(s)


def compress_text(s: str) -> bytes:
    return _zc.compress(s.encode("utf-8"))


def decompress_text(b: bytes) -> str:
    return _zd.decompress(b).decode("utf-8")


def make_minhash(s: str, num_perm: int = NUM_PERM) -> bytes | None:
    words = _WORD_RE.findall(s.lower())
    if len(words) < _SHINGLE:
        shingles = {" ".join(words)} if words else set()
    else:
        shingles = {" ".join(words[i : i + _SHINGLE]) for i in range(len(words) - _SHINGLE + 1)}
    if not shingles:
        return None
    mh = MinHash(num_perm=num_perm)
    for sh in shingles:
        mh.update(sh.encode("utf-8"))
    return mh.hashvalues.astype("<u8").tobytes()


def minhash_from_bytes(b: bytes, num_perm: int = NUM_PERM) -> MinHash:
    hv = np.frombuffer(b, dtype="<u8").astype(np.uint64)
    return MinHash(num_perm=num_perm, hashvalues=hv, scheme="affine32")
