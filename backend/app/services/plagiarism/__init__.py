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

import re

from sqlalchemy import text

from app.core.clients import engine
from app.ingest.common import (
    decompress_text,
    make_minhash,
    minhash_from_bytes,
    text_metrics,
)
from app.services.llm.provider import get_llm

_SHINGLE = 5
_SENT_RE = re.compile(r"[^.!?\n]+[.!?]?", re.UNICODE)
_WORD_RE = re.compile(r"\w+", re.UNICODE)


def _shingles(words: list[str], n: int = _SHINGLE) -> set[str]:
    if len(words) < n:
        return {" ".join(words)} if words else set()
    return {" ".join(words[i : i + n]) for i in range(len(words) - n + 1)}


def _sentences(s: str) -> list[str]:
    return [m.group(0).strip() for m in _SENT_RE.finditer(s) if len(m.group(0).strip()) >= 20]


def _chunk_match(doc: str, candidates: list[dict], threshold: float = 0.55) -> dict:
    """Pencocokan tingkat-kalimat (gaya Turnitin) terhadap dokumen kandidat.

    Untuk tiap kalimat masukan, hitung containment shingle terhadap gabungan
    shingle tiap dokumen kandidat; kalimat dengan containment tinggi ditandai
    sebagai kutipan yang cocok. Indeks kemiripan = proporsi karakter yang cocok.
    """
    cand_shingles: list[tuple[dict, set[str]]] = []
    for c in candidates:
        body = c.get("_fulltext") or ""
        if not body:
            continue
        words = [w.lower() for w in _WORD_RE.findall(body)]
        cand_shingles.append((c, _shingles(words)))

    sentences = _sentences(doc)
    matched: list[dict] = []
    matched_chars = 0
    total_chars = max(len(doc), 1)

    for sent in sentences:
        words = [w.lower() for w in _WORD_RE.findall(sent)]
        sh = _shingles(words)
        if not sh:
            continue
        best_ratio = 0.0
        best_src: dict | None = None
        for c, cset in cand_shingles:
            if not cset:
                continue
            overlap = len(sh & cset)
            ratio = overlap / len(sh)
            if ratio > best_ratio:
                best_ratio = ratio
                best_src = c
        if best_ratio >= threshold and best_src is not None:
            matched_chars += len(sent)
            matched.append(
                {
                    "sentence": sent[:300],
                    "match_ratio": round(best_ratio * 100, 1),
                    "source_title": best_src.get("title"),
                    "source_doi": best_src.get("doi"),
                    "doc_id": best_src.get("doc_id"),
                }
            )

    similarity_index = round(matched_chars / total_chars * 100, 1)
    matched.sort(key=lambda m: m["match_ratio"], reverse=True)
    return {
        "similarity_index": similarity_index,
        "matched_sentences": len(matched),
        "total_sentences": len(sentences),
        "matched_passages": matched[:50],
    }


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
        fulltext = decompress_text(r.text_zstd) if r.text_zstd else ""
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
                "snippet": fulltext[:320].strip(),
                "_fulltext": fulltext,
            }
        )

    # Pencocokan tingkat-kalimat untuk indeks kemiripan gaya Turnitin.
    chunk = _chunk_match(doc, sources)
    for s in sources:
        s.pop("_fulltext", None)

    sources.sort(key=lambda s: (s["lexical_similarity"], s["semantic_similarity"]), reverse=True)
    # Indeks kemiripan utama = kecocokan leksikal/salinan (gaya Turnitin).
    # Semantik dilaporkan terpisah sebagai risiko parafrase (butuh ambang tinggi).
    overall = max((s["lexical_similarity"] for s in sources), default=0.0)
    paraphrase = max((s["semantic_similarity"] for s in sources), default=0.0)
    # Gabungkan: indeks utama = maksimum antara coverage kalimat dan leksikal dokumen.
    similarity_index = max(overall, chunk["similarity_index"])
    return {
        "overall_similarity": similarity_index,
        "document_lexical_similarity": overall,
        "paraphrase_similarity": paraphrase,
        "similarity_index": chunk["similarity_index"],
        "matched_sentences": chunk["matched_sentences"],
        "total_sentences": chunk["total_sentences"],
        "matched_passages": chunk["matched_passages"],
        "word_count": wc,
        "char_count": cc,
        "sources": sources,
    }
