"""Deteksi kemiripan / plagiarisme terhadap korpus.

Strategi dua lapis (seperti alat komersial):
  1. Semantik (parafrase): embed teks (bge-m3, GPU) lalu cari tetangga
     terdekat di corpus_embeddings via pgvector cosine (index HNSW).
  2. Leksikal (salinan): MinHash Jaccard antara teks masukan dan dokumen
     kandidat (dari corpus_fingerprints).

Keterbatasan MVP: fingerprint tingkat-dokumen, jadi angka leksikal adalah
kemiripan keseluruhan, bukan per-paragraf. Pencocokan tingkat-paragraf
menyusul (chunk-level).
"""

from __future__ import annotations

from sqlalchemy import text

from app.core.clients import engine
from app.ingest.common import (
    decompress_text,
    make_minhash,
    minhash_from_bytes,
    text_metrics,
)
from app.services.llm.provider import get_llm

_NEAREST = text(
    """
    SELECT d.id, d.source, d.external_id, d.doi, d.title, d.pub_year,
           d.text_zstd, f.minhash,
           1 - (e.embedding <=> CAST(:qvec AS vector)) AS cos_sim
    FROM corpus_embeddings e
    JOIN corpus_documents d ON d.id = e.doc_id
    LEFT JOIN corpus_fingerprints f ON f.doc_id = d.id
    ORDER BY e.embedding <=> CAST(:qvec AS vector)
    LIMIT :k
    """
)


def _vec_literal(vec: list[float]) -> str:
    return "[" + ",".join(f"{x:.6f}" for x in vec) + "]"


def _snippet(text_zstd: bytes | None, limit: int = 320) -> str:
    if not text_zstd:
        return ""
    body = decompress_text(text_zstd)
    return body[:limit].strip()


def check_plagiarism(doc: str, top_k: int = 10) -> dict:
    """Bandingkan `doc` dengan korpus; kembalikan laporan kemiripan."""
    doc = doc.strip()
    wc, cc = text_metrics(doc)
    if cc == 0:
        return {"overall_similarity": 0.0, "sources": [], "word_count": 0, "char_count": 0}

    llm = get_llm()
    qvec = llm.embed(doc[:4000])
    q_mh_bytes = make_minhash(doc)
    q_mh = minhash_from_bytes(q_mh_bytes) if q_mh_bytes else None

    with engine.connect() as conn:
        rows = conn.execute(_NEAREST, {"qvec": _vec_literal(qvec), "k": top_k}).all()

    sources: list[dict] = []
    for r in rows:
        cos_sim = float(r.cos_sim) if r.cos_sim is not None else 0.0
        lexical = 0.0
        if q_mh is not None and r.minhash is not None:
            lexical = float(q_mh.jaccard(minhash_from_bytes(bytes(r.minhash))))
        sources.append(
            {
                "doc_id": r.id,
                "source": r.source,
                "external_id": r.external_id,
                "doi": r.doi,
                "title": r.title,
                "pub_year": r.pub_year,
                "semantic_similarity": round(cos_sim * 100, 1),
                "lexical_similarity": round(lexical * 100, 1),
                "similarity": round(max(cos_sim, lexical) * 100, 1),
                "snippet": _snippet(r.text_zstd),
            }
        )

    sources.sort(key=lambda s: (s["lexical_similarity"], s["semantic_similarity"]), reverse=True)
    # Indeks kemiripan utama = kecocokan leksikal/salinan (gaya Turnitin).
    # Semantik dilaporkan terpisah sebagai risiko parafrase (butuh ambang tinggi).
    overall = max((s["lexical_similarity"] for s in sources), default=0.0)
    paraphrase = max((s["semantic_similarity"] for s in sources), default=0.0)
    return {
        "overall_similarity": overall,
        "paraphrase_similarity": paraphrase,
        "word_count": wc,
        "char_count": cc,
        "sources": sources,
    }
