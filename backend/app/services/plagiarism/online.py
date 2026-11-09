"""Lapis pemeriksaan daring (tanpa unduh) terhadap sumber akademik gratis.

Berbeda dari korpus lokal terindeks, lapis ini TIDAK menyimpan apa pun ke
disk/DB: untuk tiap dokumen, beberapa kalimat paling "berisiko" dikirim ke
API pencarian pihak ketiga secara real-time, kandidat teratas ditarik
abstraknya, lalu dibandingkan secara lokal memakai mesin pencocokan tingkat
kalimat yang sama (`_chunk_match`).

Desain pluggable: tiap sumber adalah provider terpisah yang bisa dimatikan
lewat flag tanpa merusak aplikasi. OpenAlex/Crossref/arXiv/Wikipedia bebas
dipakai; CORE hanya aktif bila `core_api_key` diisi dan `core_enabled` benar
(sesuai Ketentuan Penggunaan CORE).
"""

from __future__ import annotations

import asyncio
import re
from xml.etree import ElementTree as ET

import httpx

from app.core.config import get_settings

from . import _WORD_RE, _chunk_match, _report_id, _sentences
from datetime import datetime, timezone
import hashlib

from app.ingest.common import text_metrics

settings = get_settings()


_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")
_UA = {"User-Agent": "ICALORA-LABS/1.0 (academic integrity; mailto:noreply@icalora-labs.local)"}
_TIMEOUT = httpx.Timeout(20.0, connect=8.0)
_MAX_SENTENCES = 12
_PER_PROVIDER = 2  # kandidat teratas per kalimat per provider
_CONCURRENCY = 8   # batasi koneksi serempak agar provider tidak menolak
_MAILTO = "noreply@icalora-labs.local"  # OpenAlex/Crossref "polite pool"


async def _get_json(client: httpx.AsyncClient, url: str, params: dict, headers: dict | None = None):
    """GET dengan satu kali percobaan ulang untuk menahan kegagalan sesaat."""
    for attempt in range(2):
        try:
            r = await client.get(url, params=params, headers=headers)
            r.raise_for_status()
            return r
        except Exception:  # noqa: BLE001
            if attempt == 1:
                return None
            await asyncio.sleep(0.4)
    return None


def _clean(txt: str) -> str:
    return _WS_RE.sub(" ", _TAG_RE.sub(" ", txt or "")).strip()


def _risky_sentences(doc: str, limit: int = _MAX_SENTENCES) -> list[str]:
    """Pilih kalimat paling khas (panjang + banyak kata jarang) sebagai sampel
    kueri — menghindari kalimat umum yang menghasilkan kueri tak berarti."""
    out: list[tuple[float, str]] = []
    for s in _sentences(doc):
        words = _WORD_RE.findall(s)
        if len(words) < 8 or len(words) > 60:
            continue
        distinct = sum(1 for w in words if len(w) >= 8)
        score = len(words) + distinct * 2
        out.append((score, s.strip()))
    out.sort(key=lambda x: x[0], reverse=True)
    picked: list[str] = []
    seen: set[str] = set()
    for _, s in out:
        key = s[:60].lower()
        if key in seen:
            continue
        seen.add(key)
        picked.append(s)
        if len(picked) >= limit:
            break
    return picked


def _openalex_abstract(inv: dict | None) -> str:
    if not inv:
        return ""
    positions: list[tuple[int, str]] = []
    for word, idxs in inv.items():
        for i in idxs:
            positions.append((i, word))
    positions.sort(key=lambda x: x[0])
    return " ".join(w for _, w in positions)


async def _q_openalex(client: httpx.AsyncClient, sentence: str) -> list[dict]:
    r = await _get_json(
        client,
        "https://api.openalex.org/works",
        {"search": sentence[:250], "per_page": _PER_PROVIDER, "mailto": _MAILTO},
    )
    if r is None:
        return []
    data = r.json()
    out = []
    for w in data.get("results", [])[:_PER_PROVIDER]:
        abstract = _clean(_openalex_abstract(w.get("abstract_inverted_index")))
        doi = (w.get("doi") or "").replace("https://doi.org/", "") or None
        out.append(
            {
                "title": _clean(w.get("title") or ""),
                "doi": doi,
                "source": "OpenAlex",
                "url": w.get("id") or (f"https://doi.org/{doi}" if doi else None),
                "_fulltext": abstract,
            }
        )
    return out


async def _q_crossref(client: httpx.AsyncClient, sentence: str) -> list[dict]:
    r = await _get_json(
        client,
        "https://api.crossref.org/works",
        {"query.bibliographic": sentence[:250], "rows": _PER_PROVIDER, "mailto": _MAILTO},
    )
    if r is None:
        return []
    data = r.json()
    out = []
    for it in data.get("message", {}).get("items", [])[:_PER_PROVIDER]:
        title = _clean(" ".join(it.get("title") or []))
        abstract = _clean(it.get("abstract") or "")
        doi = it.get("DOI")
        out.append(
            {
                "title": title,
                "doi": doi,
                "source": "Crossref",
                "url": it.get("URL") or (f"https://doi.org/{doi}" if doi else None),
                "_fulltext": abstract or title,
            }
        )
    return out


async def _q_arxiv(client: httpx.AsyncClient, sentence: str) -> list[dict]:
    r = await _get_json(
        client,
        "http://export.arxiv.org/api/query",
        {"search_query": f"all:{sentence[:200]}", "max_results": _PER_PROVIDER},
    )
    if r is None:
        return []
    try:
        root = ET.fromstring(r.text)
    except Exception:  # noqa: BLE001
        return []
    ns = {"a": "http://www.w3.org/2005/Atom"}
    out = []
    for e in root.findall("a:entry", ns)[:_PER_PROVIDER]:
        title = _clean((e.findtext("a:title", default="", namespaces=ns)))
        summary = _clean((e.findtext("a:summary", default="", namespaces=ns)))
        url = e.findtext("a:id", default="", namespaces=ns) or None
        out.append(
            {
                "title": title,
                "doi": None,
                "source": "arXiv",
                "url": url,
                "_fulltext": summary,
            }
        )
    return out


async def _q_wikipedia(client: httpx.AsyncClient, sentence: str) -> list[dict]:
    r = await _get_json(
        client,
        "https://en.wikipedia.org/w/api.php",
        {
            "action": "query",
            "list": "search",
            "srsearch": sentence[:250],
            "srlimit": _PER_PROVIDER,
            "format": "json",
        },
    )
    if r is None:
        return []
    data = r.json()
    out = []
    for hit in data.get("query", {}).get("search", [])[:_PER_PROVIDER]:
        out.append(
            {
                "title": _clean(hit.get("title") or ""),
                "doi": None,
                "source": "Wikipedia",
                "url": "https://en.wikipedia.org/?curid=" + str(hit.get("pageid"))
                if hit.get("pageid")
                else None,
                "_fulltext": _clean(hit.get("snippet") or ""),
            }
        )
    return out


async def _q_core(client: httpx.AsyncClient, sentence: str) -> list[dict]:
    key = settings.core_api_key
    if not key:
        return []
    r = await _get_json(
        client,
        "https://api.core.ac.uk/v3/search/works",
        {"q": sentence[:250], "limit": _PER_PROVIDER},
        headers={"Authorization": f"Bearer {key}"},
    )
    if r is None:
        return []
    data = r.json()
    out = []
    for w in data.get("results", [])[:_PER_PROVIDER]:
        body = _clean(w.get("abstract") or "") or _clean((w.get("fullText") or "")[:1200])
        doi = w.get("doi")
        out.append(
            {
                "title": _clean(w.get("title") or ""),
                "doi": doi,
                "source": "CORE",
                "url": w.get("downloadUrl") or (f"https://doi.org/{doi}" if doi else None),
                "_fulltext": body,
            }
        )
    return out


def _active_providers() -> list:
    providers = [_q_openalex, _q_crossref, _q_arxiv, _q_wikipedia]
    if settings.core_enabled and settings.core_api_key:
        providers.append(_q_core)
    return providers


async def _gather_candidates(doc: str) -> tuple[list[dict], list[str], dict]:
    sentences = _risky_sentences(doc)
    providers = _active_providers()
    provider_hits: dict[str, int] = {}
    seen: dict[str, dict] = {}
    async with httpx.AsyncClient(timeout=_TIMEOUT, headers=_UA, follow_redirects=True) as client:
        sem = asyncio.Semaphore(_CONCURRENCY)

        async def _run(provider, sentence):
            async with sem:
                return await provider(client, sentence)

        tasks = [_run(p, s) for s in sentences for p in providers]
        results = await asyncio.gather(*tasks, return_exceptions=True)
    for res in results:
        if isinstance(res, Exception) or not res:
            continue
        for cand in res:
            if not cand.get("_fulltext") or not cand.get("title"):
                continue
            key = (cand.get("doi") or cand["title"]).lower().strip()
            provider_hits[cand["source"]] = provider_hits.get(cand["source"], 0) + 1
            if key not in seen:
                cand["doc_id"] = None
                seen[key] = cand
            elif len(cand["_fulltext"]) > len(seen[key].get("_fulltext") or ""):
                seen[key]["_fulltext"] = cand["_fulltext"]
    return list(seen.values()), sentences, provider_hits


async def online_check(doc: str) -> dict:
    """Jalankan pemeriksaan daring tanpa-unduh dan kembalikan laporan ringkas."""
    doc = doc.strip()
    wc, cc = text_metrics(doc)
    generated_at = datetime.now(timezone.utc)
    if cc == 0:
        return {
            "online": True,
            "overall_similarity": 0.0,
            "integrity_index": 0.0,
            "matched_passages": [],
            "match_groups": [],
            "sources": [],
            "word_count": 0,
            "char_count": 0,
        }

    candidates, sentences, provider_hits = await _gather_candidates(doc)
    chunk = _chunk_match(doc, candidates)

    # Agregasi sumber yang benar-benar menghasilkan temuan.
    by_src: dict[str, dict] = {}
    for p in chunk["matched_passages"]:
        key = (p.get("source_doi") or p.get("source_title") or "").lower().strip()
        if not key:
            continue
        agg = by_src.setdefault(
            key, {"title": p.get("source_title"), "doi": p.get("source_doi"), "count": 0}
        )
        agg["count"] += 1
    # Lampirkan URL/source dari kandidat.
    meta = {}
    for c in candidates:
        k = (c.get("doi") or c.get("title") or "").lower().strip()
        meta[k] = {"url": c.get("url"), "source": c.get("source")}
    sources = []
    for key, agg in sorted(by_src.items(), key=lambda kv: kv[1]["count"], reverse=True):
        m = meta.get(key, {})
        sources.append(
            {
                "title": agg["title"],
                "doi": agg["doi"],
                "url": m.get("url"),
                "source": m.get("source"),
                "matches": agg["count"],
            }
        )

    return {
        "online": True,
        "overall_similarity": chunk["similarity_index"],
        "integrity_index": chunk["similarity_index"],
        "similarity_index": chunk["similarity_index"],
        "matched_sentences": chunk["matched_sentences"],
        "total_sentences": chunk["total_sentences"],
        "matched_passages": chunk["matched_passages"],
        "match_groups": chunk["match_groups"],
        "sources": sources,
        "word_count": wc,
        "char_count": cc,
        "queried_sentences": len(sentences),
        "candidates_checked": len(candidates),
        "providers": [
            {"name": n, "hits": h} for n, h in sorted(provider_hits.items())
        ],
        "report_id": _report_id(doc, generated_at),
        "content_sha256": hashlib.sha256(doc.encode("utf-8")).hexdigest(),
        "generated_at": generated_at.isoformat(timespec="seconds"),
        "coverage_note": (
            "Pemeriksaan daring real-time terhadap OpenAlex, Crossref, arXiv, "
            "Wikipedia"
            + (", dan CORE" if settings.core_enabled and settings.core_api_key else "")
            + ". Hanya sampel kalimat paling khas yang diperiksa; hasil bersifat "
            "pelengkap deteksi salinan, bukan pemeriksaan menyeluruh."
        ),
    }
