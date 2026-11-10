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
import hashlib
import re
from datetime import datetime, timezone
from urllib.parse import quote_plus
from xml.etree import ElementTree as ET

import httpx

from app.core.clients import redis_client
from app.core.config import get_settings
from app.ingest.common import text_metrics
from app.services.file_extract import extract_text

from . import _WORD_RE, _chunk_match, _extract_own_dois, _report_id, _sentences, _shingles

settings = get_settings()


_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")
_DOI_RE = re.compile(r"10\.\d{4,9}/[-._;()/:A-Za-z0-9]+", re.UNICODE)
_WORD_RE = re.compile(r"[A-Za-z\u00C0-\u024F]{2,}", re.UNICODE)
_UA = {"User-Agent": "ICALORA-LABS/1.0 (academic integrity; mailto:noreply@icalora-labs.local)"}
_TIMEOUT = httpx.Timeout(22.0, connect=8.0)
# Jumlah kalimat kueri bersifat ADAPTIF terhadap panjang dokumen: dokumen tebal
# (mis. 25+ halaman) memakai lebih banyak kalimat khas yang tersebar merata agar
# penemuan sumber lebih teliti. Tetap dalam anggaran waktu pemeriksaan (5–10 mnt).
_SENT_BASE = 60  # minimum kalimat kueri (dokumen pendek)
_SENT_CAP = 220  # plafon kalimat kueri (dokumen sangat tebal)
_PER_PROVIDER = 12  # kandidat teratas per kalimat per provider
_CONCURRENCY = 32  # batasi koneksi serempak agar provider tidak menolak
_MAILTO = "noreply@icalora-labs.local"  # OpenAlex/Crossref "polite pool"


async def _get_json(client: httpx.AsyncClient, url: str, params: dict, headers: dict | None = None):
    """GET dengan satu kali percobaan ulang untuk menahan kegagalan sesaat.

    Penanganan batas-laju: pada HTTP 429, jangan buang waktu mencoba ulang
    secara membabi-buta (akan 429 lagi). Hormati header `Retry-After` hanya
    bila nilainya kecil (<=2 dtk); selebihnya menyerah anggun → hasil kosong.
    """
    for attempt in range(2):
        try:
            r = await client.get(url, params=params, headers=headers)
            if r.status_code == 429:
                ra = r.headers.get("Retry-After")
                try:
                    delay = float(ra) if ra is not None else 0.0
                except ValueError:
                    delay = 0.0
                if attempt == 0 and 0 < delay <= 2.0:
                    await asyncio.sleep(delay)
                    continue
                return None  # batas-laju gigih → menyerah tanpa buang waktu
            r.raise_for_status()
            return r
        except Exception:  # noqa: BLE001
            if attempt == 1:
                return None
            await asyncio.sleep(0.4)
    return None


def _clean(txt: str) -> str:
    return _WS_RE.sub(" ", _TAG_RE.sub(" ", txt or "")).strip()


def _sentence_budget(doc: str) -> int:
    """Jumlah kalimat kueri yang menyesuaikan panjang dokumen.

    Dokumen pendek memakai `_SENT_BASE`; dokumen tebal naik proporsional
    hingga `_SENT_CAP`, sehingga paper 25+ halaman tetap tercakup menyeluruh
    tanpa melewati anggaran waktu pemeriksaan.
    """
    n = 0
    for s in _sentences(doc):
        wc = len(_WORD_RE.findall(s))
        if 8 <= wc <= 60:
            n += 1
    return max(_SENT_BASE, min(_SENT_CAP, round(n * 0.35)))


def _risky_sentences(doc: str, limit: int = _SENT_CAP) -> list[str]:
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


def _extract_dois(doc: str, limit: int = 5) -> list[str]:
    """Ambil DOI yang tertera di dokumen (mis. header paper terbit)."""
    out: list[str] = []
    seen: set[str] = set()
    for m in _DOI_RE.finditer(doc):
        d = m.group(0).rstrip(".,);]").lower()
        if d not in seen:
            seen.add(d)
            out.append(d)
        if len(out) >= limit:
            break
    return out


def _oa_pdf_from_openalex(w: dict) -> str | None:
    """URL PDF open-access dari work OpenAlex (best_oa/primary location)."""
    for loc in (w.get("best_oa_location"), w.get("primary_location")):
        if isinstance(loc, dict):
            pdf = loc.get("pdf_url")
            if pdf:
                return pdf
    oa = w.get("open_access") or {}
    return oa.get("oa_url") or None


def _oa_pdf_from_crossref(it: dict) -> str | None:
    """URL PDF teks-penuh dari field `link` Crossref (content-type pdf)."""
    links = it.get("link") or []
    pdfs = [
        lnk.get("URL")
        for lnk in links
        if isinstance(lnk, dict) and (lnk.get("content-type") == "application/pdf")
    ]
    if pdfs:
        return pdfs[0]
    for lnk in links:
        if isinstance(lnk, dict) and (lnk.get("URL") or "").lower().endswith(".pdf"):
            return lnk["URL"]
    return None


async def _fetch_fulltext(client: httpx.AsyncClient, url: str | None) -> str:
    """Ambil teks-PENUH open-access (PDF/HTML) secara ephemeral.

    Tidak menyimpan apa pun ke disk/DB — byte diproses di memori lalu dibuang.
    Dibatasi ukuran (`online_fulltext_max_bytes`) agar tidak mengunduh berkas
    raksasa. Mengembalikan "" bila gagal/terlalu besar/bukan dokumen teks.
    """
    if not url or not settings.online_fulltext_enabled:
        return ""
    cap = settings.online_fulltext_max_bytes
    try:
        async with client.stream(
            "GET", url, headers={"User-Agent": "Mozilla/5.0 (ICALORA-LABS)"}
        ) as resp:
            if resp.status_code != 200:
                return ""
            ctype = (resp.headers.get("content-type") or "").lower()
            buf = bytearray()
            async for chunk in resp.aiter_bytes():
                buf.extend(chunk)
                if len(buf) > cap:
                    return ""
        data = bytes(buf)
    except Exception:  # noqa: BLE001
        return ""
    if "html" in ctype and b"%PDF" not in data[:1024]:
        try:
            html = data.decode("utf-8", "ignore")
        except Exception:  # noqa: BLE001
            return ""
        return _clean(_TAG_RE.sub(" ", html))
    try:
        text = await asyncio.to_thread(extract_text, "oa.pdf", data)
    except Exception:  # noqa: BLE001
        return ""
    return _clean(text)


def _title_jaccard(a: str, b: str) -> float:
    wa = {w.lower() for w in _WORD_RE.findall(a or "")}
    wb = {w.lower() for w in _WORD_RE.findall(b or "")}
    if not wa or not wb:
        return 0.0
    return len(wa & wb) / len(wa | wb)


async def _unpaywall_oa_pdf(client: httpx.AsyncClient, doi: str | None) -> str | None:
    """Resolver DOI → URL PDF Open Access legal via Unpaywall.

    Unpaywall hanya mengindeks salinan OA yang SAH (repositori/penerbit), jadi
    aman dipakai untuk memperluas cakupan teks-penuh kandidat yang punya DOI
    tetapi belum memiliki `_oa_url` dari provider aslinya.
    """
    if not doi or not settings.online_unpaywall_enabled:
        return None
    r = await _get_json(
        client,
        f"https://api.unpaywall.org/v2/{quote_plus(doi)}",
        {"email": _MAILTO},
    )
    if r is None:
        return None
    try:
        data = r.json()
    except Exception:  # noqa: BLE001
        return None
    loc = data.get("best_oa_location") or {}
    return loc.get("url_for_pdf") or None


async def _enrich_fulltext(
    client: httpx.AsyncClient, cands: list[dict], doc: str, title_hint: str = ""
) -> None:
    """Perkaya kandidat dengan TEKS PENUH open-access (ephemeral, nol disk).

    Dua kelompok kandidat diambil teks penuhnya:
    1. Identitas-publikasi: paper yang kemungkinan dokumen itu sendiri
       (DOI/judul sendiri, atau abstrak hampir seluruhnya termuat).
    2. Paling mirip: calon sumber plagiarisme ber-tumpang-tindih abstrak
       tinggi dengan dokumen.
    Teks penuh (diunduh ephemeral, tak disimpan) menggantikan abstrak sebagai
    `_fulltext`, sehingga pencocokan baris-per-baris mencakup SELURUH isi
    sumber (bukan hanya abstrak) → % akurat untuk karya terbit/duplikat/salinan.
    """
    if not settings.online_fulltext_enabled:
        return
    titles = [t for t in (_extract_title(doc), _clean(title_hint or "")) if t]
    own_dois = {d.lower() for d in _extract_own_dois(doc)}
    doc_sh = _shingles([w.lower() for w in _WORD_RE.findall(doc)], 3)

    def _title_sim(c: dict) -> float:
        ct = c.get("title") or ""
        return max((_title_jaccard(ct, t) for t in titles), default=0.0)

    def _abs_containment(c: dict) -> float:
        # Porsi abstrak sumber yang sudah muncul di dokumen. Abstrak yang
        # hampir seluruhnya termuat = kandidat kuat sebagai publikasi dokumen
        # (bahkan bila judul tak terekstrak dari PDF, seperti header hilang).
        words = [w.lower() for w in _WORD_RE.findall(c.get("_fulltext") or "")]
        if len(words) < 40:
            return 0.0
        ssh = _shingles(words, 3)
        if not ssh or not doc_sh:
            return 0.0
        return len(ssh & doc_sh) / len(ssh)

    def _rank(c: dict) -> float:
        base = 1.0 if (c.get("doi") or "").lower() in own_dois else 0.0
        return base + _title_sim(c) + _abs_containment(c)

    def _passes_gate(c: dict) -> bool:
        return (
            (c.get("doi") or "").lower() in own_dois
            or _title_sim(c) >= 0.6
            or _abs_containment(c) >= 0.5
        )

    identity = [c for c in cands if _passes_gate(c)]
    identity.sort(key=_rank, reverse=True)

    # Selain identitas-publikasi, pilih kandidat PALING MIRIP (calon sumber
    # plagiarisme) berdasarkan tumpang-tindih abstrak dengan dokumen, agar
    # teks PENUH-nya ikut diperiksa — bukan hanya abstrak. Ini yang membuat
    # pemeriksaan mencakup seluruh isi sumber, tetap ephemeral (nol disk).
    id_keys = {id(c) for c in identity}
    similar = [
        c for c in cands if id(c) not in id_keys and _abs_containment(c) >= 0.10
    ]
    similar.sort(key=_abs_containment, reverse=True)
    similar = similar[: max(0, settings.online_fulltext_similar_docs)]

    # Gabungan kandidat yang akan diperkaya teks penuh (identitas + termirip).
    promising = identity[: max(1, settings.online_fulltext_max_docs)] + similar

    # Perluas cakupan: untuk kandidat menjanjikan yang punya DOI tetapi belum
    # memiliki URL PDF OA, coba resolusi lewat Unpaywall (hanya salinan OA sah).
    if settings.online_unpaywall_enabled:
        need_oa = [c for c in promising if c.get("doi") and not c.get("_oa_url")]
        resolved = await asyncio.gather(
            *(_unpaywall_oa_pdf(client, c.get("doi")) for c in need_oa),
            return_exceptions=True,
        )
        for c, oa in zip(need_oa, resolved, strict=False):
            if isinstance(oa, str) and oa:
                c["_oa_url"] = oa

    targets = [c for c in promising if c.get("_oa_url") or c.get("url")]
    if not targets:
        return

    async def _best_fulltext(c: dict) -> str:
        # Coba SEMUA URL yang tersedia untuk kandidat ini — URL PDF OA
        # (`_oa_url`) DAN URL hasil/unduh (`url`, mis. tautan unduh OJS yang
        # kerap menyajikan PDF langsung) — lalu ambil teks TERPANJANG. Ini
        # penting karena `_oa_url` dari mirror (mis. semanticscholar) sering
        # mati/kosong, sedangkan `url` penerbit justru berisi teks penuh.
        urls: list[str] = []
        for u in (c.get("_oa_url"), c.get("url")):
            if u and u not in urls:
                urls.append(u)
        if not urls:
            return ""
        fetched = await asyncio.gather(
            *(_fetch_fulltext(client, u) for u in urls),
            return_exceptions=True,
        )
        best = ""
        for t in fetched:
            if isinstance(t, str) and len(t) > len(best):
                best = t
        return best

    results = await asyncio.gather(
        *(_best_fulltext(c) for c in targets),
        return_exceptions=True,
    )
    for c, full in zip(targets, results, strict=False):
        if isinstance(full, str) and len(full) > len(c.get("_fulltext") or ""):
            c["_fulltext"] = full
            c["source"] = f"{c.get('source', '')} (teks penuh OA)".strip()
            c["_fulltext_full"] = True
            c["fulltext_oa"] = True


_TITLE_SKIP_KW = (
    "doi", "http", "@", "abstract", "abstrak", "keywords", "kata kunci",
    "received", "revised", "accepted", "published", "copyright", "©",
    "research article", "review article", "original article", "vol.", "vol ",
    "issn", "e-issn", "journal of", "proceedings", "preprint", "license",
    "creative commons", "author(s)", "all rights reserved",
)


def _extract_title(doc: str) -> str:
    """Tebak judul dokumen dari halaman depan.

    Judul kerap terpenggal menjadi beberapa baris pada ekstraksi PDF, dan
    didahului metadata jurnal (Received/Published/Vol./Research Article).
    Fungsi ini melewati baris metadata lalu menggabungkan baris judul yang
    berurutan menjadi satu — agar query pencarian paper terbit lebih tepat.
    """
    head = doc.strip()[:3000]
    buf: list[str] = []

    def _is_titleish(line: str) -> bool:
        words = _WORD_RE.findall(line)
        if len(words) < 2 or len(words) > 40:
            return False
        low = line.lower()
        if any(k in low for k in _TITLE_SKIP_KW):
            return False
        if sum(c.isdigit() for c in line) > len(line) * 0.3:
            return False
        # Baris penulis/afiliasi sering memuat banyak koma + angka superскрипт.
        if line.count(",") >= 3 and any(c.isdigit() for c in line):
            return False
        return True

    for raw in head.splitlines():
        line = raw.strip()
        if not line:
            if buf:
                break  # baris kosong menutup blok judul yang sudah terkumpul
            continue
        if _is_titleish(line):
            buf.append(line)
            # Judul utuh biasanya ≤ ~25 kata; hentikan bila sudah cukup panjang.
            if len(_WORD_RE.findall(" ".join(buf))) >= 25:
                break
        elif buf:
            break  # baris non-judul setelah blok judul → selesai
    title = " ".join(buf).strip()
    # Rapikan hyphenation pemenggalan baris: "C- Means" → "C-Means".
    title = re.sub(r"-\s+", "-", title)
    return title[:300]


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
        title = _clean(w.get("title") or "")
        doi = (w.get("doi") or "").replace("https://doi.org/", "") or None
        out.append(
            {
                "title": title,
                "doi": doi,
                "source": "OpenAlex",
                "url": w.get("id") or (f"https://doi.org/{doi}" if doi else None),
                "_fulltext": abstract or title,
                "_oa_url": _oa_pdf_from_openalex(w),
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
                "_oa_url": _oa_pdf_from_crossref(it),
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
        title = _clean(e.findtext("a:title", default="", namespaces=ns))
        summary = _clean(e.findtext("a:summary", default="", namespaces=ns))
        url = e.findtext("a:id", default="", namespaces=ns) or None
        # arXiv seluruhnya Open Access → turunkan URL PDF agar teks penuhnya
        # bisa diambil ephemeral (abs/ID → pdf/ID). Nol tambahan disk.
        oa_url = None
        if url:
            m = re.search(r"arxiv\.org/abs/([^\s?#]+)", url)
            if m:
                oa_url = f"https://arxiv.org/pdf/{m.group(1)}"
        out.append(
            {
                "title": title,
                "doi": None,
                "source": "arXiv",
                "url": url,
                "_fulltext": summary,
                "_oa_url": oa_url,
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


async def _q_europepmc(client: httpx.AsyncClient, sentence: str) -> list[dict]:
    """Europe PMC: literatur biomedis & ilmu hayati (gratis, tanpa kunci)."""
    r = await _get_json(
        client,
        "https://www.ebi.ac.uk/europepmc/webservices/rest/search",
        {
            "query": sentence[:250],
            "format": "json",
            "pageSize": _PER_PROVIDER,
            "resultType": "core",
        },
    )
    if r is None:
        return []
    try:
        data = r.json()
    except Exception:  # noqa: BLE001
        return []
    out = []
    for w in (data.get("resultList", {}).get("result", []) or [])[:_PER_PROVIDER]:
        abstract = _clean(w.get("abstractText") or "")
        title = _clean(w.get("title") or "")
        if not (abstract or title):
            continue
        doi = (w.get("doi") or "").lower() or None
        src = w.get("source")
        pid = w.get("id")
        url = (
            f"https://europepmc.org/article/{src}/{pid}"
            if src and pid
            else (f"https://doi.org/{doi}" if doi else None)
        )
        out.append(
            {
                "title": title,
                "doi": doi,
                "source": "Europe PMC",
                "url": url,
                "_fulltext": abstract or title,
            }
        )
    return out


async def _q_doaj(client: httpx.AsyncClient, sentence: str) -> list[dict]:
    """DOAJ: Directory of Open Access Journals (gratis, tanpa kunci; banyak
    jurnal Indonesia). Seluruh kontennya Open Access → legal untuk dibandingkan.
    """
    if not settings.online_doaj_enabled:
        return []
    q = quote_plus(sentence[:200])
    r = await _get_json(
        client,
        f"https://doaj.org/api/search/articles/{q}",
        {"pageSize": _PER_PROVIDER},
    )
    if r is None:
        return []
    try:
        data = r.json()
    except Exception:  # noqa: BLE001
        return []
    out = []
    for w in (data.get("results", []) or [])[:_PER_PROVIDER]:
        bj = w.get("bibjson") or {}
        title = _clean(bj.get("title") or "")
        abstract = _clean(bj.get("abstract") or "")
        if not (title or abstract):
            continue
        doi = None
        for ident in bj.get("identifier") or []:
            if (ident.get("type") or "").lower() == "doi":
                doi = (ident.get("id") or "").replace("https://doi.org/", "").lower() or None
        url = None
        oa_url = None
        for lnk in bj.get("link") or []:
            if (lnk.get("type") or "").lower() == "fulltext":
                u = lnk.get("url")
                url = url or u
                ct = (lnk.get("content_type") or "").lower()
                if u and ("pdf" in ct or u.lower().endswith(".pdf")):
                    oa_url = u
        year = bj.get("year")
        out.append(
            {
                "title": title,
                "doi": doi,
                "source": "DOAJ",
                "url": url or (f"https://doi.org/{doi}" if doi else None),
                "pub_year": int(year) if str(year or "").isdigit() else None,
                "_fulltext": abstract or title,
                "_oa_url": oa_url,
            }
        )
    return out


def _websearch_reserve() -> bool:
    """REM PENGAMAN kuota: pesan satu slot kueri web-search untuk bulan berjalan
    secara atomik (Redis INCR). Kembalikan True bila MASIH di dalam batas bulanan
    (`online_websearch_monthly_cap`) sehingga aman memanggil API berbayar.

    GAGAL-AMAN: bila Redis bermasalah atau cap<=0, kembalikan False → lewati API
    (nol panggilan, nol risiko tagihan). Kunci ber-nama per-bulan (YYYY-MM) dan
    kedaluwarsa otomatis ~45 hari, jadi kuota ter-reset tiap bulan tanpa campur
    tangan. Begitu cap tercapai, semua kueri berikutnya bulan itu dilewati.
    """
    cap = settings.online_websearch_monthly_cap
    if cap <= 0:
        return False
    try:
        r = redis_client()
        key = f"websearch:quota:{datetime.now(timezone.utc):%Y-%m}"
        n = r.incr(key)
        if n == 1:
            r.expire(key, 45 * 24 * 3600)
        return n <= cap
    except Exception:  # noqa: BLE001
        return False


def websearch_usage() -> dict:
    """Pemakaian kuota web-search bulan berjalan (untuk pemantauan/admin)."""
    cap = settings.online_websearch_monthly_cap
    try:
        r = redis_client()
        key = f"websearch:quota:{datetime.now(timezone.utc):%Y-%m}"
        used = int(r.get(key) or 0)
    except Exception:  # noqa: BLE001
        used = -1
    return {"month": f"{datetime.now(timezone.utc):%Y-%m}", "used": used, "cap": cap}


async def _q_brave(client: httpx.AsyncClient, sentence: str) -> list[dict]:
    """Web search umum (Brave Search API) sebagai VERIFIER bertarget — menangkap
    sumber yang lolos dari provider akademik (mis. halaman penerbit, repositori,
    blog). NONAKTIF otomatis bila `brave_api_key` kosong. Agar hemat kuota, hanya
    dipanggil untuk kalimat paling khas (lihat `_gather_candidates`). Hasilnya
    tetap ephemeral (snippet; teks-penuh OA hanya bila URL PDF) → nol disk.
    """
    if not settings.brave_api_key or not settings.online_websearch_enabled:
        return []
    # Rem pengaman: pesan slot kuota bulanan dulu. Bila sudah mentok batas,
    # LEWATI panggilan API (tak ada request terkirim → tak ada tagihan).
    if not _websearch_reserve():
        return []
    r = await _get_json(
        client,
        "https://api.search.brave.com/res/v1/web/search",
        {"q": sentence[:380], "count": settings.online_websearch_per_sentence},
        headers={
            "X-Subscription-Token": settings.brave_api_key,
            "Accept": "application/json",
        },
    )
    if r is None:
        return []
    try:
        data = r.json()
    except Exception:  # noqa: BLE001
        return []
    out = []
    web = (data.get("web") or {}).get("results") or []
    for w in web[: settings.online_websearch_per_sentence]:
        title = _clean(w.get("title") or "")
        desc = _clean(w.get("description") or "")
        url = w.get("url")
        if not (title and url):
            continue
        # Hanya URL PDF yang diambil teks-penuhnya (ephemeral); halaman HTML
        # memakai snippet saja agar legal & ringan.
        oa_url = url if url.lower().split("?")[0].endswith(".pdf") else None
        out.append(
            {
                "title": title,
                "doi": None,
                "source": "Web",
                "url": url,
                "_fulltext": desc or title,
                "_oa_url": oa_url,
            }
        )
    return out


async def _q_tavily(client: httpx.AsyncClient, sentence: str) -> list[dict]:
    """Web search umum (Tavily API) sebagai VERIFIER bertarget — menangkap sumber
    yang lolos dari provider akademik (mis. halaman penerbit, repositori, blog).
    NONAKTIF otomatis bila `tavily_api_key` kosong. Hemat kuota: hanya dipanggil
    untuk kalimat paling khas (lihat `_gather_candidates`), `search_depth=basic`
    = 1 kredit/kueri. Hasil ephemeral (snippet; teks-penuh OA hanya bila URL PDF)
    → nol disk. Rem pengaman kuota bulanan mencegah lewat tier gratis.
    """
    if not settings.tavily_api_key or not settings.online_websearch_enabled:
        return []
    if not _websearch_reserve():
        return []
    try:
        resp = await client.post(
            "https://api.tavily.com/search",
            json={
                "query": sentence[:400],
                "search_depth": "basic",
                "max_results": settings.online_websearch_per_sentence,
            },
            headers={"Authorization": f"Bearer {settings.tavily_api_key}"},
        )
        if resp.status_code != 200:
            return []
        data = resp.json()
    except Exception:  # noqa: BLE001
        return []
    out = []
    for w in (data.get("results") or [])[: settings.online_websearch_per_sentence]:
        title = _clean(w.get("title") or "")
        content = _clean(w.get("content") or "")
        url = w.get("url")
        if not (title and url):
            continue
        oa_url = url if url.lower().split("?")[0].endswith(".pdf") else None
        out.append(
            {
                "title": title,
                "doi": None,
                "source": "Web",
                "url": url,
                "_fulltext": content or title,
                "_oa_url": oa_url,
            }
        )
    return out


def _websearch_provider():
    """Pilih penyedia web-search aktif: Tavily diutamakan (tanpa kartu → bebas
    risiko tagihan), lalu Brave. None bila tak ada kunci terpasang."""
    if not settings.online_websearch_enabled:
        return None
    if settings.tavily_api_key:
        return _q_tavily
    if settings.brave_api_key:
        return _q_brave
    return None


async def _q_semanticscholar(client: httpx.AsyncClient, sentence: str) -> list[dict]:
    """Semantic Scholar: korpus lintas-disiplin (gratis; dibatasi laju ketat,
    kegagalan 429 ditangani anggun sebagai hasil kosong)."""
    r = await _get_json(
        client,
        "https://api.semanticscholar.org/graph/v1/paper/search",
        {
            "query": sentence[:250],
            "limit": _PER_PROVIDER,
            "fields": "title,abstract,externalIds,url",
        },
    )
    if r is None:
        return []
    try:
        data = r.json()
    except Exception:  # noqa: BLE001
        return []
    out = []
    for w in (data.get("data", []) or [])[:_PER_PROVIDER]:
        abstract = _clean(w.get("abstract") or "")
        title = _clean(w.get("title") or "")
        if not (abstract or title):
            continue
        doi = ((w.get("externalIds") or {}).get("DOI") or "").lower() or None
        out.append(
            {
                "title": title,
                "doi": doi,
                "source": "Semantic Scholar",
                "url": w.get("url") or (f"https://doi.org/{doi}" if doi else None),
                "_fulltext": abstract or title,
            }
        )
    return out


# Rencana penyedia: (fungsi, konkurensi-maks, jatah-kalimat). Penyedia yang
# dibatasi laju ketat (arXiv, Semantic Scholar) diberi konkurensi & jatah
# kalimat lebih kecil agar tidak diblokir dan tetap dalam anggaran waktu.
# (provider, konkurensi, bobot jatah, plafon jatah). Jatah kalimat tiap provider
# dihitung = clamp(bobot × anggaran_kalimat, 8, plafon). Provider kuat/cepat
# (Crossref, Europe PMC) memakai anggaran penuh; yang lambat/rawan rate-limit
# (Semantic Scholar) dibatasi ketat.
_PROVIDER_PLAN: list[tuple] = [
    (_q_openalex, 3, 0.40, 60),
    (_q_crossref, 8, 1.00, _SENT_CAP),
    (_q_europepmc, 8, 1.00, _SENT_CAP),
    (_q_doaj, 4, 0.60, 80),
    (_q_wikipedia, 6, 0.60, 80),
    (_q_arxiv, 3, 0.60, 80),
    (_q_semanticscholar, 1, 0.25, 20),
]


def _provider_plan(budget: int = _SENT_CAP) -> list[tuple]:
    """Hitung jatah kalimat per provider dari anggaran kalimat dokumen."""

    def _slot(weight: float, cap: int) -> int:
        return max(8, min(cap, round(budget * weight)))

    plan = [(fn, conc, _slot(weight, cap)) for fn, conc, weight, cap in _PROVIDER_PLAN]
    if settings.core_enabled and settings.core_api_key:
        plan.append((_q_core, 4, _slot(1.00, _SENT_CAP)))
    return plan


def _active_providers() -> list:
    return [fn for fn, _c, _s in _provider_plan()]


async def _q_openalex_doi(client: httpx.AsyncClient, doi: str) -> dict | None:
    r = await _get_json(client, f"https://api.openalex.org/works/doi:{doi}", {"mailto": _MAILTO})
    if r is None:
        return None
    w = r.json()
    abstract = _clean(_openalex_abstract(w.get("abstract_inverted_index")))
    if not abstract:
        return None
    return {
        "title": _clean(w.get("title") or ""),
        "doi": doi,
        "source": "OpenAlex",
        "url": w.get("id") or f"https://doi.org/{doi}",
        "_fulltext": abstract,
        "_oa_url": _oa_pdf_from_openalex(w),
    }


async def _q_crossref_doi(client: httpx.AsyncClient, doi: str) -> dict | None:
    r = await _get_json(client, f"https://api.crossref.org/works/{doi}", {"mailto": _MAILTO})
    if r is None:
        return None
    it = r.json().get("message", {})
    title = _clean(" ".join(it.get("title") or []))
    abstract = _clean(it.get("abstract") or "")
    if not (abstract or title):
        return None
    return {
        "title": title,
        "doi": doi,
        "source": "Crossref",
        "url": it.get("URL") or f"https://doi.org/{doi}",
        "_fulltext": abstract or title,
        "_oa_url": _oa_pdf_from_crossref(it),
    }


async def _q_title(client: httpx.AsyncClient, title: str) -> list[dict]:
    """Temukan paper terbit yang judulnya paling cocok (OpenAlex + Crossref).
    Mengembalikan kandidat dengan abstrak — dipakai untuk mendeteksi bahwa
    dokumen adalah publikasi terindeks (reverse-containment)."""
    if not title:
        return []
    out: list[dict] = []
    oa, cr = await asyncio.gather(
        _q_openalex(client, title), _q_crossref(client, title), return_exceptions=True
    )
    for res in (oa, cr):
        if isinstance(res, list):
            out.extend(res)
    return out


async def _resolve_publication(
    client: httpx.AsyncClient, doc: str, title_hint: str = ""
) -> list[dict]:
    """Kumpulkan kandidat 'identitas publikasi' via DOI SENDIRI + judul.

    Hanya DOI milik dokumen sendiri (front-matter) yang di-resolve — DOI
    referensi yang dikutip diabaikan agar tidak salah-tandai sebagai publikasi.
    `title_hint` (mis. nama berkas unggahan) ditambahkan sebagai query judul
    cadangan: banyak PDF akademik dinamai sesuai judulnya, sehingga membantu
    menemukan paper terbit saat judul tak terekstrak dari isi PDF.
    """
    tasks: list = []
    for doi in _extract_own_dois(doc):
        tasks.append(_q_openalex_doi(client, doi))
        tasks.append(_q_crossref_doi(client, doi))
    queries = {_extract_title(doc)}
    hint = _clean(title_hint or "")
    if hint and len(_WORD_RE.findall(hint)) >= 4:
        queries.add(hint)
    for q in queries:
        if q:
            tasks.append(_q_title(client, q))
    results = await asyncio.gather(*tasks, return_exceptions=True)
    out: list[dict] = []
    for res in results:
        if isinstance(res, dict):
            out.append(res)
        elif isinstance(res, list):
            out.extend(res)
    return out


async def _gather_candidates(
    doc: str, title_hint: str = ""
) -> tuple[list[dict], list[str], dict]:
    budget = _sentence_budget(doc)
    sentences = _risky_sentences(doc, budget)
    plan = _provider_plan(budget)
    provider_hits: dict[str, int] = {}
    seen: dict[str, dict] = {}
    async with httpx.AsyncClient(timeout=_TIMEOUT, headers=_UA, follow_redirects=True) as client:
        gsem = asyncio.Semaphore(_CONCURRENCY)

        async def _run(provider, psem, sentence):
            async with psem, gsem:
                return await provider(client, sentence)

        tasks = []
        for provider, conc, sent_budget in plan:
            psem = asyncio.Semaphore(conc)
            for s in sentences[:sent_budget]:
                tasks.append(_run(provider, psem, s))
        # Resolusi identitas publikasi (DOI + judul) berjalan paralel.
        pub_task = asyncio.create_task(
            _resolve_publication(doc=doc, client=client, title_hint=title_hint)
        )
        results = await asyncio.gather(*tasks, return_exceptions=True)
        pub_results = await pub_task
        # Fase VERIFIER web search (Tavily/Brave): HANYA kalimat paling khas,
        # serial dengan jeda kecil menghormati batas laju paket gratis. Nonaktif
        # otomatis bila tak ada kunci (nol kuota). Rem pengaman kuota bulanan di
        # dalam provider mencegah melewati tier gratis.
        web_results: list = []
        web_provider = _websearch_provider()
        if web_provider is not None:
            for s in sentences[: settings.online_websearch_sentences]:
                try:
                    web_results.append(await web_provider(client, s))
                except Exception:  # noqa: BLE001
                    pass
                await asyncio.sleep(1.1)
    for res in list(results) + [pub_results] + web_results:
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
            else:
                if not seen[key].get("_oa_url") and cand.get("_oa_url"):
                    seen[key]["_oa_url"] = cand["_oa_url"]
                if len(cand["_fulltext"]) > len(seen[key].get("_fulltext") or ""):
                    seen[key]["_fulltext"] = cand["_fulltext"]
    candidates = list(seen.values())
    # Fase terpisah: perkaya kandidat identitas-publikasi dengan TEKS PENUH
    # open-access. Dijalankan SETELAH query kalimat selesai (pool koneksi
    # senggang) memakai klien khusus bertimeout lebih panjang, agar unduhan
    # PDF besar tidak bersaing dan timeout. Ephemeral — tidak disimpan ke disk.
    if settings.online_fulltext_enabled:
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(45.0, connect=10.0),
            headers=_UA,
            follow_redirects=True,
        ) as ftclient:
            await _enrich_fulltext(ftclient, candidates, doc, title_hint)
    return candidates, sentences, provider_hits


async def online_candidates(doc: str, title_hint: str = "") -> tuple[list[dict], dict]:
    """Kumpulkan kandidat sumber daring (tanpa-unduh) untuk digabungkan ke
    pemeriksaan plagiarisme utama. Kembalikan (kandidat, hits-per-penyedia).
    Aman dipanggil opsional: galat jaringan menghasilkan daftar kosong.
    `title_hint` opsional (mis. nama berkas) membantu menemukan paper terbit.
    """
    doc = (doc or "").strip()
    if not doc or not _active_providers():
        return [], {}
    try:
        candidates, _sentences, provider_hits = await _gather_candidates(doc, title_hint)
    except Exception:  # noqa: BLE001
        return [], {}
    return candidates, provider_hits


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
