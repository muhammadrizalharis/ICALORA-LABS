"""Citation Finder — temukan sumber relevan dari korpus (1 juta+ dokumen)
lalu format sebagai sitasi APA & BibTeX.

Strategi: embed teks/klaim pengguna (bge-m3, GPU) -> cari tetangga terdekat di
corpus_embeddings (pgvector cosine). Hanya metadata publik yang dipakai
(judul, tahun, DOI, sumber), sehingga aman secara hak cipta.
"""

from __future__ import annotations

import re

from sqlalchemy import text

from app.core.clients import corpus_size, engine
from app.services.embedding import embed_document
from app.services.llm.provider import get_llm

_NEAREST = text(
    """
    SELECT d.id, d.source, d.external_id, d.doi, d.title, d.pub_year,
           1 - (e.embedding <=> CAST(:qvec AS vector)) AS cos_sim
    FROM corpus_embeddings e
    JOIN corpus_documents d ON d.id = e.doc_id
    ORDER BY e.embedding <=> CAST(:qvec AS vector)
    LIMIT :k
    """
)


def _vec_literal(vec: list[float]) -> str:
    return "[" + ",".join(f"{x:.6f}" for x in vec) + "]"


# Perluas cakupan pencarian HNSW agar menelusuri korpus (1,2 juta+) jauh lebih
# luas sebelum memilih kandidat terbaik — recall mendekati pemindaian penuh.
_EF_SEARCH = 500


def _set_ef_search(conn) -> None:
    conn.execute(text(f"SET LOCAL hnsw.ef_search = {_EF_SEARCH}"))


def _bibtex_key(title: str | None, year: int | None, doc_id: int) -> str:
    base = ""
    if title and title.split(" "):
        base = re.sub(r"[^A-Za-z]", "", title.split(" ")[0]).lower()
    return f"{base or 'ref'}{year or ''}_{doc_id}"


def _format_apa(title: str | None, year: int | None, doi: str | None, source: str) -> str:
    y = f"({year})" if year else "(n.d.)"
    t = (title or "[Judul tidak tersedia]").rstrip(".")
    doi_part = f" https://doi.org/{doi}" if doi else ""
    return f"{y}. {t}. {source.upper()}.{doi_part}".strip()


def _format_bibtex(
    title: str | None, year: int | None, doi: str | None, source: str, doc_id: int
) -> str:
    key = _bibtex_key(title, year, doc_id)
    lines = [f"@article{{{key},"]
    if title:
        lines.append(f"  title = {{{title}}},")
    if year:
        lines.append(f"  year = {{{year}}},")
    if doi:
        lines.append(f"  doi = {{{doi}}},")
    lines.append(f"  note = {{Sumber korpus: {source}}}")
    lines.append("}")
    return "\n".join(lines)


def find_citations(query: str, top_k: int = 15, min_similarity: float = 0.35) -> dict:
    """Cari kandidat sitasi untuk `query` dari korpus."""
    query = query.strip()
    if not query:
        return {"query": "", "count": 0, "citations": []}

    llm = get_llm()
    qvec = embed_document(llm, query)

    with engine.connect() as conn:
        _set_ef_search(conn)
        rows = conn.execute(_NEAREST, {"qvec": _vec_literal(qvec), "k": top_k}).all()

    citations: list[dict] = []
    for r in rows:
        sim = float(r.cos_sim) if r.cos_sim is not None else 0.0
        if sim < min_similarity:
            continue
        citations.append(
            {
                "doc_id": r.id,
                "source": r.source,
                "external_id": r.external_id,
                "title": r.title,
                "pub_year": r.pub_year,
                "doi": r.doi,
                "url": f"https://doi.org/{r.doi}" if r.doi else None,
                "relevance": round(sim * 100, 1),
                "apa": _format_apa(r.title, r.pub_year, r.doi, r.source),
                "bibtex": _format_bibtex(r.title, r.pub_year, r.doi, r.source, r.id),
            }
        )

    return {
        "query": query,
        "count": len(citations),
        "citations": citations,
        "corpus_size": corpus_size(),
    }
