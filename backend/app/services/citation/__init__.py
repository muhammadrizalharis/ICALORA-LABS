"""Citation Finder — temukan sumber relevan dari korpus (1 juta+ dokumen)
lalu format sebagai sitasi APA, IEEE, MLA, Harvard, Vancouver, BibTeX & RIS.

Strategi: embed teks/klaim pengguna (bge-m3, GPU) -> cari tetangga terdekat di
corpus_embeddings (pgvector cosine). Hanya metadata publik yang dipakai
(judul, tahun, DOI, sumber), sehingga aman secara hak cipta.
"""

from __future__ import annotations

import re

import httpx
from sqlalchemy import text

from app.core.clients import corpus_size, engine
from app.core.config import get_settings
from app.services.embedding import embed_document
from app.services.llm.provider import get_llm

_NEAREST = text(
    """
    SELECT d.id, d.source, d.external_id, d.doi, d.title, d.pub_year,
           1 - (e.embedding <=> CAST(:qvec AS halfvec(1024))) AS cos_sim
    FROM corpus_embeddings e
    JOIN corpus_documents d ON d.id = e.doc_id
    ORDER BY e.embedding <=> CAST(:qvec AS halfvec(1024))
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


# Nama tampilan sumber korpus (alih-alih `.upper()` yang menghasilkan "ARXIV."
# sebagai nama jurnal/kontainer — tidak baku untuk gaya sitasi apa pun).
_SOURCE_DISPLAY = {
    "arxiv": "arXiv",
    "oa": "OA",
    "pubmed": "PubMed",
    "pmc": "PubMed Central",
    "europepmc": "Europe PMC",
    "crossref": "Crossref",
    "core": "CORE",
    "doaj": "DOAJ",
    "openalex": "OpenAlex",
    "semanticscholar": "Semantic Scholar",
    "unpaywall": "Unpaywall",
}


def _source_display(source: str | None) -> str:
    s = (source or "").strip()
    if not s:
        return "Sumber korpus"
    return _SOURCE_DISPLAY.get(s.lower(), s.replace("_", " ").title())


def _format_apa(title: str | None, year: int | None, doi: str | None, source: str) -> str:
    y = f"({year})" if year else "(n.d.)"
    t = (title or "[Judul tidak tersedia]").rstrip(".")
    doi_part = f" https://doi.org/{doi}" if doi else ""
    return f"{y}. {t}. {_source_display(source)}.{doi_part}".strip()


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


def _format_ieee(title: str | None, year: int | None, doi: str | None, source: str) -> str:
    t = (title or "[Judul tidak tersedia]").rstrip(".")
    y = f", {year}" if year else ""
    doi_part = f", doi: {doi}" if doi else ""
    return f'"{t}," {_source_display(source)}{y}{doi_part}.'


def _format_mla(title: str | None, year: int | None, doi: str | None, source: str) -> str:
    t = (title or "[Judul tidak tersedia]").rstrip(".")
    y = f", {year}" if year else ""
    doi_part = f", https://doi.org/{doi}" if doi else ""
    return f'"{t}." {_source_display(source)}{y}{doi_part}.'


def _format_harvard(title: str | None, year: int | None, doi: str | None, source: str) -> str:
    head = f"{year}." if year else "n.d."
    t = (title or "[Judul tidak tersedia]").rstrip(".")
    doi_part = f" Available at: https://doi.org/{doi}" if doi else ""
    return f"{head} '{t}', {_source_display(source)}.{doi_part}".strip()


def _format_vancouver(title: str | None, year: int | None, doi: str | None, source: str) -> str:
    t = (title or "[Judul tidak tersedia]").rstrip(".")
    y = f" {year}." if year else ""
    doi_part = f" Available from: https://doi.org/{doi}" if doi else ""
    return f"{t}. {_source_display(source)}.{y}{doi_part}".strip()


def _format_ris(
    title: str | None, year: int | None, doi: str | None, source: str
) -> str:
    lines = ["TY  - JOUR"]
    if title:
        lines.append(f"TI  - {title}")
    if year:
        lines.append(f"PY  - {year}")
    if doi:
        lines.append(f"DO  - {doi}")
        lines.append(f"UR  - https://doi.org/{doi}")
    lines.append(f"DB  - {source}")
    lines.append("ER  - ")
    return "\n".join(lines)


def _citation_entry(
    *, doc_id, source, external_id, title, pub_year, doi,
    relevance: float | None, online: bool = False,
) -> dict:
    """Bangun satu entri sitasi lengkap (semua gaya) dari metadata publik."""
    return {
        "doc_id": doc_id,
        "source": source,
        "external_id": external_id,
        "title": title,
        "pub_year": pub_year,
        "doi": doi,
        "url": f"https://doi.org/{doi}" if doi else None,
        "relevance": relevance,
        "online": online,
        "apa": _format_apa(title, pub_year, doi, source),
        "bibtex": _format_bibtex(title, pub_year, doi, source, doc_id or 0),
        "ieee": _format_ieee(title, pub_year, doi, source),
        "mla": _format_mla(title, pub_year, doi, source),
        "harvard": _format_harvard(title, pub_year, doi, source),
        "vancouver": _format_vancouver(title, pub_year, doi, source),
        "ris": _format_ris(title, pub_year, doi, source),
    }


def _crossref_fallback(query: str, need: int) -> list[dict]:
    """Ambil kandidat sitasi langsung dari Crossref bila korpus lokal kurang.

    Dipakai sebagai pelengkap agar pengguna tetap mendapat sumber relevan
    walau topiknya belum ada di korpus. Hanya metadata publik (judul, tahun,
    DOI) — aman hak cipta. Gagal-aman: error jaringan -> daftar kosong.
    """
    if need <= 0:
        return []
    mailto = (get_settings().contact_email or "").strip() or "noreply@icalora-labs.local"
    params = {
        "query.bibliographic": query[:250],
        "rows": min(20, max(need, 5)),
        "select": "DOI,title,issued",
        "mailto": mailto,
    }
    headers = {"User-Agent": f"ICALORA-LABS/1.0 (mailto:{mailto})"}
    try:
        with httpx.Client(timeout=httpx.Timeout(15.0, connect=6.0)) as client:
            resp = client.get(
                "https://api.crossref.org/works", params=params, headers=headers
            )
            resp.raise_for_status()
            items = resp.json().get("message", {}).get("items", [])
    except (httpx.HTTPError, ValueError):
        return []
    out: list[dict] = []
    for it in items:
        title = " ".join(it.get("title") or []).strip()
        doi = it.get("DOI")
        if not title or not doi:
            continue
        year = None
        try:
            year = (it.get("issued", {}).get("date-parts") or [[None]])[0][0]
        except (IndexError, TypeError, KeyError):
            year = None
        out.append(
            _citation_entry(
                doc_id=None, source="crossref", external_id=doi, title=title,
                pub_year=year, doi=doi, relevance=None, online=True,
            )
        )
    return out


def find_citations(query: str, top_k: int = 15, min_similarity: float = 0.35) -> dict:
    """Cari kandidat sitasi untuk `query` dari korpus lokal; bila hasil relevan
    kurang dari `top_k`, lengkapi dengan pencarian langsung ke Crossref."""
    query = query.strip()
    if not query:
        return {"query": "", "count": 0, "citations": []}

    llm = get_llm()
    qvec = embed_document(llm, query)

    with engine.connect() as conn:
        _set_ef_search(conn)
        rows = conn.execute(_NEAREST, {"qvec": _vec_literal(qvec), "k": top_k}).all()

    citations: list[dict] = []
    seen_doi: set[str] = set()
    for r in rows:
        sim = float(r.cos_sim) if r.cos_sim is not None else 0.0
        if sim < min_similarity:
            continue
        if r.doi:
            seen_doi.add(r.doi.lower())
        citations.append(
            _citation_entry(
                doc_id=r.id, source=r.source, external_id=r.external_id,
                title=r.title, pub_year=r.pub_year, doi=r.doi,
                relevance=round(sim * 100, 1), online=False,
            )
        )

    # Pelengkap online: hanya bila korpus lokal belum memenuhi top_k.
    if len(citations) < top_k:
        for entry in _crossref_fallback(query, top_k - len(citations)):
            doi = (entry.get("doi") or "").lower()
            if doi and doi in seen_doi:
                continue
            if doi:
                seen_doi.add(doi)
            citations.append(entry)
            if len(citations) >= top_k:
                break

    return {
        "query": query,
        "count": len(citations),
        "citations": citations,
        "corpus_size": corpus_size(),
        "min_similarity": min_similarity,
    }
