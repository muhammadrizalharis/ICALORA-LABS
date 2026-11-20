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
import logging
import re
from contextvars import ContextVar
from datetime import datetime, timezone
from html import unescape as _html_unescape
from urllib.parse import quote_plus, urljoin, urlparse
from xml.etree import ElementTree as ET

import httpx

from app.core.clients import redis_client
from app.core.config import get_settings
from app.ingest.common import text_metrics
from app.services.file_extract import extract_text

from . import _chunk_match, _extract_own_dois, _report_id, _sentences, _shingles, online_cache

settings = get_settings()


# Hanya cocok TAG HTML/XML asli (diawali huruf atau `/huruf`, tanpa baris-baru,
# panjang terbatas). Pola lama `<[^>]+>` rakus: pada teks PDF akademik, sebuah
# `<` dari notasi matematis (mis. `p < ε`) sampai `>` berikutnya ribuan karakter
# jauhnya ikut terhapus — bisa membuang ~28% isi dokumen, sehingga sumber yang
# IDENTIK pun hanya tercakup ~72%. Pola ini aman untuk teks matematis.
_TAG_RE = re.compile(r"</?[a-zA-Z][^<>\n]{0,200}?>")
_WS_RE = re.compile(r"\s+")
# Pembersih HTML halaman penerbit (BUKAN isi dokumen): buang komentar,
# script/style, lalu SEMUA tag termasuk `<!doctype>` & `<html ...>` panjang
# yang lolos dari `_TAG_RE` konservatif → teks landing bersih untuk cuplikan.
_HTML_COMMENT_RE = re.compile(r"<!--.*?-->", re.S)
_HTML_SCRIPT_RE = re.compile(r"<(script|style)\b[^>]*>.*?</\1>", re.I | re.S)
_HTML_TAG_RE = re.compile(r"<[^>]+>", re.S)
_DOI_RE = re.compile(r"10\.\d{4,9}/[-._;()/:A-Za-z0-9]+", re.UNICODE)
_WORD_RE = re.compile(r"[A-Za-z\u00C0-\u024F]{2,}", re.UNICODE)
_UA = {"User-Agent": "ICALORA-LABS/1.0 (academic integrity; mailto:noreply@icalora-labs.local)"}
_TIMEOUT = httpx.Timeout(22.0, connect=8.0)
# Jumlah kalimat kueri bersifat ADAPTIF terhadap panjang dokumen: dokumen tebal
# (mis. 25+ halaman) memakai lebih banyak kalimat khas yang tersebar merata agar
# penemuan sumber lebih teliti. Tetap dalam anggaran waktu pemeriksaan (5–10 mnt).
_SENT_BASE = 60  # minimum kalimat kueri (dokumen pendek)
_SENT_CAP = 220  # plafon kalimat kueri (dokumen sangat tebal)
_PER_PROVIDER = 18  # kandidat teratas per kalimat per provider (lebih banyak hasil)
_CONCURRENCY = 32  # batasi koneksi serempak agar provider tidak menolak
# Batas unduhan teks-penuh OA yang berjalan serempak. Tanpa batas, menaikkan
# jumlah kandidat termirip bisa memicu puluhan unduhan PDF sekaligus → membebani
# jaringan & server penerbit. Semaphore ini "memperlambat" dengan sehat: lebih
# banyak sumber diperiksa, tetapi laju unduh tetap terkendali (dalam anggaran
# 5–10 mnt job latar belakang).
_FULLTEXT_FETCH_CONC = 12
_FT_FETCH_SEM: asyncio.Semaphore | None = None
_MAILTO = "noreply@icalora-labs.local"  # OpenAlex/Crossref "polite pool"


_log = logging.getLogger(__name__)

# ── Pemantauan batas-laju (HTTP 429) ─────────────────────────────────────────
# Bila Crossref/OpenAlex membatasi permintaan, pencarian daring diam-diam
# menghasilkan lebih sedikit sumber sehingga skor bisa lebih rendah dari
# seharusnya. Hitung per-job (untuk catatan di laporan) dan per-hari di Redis
# (untuk pemantauan admin), serta catat peringatan di log.
_RL_JOB: ContextVar[dict | None] = ContextVar("icalora_rate_limited", default=None)
_RL_NAMES = ("openalex", "crossref", "unpaywall", "arxiv", "core", "other")
RATE_LIMIT_NOTE_MIN = 20  # ambang 429 per-job sebelum laporan memberi catatan


def begin_rate_limit_tracking() -> dict:
    """Mulai penghitung 429 untuk job ini (diwarisi semua task anak)."""
    counter: dict = {}
    _RL_JOB.set(counter)
    return counter


def _count_openalex_call() -> None:
    """Hitung panggilan OpenAlex per job (untuk memantau pemakaian kuota harian)."""
    counter = _RL_JOB.get()
    if counter is not None:
        counter["_oa_calls"] = counter.get("_oa_calls", 0) + 1


def _rate_limited_total() -> int:
    counter = _RL_JOB.get() or {}
    return sum(v for k, v in counter.items() if not k.startswith("_"))


def _is_daily_budget(r: httpx.Response) -> bool:
    try:
        return (r.json() or {}).get("reason") == "daily_budget"
    except Exception:  # noqa: BLE001
        return False


def _retry_after_of(r: httpx.Response) -> float | None:
    try:
        return float((r.json() or {}).get("retryAfter"))
    except Exception:  # noqa: BLE001
        return None


def _provider_name(url: str) -> str:
    host = (urlparse(url).hostname or "").lower()
    for name in _RL_NAMES[:-1]:
        if name in host:
            return name
    return "other"


def _record_rate_limit(url: str) -> None:
    name = _provider_name(url)
    counter = _RL_JOB.get()
    if counter is not None:
        counter[name] = counter.get(name, 0) + 1
    try:
        r = redis_client()
        key = f"online:ratelimit:{datetime.now(timezone.utc):%Y-%m-%d}:{name}"
        n = r.incr(key)
        if n == 1:
            r.expire(key, 3 * 24 * 3600)
        if n in (1, 100, 1000, 10000):
            _log.warning("Batas-laju (429) dari %s: %d kali hari ini", name, n)
    except Exception:  # noqa: BLE001, S110
        pass


# ── Pemutus-sirkuit kuota harian OpenAlex ────────────────────────────────────
# Kuota gratis OpenAlex ($1/hari, ±1.000 pencarian) bisa habis. Setelah habis,
# setiap panggilan pasti 429 sampai reset (tengah malam UTC) — jadi berhenti
# memanggil (hemat waktu job) dan tandai agar laporan memberi tahu pengguna.
_OA_BREAKER_KEY = "online:openalex:budget_exhausted"
BUDGET_FLAG = "_budget_exhausted"


def _openalex_budget_exhausted() -> bool:
    try:
        return bool(redis_client().get(_OA_BREAKER_KEY))
    except Exception:  # noqa: BLE001
        return False


def _trip_openalex_breaker(retry_after: float | int | None) -> None:
    ttl = int(min(max(float(retry_after or 3600), 60), 86400))
    try:
        redis_client().set(_OA_BREAKER_KEY, "1", ex=ttl)
        _log.warning("Kuota harian OpenAlex habis; panggilan dihentikan %d detik", ttl)
    except Exception:  # noqa: BLE001, S110
        pass


def _mark_budget_exhausted() -> None:
    counter = _RL_JOB.get()
    if counter is not None:
        counter[BUDGET_FLAG] = True


def rate_limit_usage() -> dict:
    """Jumlah 429 per penyedia hari ini (UTC) untuk pemantauan."""
    day = f"{datetime.now(timezone.utc):%Y-%m-%d}"
    out: dict = {"day": day, "hits": {}, "openalex_budget_exhausted": False}
    try:
        r = redis_client()
        out["openalex_budget_exhausted"] = bool(r.get(_OA_BREAKER_KEY))
        for name in _RL_NAMES:
            n = int(r.get(f"online:ratelimit:{day}:{name}") or 0)
            if n:
                out["hits"][name] = n
    except Exception:  # noqa: BLE001
        out["error"] = "redis tidak tersedia"
    return out


async def _get_json(client: httpx.AsyncClient, url: str, params: dict, headers: dict | None = None):
    """GET dengan satu kali percobaan ulang untuk menahan kegagalan sesaat.

    Penanganan batas-laju: pada HTTP 429, jangan buang waktu mencoba ulang
    secara membabi-buta (akan 429 lagi). Hormati header `Retry-After` hanya
    bila nilainya kecil (<=2 dtk); selebihnya menyerah anggun → hasil kosong.
    """
    is_openalex = "openalex.org" in url
    if is_openalex and not settings.openalex_enabled:
        return None
    if is_openalex and _openalex_budget_exhausted():
        _mark_budget_exhausted()
        return None
    for attempt in range(2):
        try:
            if is_openalex:
                _count_openalex_call()
            r = await client.get(url, params=params, headers=headers)
            if r.status_code == 429:
                _record_rate_limit(url)
                if is_openalex and _is_daily_budget(r):
                    _trip_openalex_breaker(_retry_after_of(r))
                    _mark_budget_exhausted()
                    return None
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


def _strip_html(html: str) -> str:
    """Bersihkan HTML landing-page penerbit menjadi teks terbaca.

    Buang komentar, blok script/style, lalu SELURUH tag (termasuk `<!doctype>`
    dan `<html ...>` beratribut panjang yang lolos `_TAG_RE`). Khusus HTML
    penerbit; isi dokumen tetap memakai `_clean`/`_TAG_RE` yang konservatif.
    """
    html = _HTML_COMMENT_RE.sub(" ", html or "")
    html = _HTML_SCRIPT_RE.sub(" ", html)
    return _WS_RE.sub(" ", _HTML_TAG_RE.sub(" ", html)).strip()


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


_CRAWL4AI_SEM: asyncio.Semaphore | None = None


def _crawl4ai_sem() -> asyncio.Semaphore:
    global _CRAWL4AI_SEM
    if _CRAWL4AI_SEM is None:
        _CRAWL4AI_SEM = asyncio.Semaphore(max(1, settings.crawl4ai_concurrency))
    return _CRAWL4AI_SEM


def _ft_fetch_sem() -> asyncio.Semaphore:
    global _FT_FETCH_SEM
    if _FT_FETCH_SEM is None:
        _FT_FETCH_SEM = asyncio.Semaphore(max(1, _FULLTEXT_FETCH_CONC))
    return _FT_FETCH_SEM


async def _crawl4ai_markdown(client: httpx.AsyncClient, url: str) -> str:
    """Ambil teks artikel BERSIH dari URL HTML via Crawl4AI lokal.

    Jauh lebih bersih dari penjungkiran tag mentah (membuang nav/menu/iklan,
    merender JS), jadi perbandingan plagiarisme lebih presisi & tak "ngawur".
    Lambat (merender JS) → konkurensi dibatasi & timeout pendek agar tak
    melewati anggaran waktu cek. Gagal-aman: "" bila mati/menolak/timeout.
    """
    if not settings.crawl4ai_enabled or not settings.crawl4ai_url:
        return ""
    base = settings.crawl4ai_url.rstrip("/")
    headers = {"Content-Type": "application/json"}
    if settings.crawl4ai_token:
        headers["Authorization"] = f"Bearer {settings.crawl4ai_token}"
    try:
        async with _crawl4ai_sem():
            resp = await client.post(
                f"{base}/md",
                json={"url": url},
                headers=headers,
                timeout=httpx.Timeout(float(settings.crawl4ai_timeout), connect=6.0),
            )
        if resp.status_code != 200:
            return ""
        data = resp.json()
    except Exception:  # noqa: BLE001
        return ""
    md = data.get("markdown")
    if isinstance(md, dict):  # beberapa versi mengembalikan objek
        md = md.get("raw_markdown") or md.get("fit_markdown") or ""
    if not md and isinstance(data.get("result"), dict):
        md = data["result"].get("markdown") or ""
    return _clean(md or "")


# Meta Highwire/Google-Scholar `citation_pdf_url` menunjuk PDF artikel ASLI.
# Dipakai hampir semua OJS (mis. Jurnal RESTI) & banyak penerbit. Tanpa ini,
# fetcher hanya mengambil HALAMAN LANDING (judul+abstrak+navigasi) dan salah
# mengira itu "teks penuh" → cakupan pencocokan anjlok (mis. paper SENDIRI
# hanya 6.8% padahal ~semua katanya ada di PDF resmi).
_CIT_PDF_RE = re.compile(
    r"<meta[^>]+?name=[\"']citation_pdf_url[\"'][^>]+?content=[\"']([^\"']+)[\"']",
    re.I,
)
_CIT_PDF_RE2 = re.compile(
    r"<meta[^>]+?content=[\"']([^\"']+)[\"'][^>]+?name=[\"']citation_pdf_url[\"']",
    re.I,
)
_OJS_DL_RE = re.compile(
    r"href=[\"']([^\"']*/article/download/[^\"']+)[\"']", re.I
)
# IIETA & banyak penerbit berbasis Drupal menautkan PDF artikel lewat pola
# `/download/file/fid/<id>` (TANPA meta citation_pdf_url & bukan galley OJS).
# Tanpa pola ini, fetcher hanya mengambil halaman landing (judul+abstrak+daftar
# referensi) → paper SENDIRI pun skornya <1% padahal seluruh isinya ada di PDF.
_FID_DL_RE = re.compile(
    r"href=[\"']([^\"']*/download/file/fid/\d+[^\"']*)[\"']", re.I
)
# Fallback generik: tautan yang jelas menuju berkas PDF. Tautan "daftar
# sitasi/citation list" DIKECUALIKAN agar tak salah ambil PDF non-artikel.
_PDF_HREF_RE = re.compile(
    r"href=[\"']([^\"']+\.pdf(?:\?[^\"']*)?)[\"']", re.I
)
_PDF_NOISE_RE = re.compile(r"citation|cite|list|cover|flyer|template", re.I)


def _pdf_url_from_html(html: str, base_url: str) -> str | None:
    """URL PDF artikel asli yang diiklankan halaman landing (bila ada).

    Prioritas: meta `citation_pdf_url` (standar), pola unduh galley OJS, pola
    unduh berbasis Drupal (`/download/file/fid/`, mis. IIETA), lalu fallback
    tautan `.pdf` generik (dengan menyaring berkas non-artikel seperti daftar
    sitasi/template).
    """
    if not html or len(html) > 4_000_000:
        html = (html or "")[:4_000_000]
    for rx in (_CIT_PDF_RE, _CIT_PDF_RE2):
        m = rx.search(html)
        if m:
            return urljoin(base_url, _html_unescape(m.group(1)).strip())
    for rx in (_OJS_DL_RE, _FID_DL_RE):
        m = rx.search(html)
        if m:
            return urljoin(base_url, _html_unescape(m.group(1)).strip())
    for m in _PDF_HREF_RE.finditer(html):
        href = m.group(1)
        if _PDF_NOISE_RE.search(href):
            continue
        return urljoin(base_url, _html_unescape(href).strip())
    return None


async def _fetch_fulltext(
    client: httpx.AsyncClient, url: str | None, _depth: int = 0
) -> str:
    """Ambil teks-PENUH open-access (PDF/HTML) secara ephemeral.

    Tidak menyimpan apa pun ke disk/DB — byte diproses di memori lalu dibuang.
    Dibatasi ukuran (`online_fulltext_max_bytes`) agar tidak mengunduh berkas
    raksasa. Mengembalikan "" bila gagal/terlalu besar/bukan dokumen teks.
    """
    if not url or not settings.online_fulltext_enabled:
        return ""
    cap = settings.online_fulltext_max_bytes
    final_url = url
    try:
        async with client.stream(
            "GET", url, headers={"User-Agent": "Mozilla/5.0 (ICALORA-LABS)"}
        ) as resp:
            if resp.status_code != 200:
                # Halaman yang menolak unduh langsung (403/JS-wall) sering masih
                # bisa dirender Crawl4AI — coba sebagai cadangan terakhir.
                return await _crawl4ai_markdown(client, url)
            final_url = str(resp.url) or url
            ctype = (resp.headers.get("content-type") or "").lower()
            buf = bytearray()
            async for chunk in resp.aiter_bytes():
                buf.extend(chunk)
                if len(buf) > cap:
                    return ""
        data = bytes(buf)
    except Exception:  # noqa: BLE001
        return await _crawl4ai_markdown(client, url)
    if "html" in ctype and b"%PDF" not in data[:1024]:
        try:
            html = data.decode("utf-8", "ignore")
        except Exception:  # noqa: BLE001
            html = ""
        # PRIORITAS: ikuti PDF artikel asli yang diiklankan halaman landing
        # (citation_pdf_url / galley OJS / unduhan Drupal). Tanpa ini, landing
        # page sering lolos ambang `min_strip_chars` dan DISALAHARTIKAN sebagai
        # teks penuh. Bila PDF artikel berhasil diambil dan isinya SUBSTANSIAL,
        # UTAMAKAN PDF itu: halaman landing kerap lebih PANJANG karena memuat
        # navigasi/daftar referensi/artikel lain (noise) sehingga pembanding
        # panjang keliru memilih landing alih-alih teks artikel sebenarnya.
        pdf_text = ""
        if _depth < 1:
            pdf_url = _pdf_url_from_html(html, final_url)
            if pdf_url and pdf_url != url and pdf_url != final_url:
                pdf_text = await _fetch_fulltext(client, pdf_url, _depth + 1)
        # Jalur CEPAT: penjungkiran tag murah. Mayoritas halaman penerbit/arXiv
        # memuat teks artikel di HTML mentah → tak perlu Crawl4AI yang lambat.
        stripped = _strip_html(html)
        if pdf_text and len(pdf_text) >= settings.crawl4ai_min_strip_chars:
            best_html = pdf_text
        else:
            best_html = pdf_text if len(pdf_text) > len(stripped) else stripped
        if len(best_html) >= settings.crawl4ai_min_strip_chars:
            return best_html
        clean = await _crawl4ai_markdown(client, url)
        return clean if len(clean) > len(best_html) else best_html
    try:
        text = await asyncio.to_thread(extract_text, "oa.pdf", data)
    except Exception:  # noqa: BLE001
        return ""
    return _clean(text)



async def _fetch_fulltext_resilient(client: httpx.AsyncClient, url: str | None) -> str:
    """Seperti `_fetch_fulltext` tetapi ulangi bila hasil kosong.

    Unduhan PDF teks-penuh (mis. tautan unduh OJS) sesekali gagal transient
    (koneksi putus/timeout di sisi penerbit), menyebabkan kandidat identitas
    jatuh ke abstrak saja → cakupan pencocokan anjlok (mis. 55%→23%). Retry
    singkat memulihkan kegagalan sesaat TANPA menambah beban pada kasus normal
    (hanya berulang saat hasil kosong).
    """
    attempts = max(1, settings.online_fulltext_fetch_attempts)
    text = ""
    for i in range(attempts):
        text = await _fetch_fulltext(client, url)
        if text:
            return text
        if i + 1 < attempts:
            await asyncio.sleep(0.5 * (i + 1))
    return text


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


def _title_in_doc_score(c: dict, doc: str) -> float:
    """Kandidat TANPA abstrak (paper baru, abstrak belum terindeks) tak bisa dinilai
    lewat abstrak. Ukur seberapa banyak kata isi JUDUL kandidat termuat di dokumen:
    judul paper yang menjadi dokumen ini hampir selalu termuat utuh. Hanya sebagai
    gerbang pengunduhan teks penuh — skor akhir tetap ditentukan pencocokan
    baris-per-baris."""
    if len(_WORD_RE.findall(c.get("_fulltext") or "")) >= 40:
        return 0.0
    tw = {w.lower() for w in re.findall(r"[A-Za-z]{4,}", c.get("title") or "")}
    tw -= _GENERIC_TERMS
    if len(tw) < 5:
        return 0.0
    dw = {w.lower() for w in re.findall(r"[A-Za-z]{4,}", doc)}
    return len(tw & dw) / len(tw)


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

    def _title_in_doc(c: dict) -> float:
        return _title_in_doc_score(c, doc)

    def _rank(c: dict) -> float:
        base = 1.0 if (c.get("doi") or "").lower() in own_dois else 0.0
        ft = min(int(c.get("_ft_hits", 0)), 4) * 0.25
        return base + _title_sim(c) + _abs_containment(c) + _title_in_doc(c) + ft

    def _passes_gate(c: dict) -> bool:
        return (
            (c.get("doi") or "").lower() in own_dois
            or _title_sim(c) >= 0.6
            or _abs_containment(c) >= 0.5
            or _title_in_doc(c) >= 0.9
            or int(c.get("_ft_hits", 0)) >= _FT_MIN_HITS
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

    # Sertakan juga kandidat ber-DOI tanpa URL: teks penuhnya mungkin sudah
    # tersimpan di cache dari pemeriksaan sebelumnya.
    targets = [
        c for c in promising
        if c.get("_oa_url") or c.get("url") or c.get("doi")
    ]
    if not targets:
        return

    async def _best_fulltext(c: dict) -> str:
        # DETERMINISME: jika teks penuh sumber ini sudah pernah berhasil
        # diunduh, pakai ulang dari cache (per-DOI/URL) alih-alih mengunduh
        # ulang. Mencegah skor berayun saat server penerbit lambat/putus.
        ckey = online_cache.cache_key(c.get("doi"), c.get("_oa_url") or c.get("url"))
        cached = await asyncio.to_thread(online_cache.get, ckey)
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
            return cached or ""
        fetched = await asyncio.gather(
            *(_fetch_fulltext_resilient(client, u) for u in urls),
            return_exceptions=True,
        )
        best = ""
        for t in fetched:
            if isinstance(t, str) and len(t) > len(best):
                best = t
        # Simpan hasil unduhan yang lebih baik ke cache; bila unduhan kali ini
        # lebih pendek dari yang tersimpan, pakai yang tersimpan (lebih lengkap).
        if best:
            await asyncio.to_thread(online_cache.put, ckey, best)
        if cached and len(cached) > len(best):
            return cached
        return best

    async def _guarded_fulltext(c: dict) -> str:
        # Batasi unduhan teks-penuh serempak lewat semaphore bersama.
        async with _ft_fetch_sem():
            return await _best_fulltext(c)

    results = await asyncio.gather(
        *(_guarded_fulltext(c) for c in targets),
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


def _oa_params(params: dict) -> dict:
    """Parameter standar OpenAlex: mailto (polite pool) + api_key bila ada."""
    out = {**params, "mailto": _MAILTO}
    if settings.openalex_api_key:
        out["api_key"] = settings.openalex_api_key
    return out


async def _q_openalex(client: httpx.AsyncClient, sentence: str) -> list[dict]:
    r = await _get_json(
        client,
        "https://api.openalex.org/works",
        _oa_params({"search": sentence[:250], "per_page": _PER_PROVIDER}),
    )
    if r is None:
        return []
    return _openalex_items(r.json())


def _openalex_items(data: dict) -> list[dict]:
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


_FT_MAX_PHRASES = 6
_FT_PHRASE_WORDS = 9
_FT_MIN_HITS = 2  # kandidat dikembalikan >= 2 frasa berbeda = pembagi teks nyata
_FT_SENT_RE = re.compile(r"(?<=[.!?])\s+(?=[A-Z])")
_FT_REFS_RE = re.compile(
    r"(?im)^\s*(?:\d+\.?\s*)?(?:references|daftar\s+pustaka|bibliography)\s*$"
)


def _fulltext_phrases(doc: str, n: int = _FT_MAX_PHRASES) -> list[str]:
    """Frasa 9-kata dari kalimat isi dokumen (tersebar merata, tanpa daftar pustaka).

    Dipakai untuk pencarian TEKS PENUH OpenAlex (`fulltext.search`) — satu-satunya
    cara menemukan paper terbit dari dokumen yang diunggah tanpa judul/abstrak
    (mulai dari Pendahuluan), termasuk jurnal lokal yang abstraknya tak informatif.
    """
    text = doc or ""
    refs = list(_FT_REFS_RE.finditer(text))
    if refs and refs[-1].start() > len(text) * 0.4:
        text = text[: refs[-1].start()]
    flat = re.sub(r"\s+", " ", text)
    eligible: list[str] = []
    for sent in _FT_SENT_RE.split(flat):
        if not 80 <= len(sent) <= 240:
            continue
        low = sent.lower()
        if "http" in low or "doi" in low or sum(c.isdigit() for c in sent) > 6:
            continue
        words = re.findall(r"[A-Za-z\u00C0-\u024F]{3,}", sent)
        if len(words) < _FT_PHRASE_WORDS + 3:
            continue
        eligible.append(" ".join(words[:_FT_PHRASE_WORDS]))
    if not eligible:
        return []
    step = max(1, len(eligible) // n)
    out: list[str] = []
    for phrase in eligible[::step]:
        if phrase not in out:
            out.append(phrase)
        if len(out) >= n:
            break
    return out


async def _q_openalex_fulltext(client: httpx.AsyncClient, phrase: str) -> list[dict]:
    """Cari frasa di TEKS PENUH karya OpenAlex (filter `fulltext.search`)."""
    r = await _get_json(
        client,
        "https://api.openalex.org/works",
        _oa_params({"filter": f'fulltext.search:"{phrase}"', "per_page": 5}),
    )
    if r is None:
        return []
    return _openalex_items(r.json())


async def _q_fulltext_phrases(client: httpx.AsyncClient, doc: str) -> list[dict]:
    """Kandidat yang muncul untuk >= _FT_MIN_HITS frasa isi dokumen berbeda.

    Menandai `_ft_hits` (jumlah frasa yang cocok) agar gerbang pengunduhan
    teks-penuh dapat menjadikannya kandidat identitas tanpa perlu judul/abstrak.
    """
    phrases = _fulltext_phrases(doc)
    if not phrases:
        return []
    sem = asyncio.Semaphore(3)

    async def _one(ph: str) -> list[dict]:
        async with sem:
            try:
                return await _q_openalex_fulltext(client, ph)
            except Exception:  # noqa: BLE001
                return []

    results = await asyncio.gather(*(_one(p) for p in phrases))
    merged: dict[str, dict] = {}
    for items in results:
        seen_here: set[str] = set()
        for it in items:
            key = (it.get("doi") or it.get("title") or "").lower().strip()
            if not key or key in seen_here:
                continue
            seen_here.add(key)
            cur = merged.setdefault(key, it)
            cur["_ft_hits"] = cur.get("_ft_hits", 0) + 1
    return [c for c in merged.values() if c.get("_ft_hits", 0) >= _FT_MIN_HITS]


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


async def _q_searxng(client: httpx.AsyncClient, sentence: str) -> list[dict]:
    """Web search umum via SearXNG LOKAL (gratis, keluar lewat Tor → anonim).

    Pengganti/pendamping Tavily/Brave TANPA kuota & tanpa risiko tagihan.
    Memakai `categories=science` agar menjangkau sumber ilmiah (Google Scholar
    dsb.) yang lolos dari provider API akademik. Hasil (judul/URL/snippet) tetap
    ephemeral; teks penuh diambil terpisah via Crawl4AI pada tahap enrich.
    Gagal-aman: bila SearXNG mati, kembalikan daftar kosong (tak menggagalkan
    pengecekan).
    """
    if not settings.online_websearch_enabled or not settings.searxng_enabled:
        return []
    base = settings.searxng_url.rstrip("/")
    r = await _get_json(
        client,
        f"{base}/search",
        {
            "q": sentence[:380],
            "format": "json",
            "categories": "science",
            "language": "en",
        },
    )
    if r is None:
        return []
    try:
        data = r.json()
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
                "source": "SearXNG",
                "url": url,
                "_fulltext": content or title,
                "_oa_url": oa_url,
            }
        )
    return out


def _websearch_provider():
    """Pilih penyedia web-search aktif. SearXNG (lokal, GRATIS, tanpa kuota &
    keluar lewat Tor) diutamakan; lalu Tavily (tanpa kartu → bebas risiko
    tagihan), lalu Brave. None bila tak ada yang aktif."""
    if not settings.online_websearch_enabled:
        return None
    if settings.searxng_enabled and settings.searxng_url:
        return _q_searxng
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

    plan = [
        (fn, conc, _slot(weight, cap))
        for fn, conc, weight, cap in _PROVIDER_PLAN
        if fn is not _q_openalex
        or (settings.openalex_enabled and settings.openalex_sentence_search)
    ]
    if settings.core_enabled and settings.core_api_key:
        plan.append((_q_core, 4, _slot(1.00, _SENT_CAP)))
    return plan


def _active_providers() -> list:
    return [fn for fn, _c, _s in _provider_plan()]


async def _q_openalex_doi(client: httpx.AsyncClient, doi: str) -> dict | None:
    r = await _get_json(client, f"https://api.openalex.org/works/doi:{doi}", _oa_params({}))
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


_KEYWORDS_RE = re.compile(r"(?im)^\s*(?:keywords?|kata\s+kunci)\s*[:\-–]\s*(.+)$")
_ABSTRACT_HEAD_RE = re.compile(r"(?im)^\s*(?:abstract|abstrak)\b[\s:.\-–]*")
_SENT_SPLIT_RE = re.compile(r"(?<=[.!?])\s+(?=[A-Z])")


_GENERIC_TERMS = frozenset(
    "about above after between because during under using study studies results result "
    "which these those their there where while through paper research analysis based "
    "method methods approach conditions condition measured evaluated evaluates indicate "
    "indicates provides proposed present presents found shows showed different several "
    "should within without major higher lower under over from this that with have been "
    "were what when also than more most both each other such into onto only very yang "
    "dengan untuk dalam pada dari adalah penelitian hasil metode figure figures table "
    "tables equation equations value values shown shows could would increase decrease "
    "number total effect effects often however therefore thus data model models "
    "will used same then they them high some like make made many much must well "
    "case cases time part parts well also into over".split()
)
_HYPHEN_TERM_RE = re.compile(r"\b[A-Za-z]{3,}-[A-Za-z]{3,}\b")


_REFS_HEAD_RE = re.compile(
    r"(?im)^\s*(?:\d+\.?\s*)?(?:references|daftar\s+pustaka|bibliography)\s*$"
)


def _term_query_sets(body: str) -> list[str]:
    words = [w.lower() for w in re.findall(r"[A-Za-z]{4,}", body)]
    freq: dict[str, int] = {}
    for w in words:
        if w not in _GENERIC_TERMS:
            freq[w] = freq.get(w, 0) + 1
    top = [w for w, _ in sorted(freq.items(), key=lambda kv: (-kv[1], kv[0]))[:6]]
    compounds: dict[str, int] = {}
    for h in _HYPHEN_TERM_RE.findall(body):
        compounds[h.lower()] = compounds.get(h.lower(), 0) + 1
    comp = [c for c, _ in sorted(compounds.items(), key=lambda kv: (-kv[1], kv[0]))[:1]]
    out: list[str] = []
    if len(top) >= 3:
        out.append(" ".join(top[:4]))
        if comp:
            out.append(" ".join(comp + top[:2]))
        # Pencarian OpenAlex bersifat AND atas judul: satu kata ekstra yang
        # tak ada di judul membuat paper hilang. Pasangan 2 kata lebih tahan.
        lead = comp or top[:1]
        for t in top[: 4 if comp else 3]:
            if t != lead[0]:
                out.append(f"{lead[0]} {t}")
        if not comp:
            out.append(f"{top[1]} {top[2]}")
    return out


def _distinct_term_queries(doc: str) -> list[str]:
    """Query SINGKAT berisi istilah paling khas dokumen.

    OpenAlex/Crossref menilai relevansi kata-kunci terhadap JUDUL (abstrak
    sering kosong untuk paper baru). Kalimat panjang mengencerkan istilah
    khas; beberapa kata paling sering muncul (mis. "porous-net scour bridge
    pier") justru menempatkan paper terbit di peringkat teratas.

    Dua sudut pandang: (1) awal dokumen (abstrak) dan (2) SELURUH isi tanpa
    daftar pustaka. Yang kedua penting untuk makalah yang diunggah mulai dari
    Pendahuluan: Pendahuluan hanya memuat istilah umum, sedangkan istilah
    khas penelitian (mis. nama metode/perangkat) baru dominan di Metode/Hasil.
    """
    doc = (doc or "").strip()
    head = doc[:4000]
    m = _ABSTRACT_HEAD_RE.search(head)
    queries = _term_query_sets(head[m.end():] if m else head)
    refs = list(_REFS_HEAD_RE.finditer(doc))
    full = doc[: refs[-1].start()] if refs and refs[-1].start() > len(doc) * 0.4 else doc
    for q in _term_query_sets(full):
        if q not in queries:
            queries.append(q)
    return queries[:12]


def _abstract_queries(doc: str) -> list[str]:
    """Query cadangan untuk menemukan paper terbit saat JUDUL tak ada.

    Banyak pengguna menghapus header/judul/penulis sebelum mengunggah, sehingga
    dokumen dimulai dari "Abstract". Judul tak bisa diekstrak (dan nama berkas
    tak informatif), padahal paper tersebut terindeks. Mesin cari OpenAlex/
    Crossref mencocokkan judul+abstrak, jadi kalimat awal abstrak dan baris
    Keywords efektif sebagai kueri identitas.
    """
    head = (doc or "").strip()[:6000]
    queries: list[str] = []
    kw = _KEYWORDS_RE.search(head)
    if kw:
        words = _clean(kw.group(1))
        if len(_WORD_RE.findall(words)) >= 3:
            queries.append(words[:200])
    m = _ABSTRACT_HEAD_RE.search(head)
    body = head[m.end():] if m else head
    body = _clean(body)
    sents = [s for s in _SENT_SPLIT_RE.split(body) if len(_WORD_RE.findall(s)) >= 6]
    for i in range(min(2, len(sents))):
        queries.append(" ".join(sents[i : i + 2])[:300])
    return queries


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


_IDENTITY_SEM: asyncio.Semaphore | None = None


async def _q_title_throttled(client: httpx.AsyncClient, title: str) -> list[dict]:
    """`_q_title` dengan batas konkurensi BERSAMA antar-job + satu retry.

    Banyak user mengunggah serentak → belasan query identitas per job memicu
    429 (rate-limit Crossref/OpenAlex) dan paper terbit tak ditemukan. Semaphore
    tingkat-proses meratakan beban; hasil kosong dicoba ulang sekali setelah jeda.
    """
    global _IDENTITY_SEM
    if _IDENTITY_SEM is None:
        _IDENTITY_SEM = asyncio.Semaphore(4)
    async with _IDENTITY_SEM:
        before = _rate_limited_total()
        res = await _q_title(client, title)
        # Retry hanya bila hasil kosong AKIBAT 429; kosong yang sah tak diulang
        # (tiap ulang memakan kuota OpenAlex).
        if not res and _rate_limited_total() > before:
            await asyncio.sleep(2.0)
            res = await _q_title(client, title)
        return res


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
    queries.update(_abstract_queries(doc))
    for q in queries:
        if q:
            tasks.append(_q_title_throttled(client, q))
    tasks.append(_q_fulltext_phrases(client, doc))
    out = _flatten(await asyncio.gather(*tasks, return_exceptions=True))
    # Tahap 2 (hemat kuota): query istilah-khas (±12 panggilan) hanya dijalankan bila
    # tahap 1 belum menemukan kandidat identitas yang meyakinkan.
    if not _has_identity_hit(out, doc, hint):
        extra = [q for q in _distinct_term_queries(doc) if q not in queries]
        out.extend(
            _flatten(
                await asyncio.gather(
                    *(_q_title_throttled(client, q) for q in extra), return_exceptions=True
                )
            )
        )
    return out


def _flatten(results: list) -> list[dict]:
    out: list[dict] = []
    for res in results:
        if isinstance(res, dict):
            out.append(res)
        elif isinstance(res, list):
            out.extend(res)
    return out


def _has_identity_hit(cands: list[dict], doc: str, title_hint: str = "") -> bool:
    """Ada kandidat yang MEYAKINKAN sebagai paper terbit dokumen ini?

    Hanya sinyal kuat yang dihitung: DOI sendiri, muncul untuk >= 2 frasa isi berbeda
    (pencarian teks penuh), atau kemiripan judul tinggi. Sinyal "kata judul termuat di
    dokumen" SENGAJA tidak dipakai di sini: paper LAIN yang kata judulnya kebetulan ada
    di naskah akan dianggap ketemu dan tahap 2 dilewati, padahal paper aslinya belum
    ditemukan (regresi nyata pada uji validasi). Sinyal itu hanya untuk gerbang unduhan.
    """
    own = {d.lower() for d in _extract_own_dois(doc)}
    titles = [t for t in (_extract_title(doc), _clean(title_hint or "")) if t]
    for c in cands:
        if (c.get("doi") or "").lower() in own:
            return True
        if int(c.get("_ft_hits", 0)) >= _FT_MIN_HITS:
            return True
        ct = c.get("title") or ""
        if any(_title_jaccard(ct, t) >= 0.6 for t in titles):
            return True
    return False


async def _gather_candidates(
    doc: str, title_hint: str = "", skip_identity: bool = False
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
        # Dilewati bila pass identitas SUDAH dijalankan sebelumnya (hemat kuota:
        # hasilnya digabung terpisah oleh pemanggil).
        pub_task = None if skip_identity else asyncio.create_task(
            _resolve_publication(doc=doc, client=client, title_hint=title_hint)
        )
        results = await asyncio.gather(*tasks, return_exceptions=True)
        pub_results = await pub_task if pub_task is not None else []
        # Fase VERIFIER web search: HANYA kalimat paling khas. SearXNG lokal
        # (gratis, tanpa kuota) dijalankan PARALEL (cepat); Tavily/Brave (API
        # berbayar/berkuota) tetap serial dengan jeda kecil menghormati batas
        # laju tier gratis. Nonaktif otomatis bila tak ada penyedia aktif.
        web_results: list = []
        web_provider = _websearch_provider()
        if web_provider is _q_searxng:
            wsem = asyncio.Semaphore(6)

            async def _run_web(sentence):
                async with wsem:
                    try:
                        return await web_provider(client, sentence)
                    except Exception:  # noqa: BLE001
                        return []

            web_results = await asyncio.gather(
                *(_run_web(s) for s in sentences[: settings.online_websearch_sentences])
            )
        elif web_provider is not None:
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
                if cand.get("_ft_hits"):
                    seen[key]["_ft_hits"] = max(
                        int(seen[key].get("_ft_hits", 0)), int(cand["_ft_hits"])
                    )
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


async def online_candidates(
    doc: str, title_hint: str = "", skip_identity: bool = False
) -> tuple[list[dict], dict]:
    """Kumpulkan kandidat sumber daring (tanpa-unduh) untuk digabungkan ke
    pemeriksaan plagiarisme utama. Kembalikan (kandidat, hits-per-penyedia).
    Aman dipanggil opsional: galat jaringan menghasilkan daftar kosong.
    `title_hint` opsional (mis. nama berkas) membantu menemukan paper terbit.
    """
    doc = (doc or "").strip()
    if not doc or not _active_providers():
        return [], {}
    try:
        candidates, _sentences, provider_hits = await _gather_candidates(
            doc, title_hint, skip_identity
        )
    except Exception:  # noqa: BLE001
        return [], {}
    return candidates, provider_hits


def _merge_dup(seen: dict[str, dict], key: str, cand: dict) -> None:
    """Gabung kandidat duplikat: pertahankan teks terpanjang + `_ft_hits` tertinggi."""
    cur = seen.get(key)
    if cur is None:
        seen[key] = cand
        return
    hits = max(int(cur.get("_ft_hits", 0)), int(cand.get("_ft_hits", 0)))
    if len(cand.get("_fulltext") or "") > len(cur.get("_fulltext") or ""):
        if not cand.get("_oa_url") and cur.get("_oa_url"):
            cand["_oa_url"] = cur["_oa_url"]
        seen[key] = cur = cand
    if hits:
        cur["_ft_hits"] = hits


async def identity_candidates(doc: str, title_hint: str = "") -> list[dict]:
    """Pass RINGAN & CEPAT: temukan paper terbit yang MERUPAKAN dokumen ini
    (via judul/DOI sendiri) lalu perkaya dengan TEKS PENUH open-access.

    Dirancang berjalan PARALEL dengan `online_candidates` (pencarian luas
    per-kalimat yang lambat). Karena hanya beberapa permintaan + unduh 1–2 PDF,
    pass ini selesai jauh di dalam anggaran dan MENJAMIN paper terbit milik user
    tetap tercocok meskipun fase pencarian luas kehabisan waktu/dibatalkan.
    """
    doc = (doc or "").strip()
    if not doc or not _active_providers():
        return []
    try:
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(45.0, connect=10.0),
            headers=_UA,
            follow_redirects=True,
        ) as client:
            raw = await _resolve_publication(doc=doc, client=client, title_hint=title_hint)
            seen: dict[str, dict] = {}
            for cand in raw:
                if not cand.get("title"):
                    continue
                key = (cand.get("doi") or cand["title"]).lower().strip()
                cand["doc_id"] = None
                _merge_dup(seen, key, cand)
            cands = list(seen.values())
            if settings.online_fulltext_enabled:
                await _enrich_fulltext(client, cands, doc, title_hint)
            # Hanya pertahankan kandidat yang benar-benar punya teks untuk dicocokkan.
            return [c for c in cands if c.get("_fulltext") and c.get("title")]
    except Exception:  # noqa: BLE001
        return []


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
