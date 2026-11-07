"""Publikasi Jurnal.

Dari abstrak/naskah pengguna, cari paper terbit yang paling relevan di korpus
(pgvector) lalu rekomendasikan bidang & contoh venue akses-terbuka tempat karya
serupa dipublikasikan, plus penilaian kesiapan singkat via LLM.

Catatan: korpus tidak menyimpan nama jurnal/venue, sehingga rekomendasi berupa
bidang dominan + contoh paper terbit (dengan DOI) sebagai acuan target.
"""

from __future__ import annotations

from collections import Counter

from sqlalchemy import text

from app.core.clients import corpus_size, engine
from app.ingest.common import decompress_text
from app.services.llm.provider import get_llm

_NEAREST = text(
    """
    SELECT d.id, d.source, d.doi, d.title, d.pub_year, d.fields, d.text_zstd,
           1 - (e.embedding <=> CAST(:qvec AS vector)) AS cos_sim
    FROM corpus_embeddings e
    JOIN corpus_documents d ON d.id = e.doc_id
    ORDER BY e.embedding <=> CAST(:qvec AS vector)
    LIMIT :k
    """
)

_SOURCE_LABEL = {
    "openalex": "OpenAlex (indeks jurnal akses-terbuka global)",
    "pmc": "PubMed Central (biomedis akses-terbuka)",
}


def _vec_literal(vec: list[float]) -> str:
    return "[" + ",".join(f"{x:.6f}" for x in vec) + "]"


# Perluas cakupan pencarian HNSW agar menelusuri korpus (1,2 juta+) jauh lebih
# luas sebelum memilih kandidat terbaik — recall mendekati pemindaian penuh.
_EF_SEARCH = 500


def _set_ef_search(conn) -> None:
    conn.execute(text(f"SET LOCAL hnsw.ef_search = {_EF_SEARCH}"))


def _readiness(text_in: str) -> dict:
    llm = get_llm()
    messages = [
        {
            "role": "system",
            "content": (
                "Anda reviewer jurnal. Nilai kesiapan naskah/abstrak untuk publikasi. "
                "Balas HANYA JSON: {\"readiness_score\": <0-100>, "
                "\"strengths\": [\"...\"], \"gaps\": [\"...\"], "
                "\"recommended_fields\": [\"...\"], \"advice\": \"<1-2 kalimat>\"}"
            ),
        },
        {"role": "user", "content": text_in[:6000]},
    ]
    raw = llm.chat(messages, temperature=0.3, max_tokens=800)
    from app.services.llm.tasks import _extract_json

    try:
        data = _extract_json(raw)
        return data if isinstance(data, dict) else {}
    except Exception:  # noqa: BLE001
        return {"readiness_score": None, "advice": raw[:400]}


def recommend_journals(doc: str, top_k: int = 15) -> dict:
    """Rekomendasi publikasi berdasarkan kemiripan dengan paper terbit."""
    doc = doc.strip()
    if not doc:
        return {"matches": [], "fields": [], "sources": [], "readiness": {}}

    llm = get_llm()
    qvec = llm.embed(doc[:4000])
    with engine.connect() as conn:
        _set_ef_search(conn)
        rows = conn.execute(_NEAREST, {"qvec": _vec_literal(qvec), "k": top_k}).all()

    matches: list[dict] = []
    field_counter: Counter[str] = Counter()
    source_counter: Counter[str] = Counter()
    for r in rows:
        fields = list(r.fields) if r.fields else []
        for f in fields:
            field_counter[f] += 1
        source_counter[r.source] += 1
        snippet = ""
        if r.text_zstd:
            snippet = decompress_text(r.text_zstd)[:240].strip()
        matches.append(
            {
                "title": r.title,
                "doi": r.doi,
                "pub_year": r.pub_year,
                "source": r.source,
                "fields": fields[:5],
                "relevance": round(float(r.cos_sim) * 100, 1),
                "snippet": snippet,
            }
        )

    top_fields = [{"field": f, "count": c} for f, c in field_counter.most_common(8)]
    sources = [
        {"source": s, "label": _SOURCE_LABEL.get(s, s), "count": c}
        for s, c in source_counter.most_common()
    ]

    return {
        "matches": matches,
        "fields": top_fields,
        "sources": sources,
        "readiness": _readiness(doc),
        "corpus_size": corpus_size(),
        "note": (
            "Rekomendasi berbasis kemiripan dengan paper terbit akses-terbuka. "
            "Bidang & contoh paper menjadi acuan untuk memilih jurnal tujuan."
        ),
    }
