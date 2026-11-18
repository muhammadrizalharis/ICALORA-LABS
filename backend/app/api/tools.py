"""Endpoint fitur ringan Fase 1."""

import asyncio
import os
import re
import threading
import time
from collections import defaultdict, deque

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import Response
from pydantic import BaseModel, Field

from app.core.config import get_settings
from app.services import admin as admin_svc
from app.services.ai_detector import detect_ai
from app.services.ai_detector.report_pdf import build_ai_report_pdf
from app.services.auth import (
    get_history_item,
    get_tool_file_by_history,
    optional_user_from_request,
    record_history,
    save_tool_file,
)
from app.services.authorship import analyze_authorship
from app.services.citation import find_citations
from app.services.file_extract import MAX_UPLOAD_BYTES, extract_text
from app.services.grammar.report_pdf import build_grammar_report_pdf
from app.services.hidden_text import check_hidden_text
from app.services.jobs import complete_job, create_job, fail_job, get_job
from app.services.llm.tasks import (
    build_resume,
    chat,
    doc_chat,
    generate_toc,
    grade_essay,
    grammar_check,
    humanize,
    improve_document,
    paraphrase,
    reader_reactions,
    rewrite,
)
from app.services.plagiarism import check_plagiarism
from app.services.plagiarism.online import (
    identity_candidates,
    online_candidates,
    online_check,
)
from app.services.plagiarism.report_pdf import build_report_pdf
from app.services.publikasi import recommend_journals
from app.services.report import MAX_HTML_BYTES, render_pdf
from app.services.report.reports import (
    ai_detector_report_html,
    grammar_report_html,
    toc_report_html,
    transform_report_html,
)
from app.services.text_tools import analyze_text
from app.services.transkrip import (
    MAX_AUDIO_BYTES,
    is_supported,
    transcribe_audio,
)

router = APIRouter(prefix="/tools", tags=["tools"])

# Tidak ada batas fungsional untuk panjang teks. Angka ini hanya pagar
# keamanan agar server (dibagi 24/7) tidak kehabisan memori pada input
# ekstrem — setara buku/tesis sangat panjang (~340rb kata). Analisis semantik
# memakai embedding per-jendela, jadi seluruh isi dokumen tetap diperiksa.
MAX_CHARS = 2_000_000
# MIME peran untuk laporan overlay AI yang sudah dibangun & di-cache pada
# riwayat (dibedakan dari PDF asli "application/pdf"). Laporan dibangun sekali
# di latar belakang saat deteksi (bisa ~1 mnt) lalu disajikan seketika agar
# unduhan tidak melewati batas waktu proxy (Cloudflare 524).
AI_REPORT_MIME = "application/x-icalora-ai-report"
GRAMMAR_REPORT_MIME = "application/x-icalora-grammar-report"
# MIME laporan alat transformasi (parafrase/humanize/rewrite/perbaikan): laporan
# diff bersorotan (asli vs hasil) yang dibangun & di-cache saat job selesai.
TRANSFORM_REPORT_MIME = "application/x-icalora-transform-report"
# MIME laporan Daftar Isi Otomatis (struktur bab/sub-bab ber-jenjang).
TOC_REPORT_MIME = "application/x-icalora-toc-report"
# Batas waktu transkripsi (detik) agar tidak menahan worker pada berkas panjang.
TRANSCRIBE_TIMEOUT = int(os.environ.get("WHISPER_TIMEOUT", "900"))
settings = get_settings()


# Peta endpoint /tools/<suffix> -> slug fitur (untuk on/off oleh Super Admin).
_FEATURE_BY_PATH: dict[str, str] = {
    "word-count": "word-count",
    "extract-text": "extract-text",
    "grammar-check": "grammar-checker",
    "grammar-check-async": "grammar-checker",
    "grammar-check-file-async": "grammar-checker",
    "paraphrase": "paraphraser",
    "paraphrase-async": "paraphraser",
    "paraphrase-file-async": "paraphraser",
    "humanize": "humanizer",
    "humanize-async": "humanizer",
    "humanize-file-async": "humanizer",
    "rewrite": "ai-rewriter",
    "rewrite-async": "ai-rewriter",
    "rewrite-file-async": "ai-rewriter",
    "improve-async": "perbaikan-dokumen",
    "improve-file-async": "perbaikan-dokumen",
    "toc-async": "daftar-isi",
    "toc-file-async": "daftar-isi",
    "plagiarism": "plagiarism-checker",
    "plagiarism-online": "plagiarism-checker",
    "plagiarism-file": "plagiarism-checker",
    "plagiarism-async": "plagiarism-checker",
    "plagiarism-file-async": "plagiarism-checker",
    "chat": "ai-chat",
    "grade": "ai-grader",
    "reader-reactions": "reader-reactions",
    "resume": "resume-builder",
    "citations": "citation-finder",
    "ai-detect": "ai-detector",
    "ai-detect-file": "ai-detector",
    "ai-detect-file-async": "ai-detector",
    "authorship": "authorship",
    "toc": "toc-generator",
    "improve": "document-improver",
    "hidden-text": "hidden-text",
    "doc-chat": "doc-chat",
    "publikasi": "publikasi",
    "transcribe": "transcribe",
    "report-pdf": "report-pdf",
}


def _access_guard(request: Request) -> None:
    """Dependency router: tegakkan maintenance, blokir akun, dan on/off fitur.

    Super Admin dikecualikan dari semua pembatasan agar tetap bisa menguji.
    """
    user = optional_user_from_request(request)
    is_admin = bool(user and user.get("is_admin"))
    if is_admin:
        return
    if admin_svc.is_maintenance():
        raise HTTPException(
            status_code=503,
            detail="Situs sedang dalam pemeliharaan. Silakan coba lagi nanti.",
        )
    if user and not user.get("is_active", True):
        raise HTTPException(status_code=403, detail="Akun Anda dinonaktifkan.")
    suffix = request.url.path.rsplit("/", 1)[-1]
    slug = _FEATURE_BY_PATH.get(suffix)
    if slug and not admin_svc.feature_enabled(slug):
        raise HTTPException(
            status_code=403, detail="Fitur ini sedang dinonaktifkan oleh admin."
        )
    # --- Proteksi penyalahgunaan (hanya aktif bila di-ON-kan admin) ---
    if slug:
        _enforce_rate_limit(request, user)
        _enforce_token_cost(request, user, slug)


# Rate limiter in-memory sederhana (sliding window per identitas).
# Cukup untuk 1 proses; default OFF, hanya pagar anti-abuse bila di-ON-kan.
_RL_LOCK = threading.Lock()
_RL_HITS: dict[str, deque[float]] = defaultdict(deque)


def _client_identity(request: Request, user: dict | None) -> str:
    if user and user.get("id") is not None:
        return f"u:{user['id']}"
    xff = request.headers.get("x-forwarded-for", "")
    ip = xff.split(",")[0].strip() if xff else (
        request.client.host if request.client else "?"
    )
    return f"ip:{ip}"


def _enforce_rate_limit(request: Request, user: dict | None) -> None:
    if not admin_svc.rate_limit_enabled():
        return
    limit = admin_svc.rate_limit_per_min()
    key = _client_identity(request, user)
    now = time.monotonic()
    window = 60.0
    with _RL_LOCK:
        hits = _RL_HITS[key]
        while hits and now - hits[0] > window:
            hits.popleft()
        if len(hits) >= limit:
            retry = max(1, int(window - (now - hits[0])))
            raise HTTPException(
                status_code=429,
                detail=f"Terlalu banyak permintaan. Coba lagi dalam {retry} detik.",
                headers={"Retry-After": str(retry)},
            )
        hits.append(now)


def _enforce_token_cost(request: Request, user: dict | None, slug: str) -> None:
    if not admin_svc.token_enforcement_enabled():
        return
    if not user or user.get("id") is None:
        # Tanpa akun tidak bisa dipotong token; rate-limit sudah menjaga.
        return
    cost = admin_svc.tool_cost(slug)
    if cost <= 0:
        return
    if not admin_svc.charge_tokens(int(user["id"]), cost):
        raise HTTPException(
            status_code=402,
            detail=(
                "Saldo token Anda tidak mencukupi untuk menjalankan fitur ini. "
                "Hubungi admin untuk menambah saldo."
            ),
        )


router.dependencies.append(Depends(_access_guard))


class TextIn(BaseModel):
    text: str = Field(..., min_length=1)


class ParaphraseIn(TextIn):
    style: str = Field(default="standar")


class ExcludeIn(BaseModel):
    """Pengaturan Exclude pra-pengecekan (dikunci pada hasil)."""

    bibliography: bool = False
    quotes: bool = False
    min_source_percent: float = Field(default=0.0, ge=0.0, le=100.0)


class PlagiarismIn(TextIn):
    top_k: int = Field(default=30, ge=1, le=60)
    exclude: ExcludeIn | None = None
    title: str = Field(default="", max_length=300)  # judul dokumen dari user


class RewriteIn(TextIn):
    tone: str = Field(default="formal")


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatIn(BaseModel):
    messages: list[ChatMessage] = Field(..., min_length=1)
    system: str | None = Field(default=None)


class GradeIn(TextIn):
    rubric: str | None = Field(default=None)


class CitationIn(TextIn):
    top_k: int = Field(default=15, ge=1, le=40)


class ResumeIn(BaseModel):
    info: str = Field(..., min_length=1)
    target_role: str | None = Field(default=None)


class AuthorshipIn(TextIn):
    compare: str | None = Field(default=None)


class ImproveIn(TextIn):
    goal: str | None = Field(default=None)


class HiddenTextIn(TextIn):
    check_typos: bool = Field(default=True)


class DocChatIn(BaseModel):
    context: str = Field(..., min_length=1)
    messages: list[ChatMessage] = Field(..., min_length=1)


class PublikasiIn(TextIn):
    top_k: int = Field(default=15, ge=1, le=40)


def _guard(text: str) -> None:
    if len(text) > MAX_CHARS:
        raise HTTPException(
            status_code=413,
            detail=(
                f"Teks melebihi batas keamanan server ({MAX_CHARS:,} karakter). "
                "Pisahkan dokumen menjadi beberapa bagian."
            ),
        )


def _log(request: Request, tool: str, title: str, preview: str, result: dict) -> None:
    """Catat riwayat bila pengguna login (tidak memblokir bila gagal)."""
    try:
        user = optional_user_from_request(request)
        if user:
            record_history(user["id"], tool, title, preview, result)
    except Exception:  # noqa: BLE001, S110
        pass


@router.post("/word-count")
def word_count(body: TextIn, request: Request) -> dict:
    res = analyze_text(body.text)
    _log(request, "word-count", "Word Count", body.text[:200], res)
    return res


@router.post("/extract-text")
async def extract_text_ep(file: UploadFile = File(...)) -> dict:  # noqa: B008
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Berkas kosong.")
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"Berkas melebihi {MAX_UPLOAD_BYTES // (1024 * 1024)} MB.",
        )
    try:
        text = extract_text(file.filename or "", data)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    text = text.strip()
    if not text:
        raise HTTPException(
            status_code=422,
            detail="Tidak ada teks yang dapat diekstrak dari berkas.",
        )
    if len(text) > MAX_CHARS:
        text = text[:MAX_CHARS]
    return {"filename": file.filename, "text": text, "chars": len(text)}


@router.post("/grammar-check")
def grammar(body: TextIn, request: Request) -> dict:
    _guard(body.text)
    try:
        res = grammar_check(body.text)
        _log(request, "grammar-checker", "Grammar Check", body.text[:200], res)
        return res
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"LLM gagal: {exc}") from exc


def _store_grammar_file_result(
    user_id: int | None, text: str, data: bytes, filename: str | None, is_pdf: bool,
) -> tuple[dict, int | None]:
    """Jalankan grammar check pada teks penuh, simpan hasil + PDF asli, lalu
    bangun & cache laporan overlay (sorotan masalah di atas dokumen asli).
    Mengembalikan (hasil, history_id)."""
    res = grammar_check(text)
    res["has_original_pdf"] = is_pdf
    res["source_filename"] = filename
    hist_id = None
    if user_id is not None:
        hist_id = record_history(
            user_id, "grammar-checker", filename or "Grammar Check", text[:200], res
        )
        if hist_id and is_pdf:
            save_tool_file(user_id, hist_id, filename, "application/pdf", data, None)
            try:
                report_pdf = build_grammar_report_pdf(data, res, {"title": filename})
                save_tool_file(
                    user_id, hist_id, filename, GRAMMAR_REPORT_MIME, report_pdf, None
                )
            except Exception:  # noqa: BLE001, S110
                pass  # gagal-aman: endpoint laporan akan membangun on-demand
    return res, hist_id


async def _job_run_grammar_text(
    job_id: str, user_id: int | None, text: str, title: str,
) -> None:
    try:
        res = await run_in_threadpool(grammar_check, text)
        hist_id = None
        if user_id is not None:
            hist_id = await run_in_threadpool(
                record_history, user_id, "grammar-checker", title, text[:200], res
            )
        complete_job(job_id, hist_id)
    except Exception as exc:  # noqa: BLE001
        fail_job(job_id, str(exc))


async def _job_run_grammar_file(
    job_id: str, user_id: int | None, text: str, data: bytes, filename: str | None,
    is_pdf: bool,
) -> None:
    try:
        _, hist_id = await run_in_threadpool(
            _store_grammar_file_result, user_id, text, data, filename, is_pdf
        )
        complete_job(job_id, hist_id)
    except Exception as exc:  # noqa: BLE001
        fail_job(job_id, str(exc))


@router.post("/grammar-check-async")
async def grammar_async_ep(body: TextIn, request: Request) -> dict:
    """Versi async grammar check untuk teks tempel; kembalikan `job_id` segera
    (aman dari timeout proxy untuk dokumen besar yang dipecah per-chunk)."""
    _guard(body.text)
    user = optional_user_from_request(request)
    uid = user["id"] if user else None
    title = body.text[:60].strip() or "Grammar Check"
    job_id = create_job(uid, "grammar-checker", title)
    _spawn(_job_run_grammar_text(job_id, uid, body.text, title))
    return {"job_id": job_id, "status": "processing"}


@router.post("/grammar-check-file-async")
async def grammar_file_async_ep(  # noqa: B008
    request: Request,
    file: UploadFile = File(...),  # noqa: B008
) -> dict:
    """Versi async grammar check dari BERKAS PDF; kembalikan `job_id` segera.
    Menyimpan PDF asli agar laporan berformat identik dengan sorotan masalah."""
    data, text = await _read_pdf_upload(file)
    is_pdf = (file.filename or "").lower().endswith(".pdf")
    user = optional_user_from_request(request)
    uid = user["id"] if user else None
    job_id = create_job(uid, "grammar-checker", file.filename or "Grammar Check")
    _spawn(_job_run_grammar_file(job_id, uid, text, data, file.filename, is_pdf))
    return {"job_id": job_id, "status": "processing"}


@router.post("/paraphrase")
def paraphrase_ep(body: ParaphraseIn, request: Request) -> dict:
    _guard(body.text)
    try:
        res = paraphrase(body.text, body.style)
        _log(request, "paraphraser", "Parafrase", body.text[:200], res)
        return res
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"LLM gagal: {exc}") from exc


@router.post("/humanize")
def humanize_ep(body: TextIn, request: Request) -> dict:
    _guard(body.text)
    try:
        res = humanize(body.text)
        _log(request, "humanizer", "Humanize", body.text[:200], res)
        return res
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"LLM gagal: {exc}") from exc


# --- Alat transformasi: versi async + unggah PDF + laporan diff bersorotan -----
# paraphrase/humanize/rewrite/improve berbagi bentuk: teks masuk -> teks hasil.
# Versi async aman dari timeout proxy untuk dokumen panjang (diproses per-chunk).

# tool_key -> (slug_riwayat, label_tampilan)
_TRANSFORM_META: dict[str, tuple[str, str]] = {
    "paraphrase": ("paraphraser", "Parafrase"),
    "humanize": ("humanizer", "Humanize"),
    "rewrite": ("ai-rewriter", "AI Rewriter"),
    "improve": ("perbaikan-dokumen", "Perbaikan Dokumen"),
}
_TRANSFORM_SLUGS = {slug for slug, _ in _TRANSFORM_META.values()}


def _run_transform(tool: str, text: str, opts: dict) -> tuple[dict, str]:
    """Jalankan satu alat transformasi; kembalikan (hasil_dict, teks_hasil)."""
    if tool == "paraphrase":
        res = paraphrase(text, opts.get("style") or "standar")
        return res, res.get("result") or ""
    if tool == "humanize":
        res = humanize(text)
        return res, res.get("result") or ""
    if tool == "rewrite":
        res = rewrite(text, opts.get("tone") or "formal")
        return res, res.get("result") or ""
    if tool == "improve":
        res = improve_document(text, opts.get("goal"))
        return res, res.get("improved") or ""
    raise ValueError(f"alat transformasi tak dikenal: {tool}")


def _store_transform_result(
    user_id: int | None, tool: str, title: str, original_text: str,
    data: bytes | None, filename: str | None, is_pdf: bool, opts: dict,
) -> tuple[dict, int | None]:
    """Jalankan transformasi, simpan riwayat + PDF asli (bila ada), lalu bangun &
    cache laporan diff bersorotan (asli vs hasil)."""
    slug, label = _TRANSFORM_META[tool]
    res, result_text = _run_transform(tool, original_text, opts)
    res["original_text"] = original_text
    res["result_text"] = result_text
    res["tool_label"] = label
    res["has_original_pdf"] = is_pdf
    res["source_filename"] = filename
    hist_id = None
    if user_id is not None:
        hist_id = record_history(user_id, slug, title, original_text[:200], res)
        if hist_id:
            if is_pdf and data is not None:
                save_tool_file(user_id, hist_id, filename, "application/pdf", data, None)
            try:
                report_pdf = render_pdf(
                    transform_report_html(
                        original_text, result_text,
                        {"tool_label": label, "title": title},
                    )
                )
                save_tool_file(
                    user_id, hist_id, filename, TRANSFORM_REPORT_MIME, report_pdf, None
                )
            except Exception:  # noqa: BLE001, S110
                pass  # gagal-aman: laporan dibangun on-demand di endpoint
    return res, hist_id


async def _job_run_transform(
    job_id: str, user_id: int | None, tool: str, title: str, text: str,
    data: bytes | None, filename: str | None, is_pdf: bool, opts: dict,
) -> None:
    try:
        _, hist_id = await run_in_threadpool(
            _store_transform_result, user_id, tool, title, text, data, filename,
            is_pdf, opts,
        )
        complete_job(job_id, hist_id)
    except Exception as exc:  # noqa: BLE001
        fail_job(job_id, str(exc))


def _launch_transform_text(
    request: Request, tool: str, text: str, opts: dict,
) -> dict:
    _guard(text)
    slug, label = _TRANSFORM_META[tool]
    user = optional_user_from_request(request)
    uid = user["id"] if user else None
    title = text[:60].strip() or label
    job_id = create_job(uid, slug, title)
    _spawn(_job_run_transform(job_id, uid, tool, title, text, None, None, False, opts))
    return {"job_id": job_id, "status": "processing"}


async def _launch_transform_file(
    request: Request, tool: str, file: UploadFile, opts: dict,
) -> dict:
    data, text = await _read_pdf_upload(file)
    is_pdf = (file.filename or "").lower().endswith(".pdf")
    slug, label = _TRANSFORM_META[tool]
    user = optional_user_from_request(request)
    uid = user["id"] if user else None
    title = file.filename or label
    job_id = create_job(uid, slug, title)
    _spawn(
        _job_run_transform(job_id, uid, tool, title, text, data, file.filename, is_pdf, opts)
    )
    return {"job_id": job_id, "status": "processing"}


@router.post("/paraphrase-async")
async def paraphrase_async_ep(body: ParaphraseIn, request: Request) -> dict:
    return _launch_transform_text(request, "paraphrase", body.text, {"style": body.style})


@router.post("/paraphrase-file-async")
async def paraphrase_file_async_ep(  # noqa: B008
    request: Request,
    file: UploadFile = File(...),  # noqa: B008
    style: str = Form("standar"),  # noqa: B008
) -> dict:
    return await _launch_transform_file(request, "paraphrase", file, {"style": style})


@router.post("/humanize-async")
async def humanize_async_ep(body: TextIn, request: Request) -> dict:
    return _launch_transform_text(request, "humanize", body.text, {})


@router.post("/humanize-file-async")
async def humanize_file_async_ep(  # noqa: B008
    request: Request,
    file: UploadFile = File(...),  # noqa: B008
) -> dict:
    return await _launch_transform_file(request, "humanize", file, {})


@router.post("/rewrite-async")
async def rewrite_async_ep(body: RewriteIn, request: Request) -> dict:
    return _launch_transform_text(request, "rewrite", body.text, {"tone": body.tone})


@router.post("/rewrite-file-async")
async def rewrite_file_async_ep(  # noqa: B008
    request: Request,
    file: UploadFile = File(...),  # noqa: B008
    tone: str = Form("formal"),  # noqa: B008
) -> dict:
    return await _launch_transform_file(request, "rewrite", file, {"tone": tone})


@router.post("/improve-async")
async def improve_async_ep(body: ImproveIn, request: Request) -> dict:
    return _launch_transform_text(request, "improve", body.text, {"goal": body.goal})


@router.post("/improve-file-async")
async def improve_file_async_ep(  # noqa: B008
    request: Request,
    file: UploadFile = File(...),  # noqa: B008
    goal: str | None = Form(None),  # noqa: B008
) -> dict:
    return await _launch_transform_file(request, "improve", file, {"goal": goal})


@router.get("/transform-report/{history_id}")
def transform_report_ep(history_id: int, request: Request, dl: int = 0) -> Response:
    """Laporan PDF diff bersorotan untuk alat transformasi: sajikan cache bila
    ada, jika tidak bangun on-demand dari teks asli + hasil di riwayat."""
    user = optional_user_from_request(request)
    if not user:
        raise HTTPException(status_code=401, detail="Perlu login.")
    uid = user["id"]
    item = get_history_item(uid, history_id)
    if not item or item.get("tool") not in _TRANSFORM_SLUGS:
        raise HTTPException(status_code=404, detail="Riwayat tidak ditemukan.")
    result = item.get("result") or {}

    cached = get_tool_file_by_history(uid, history_id, TRANSFORM_REPORT_MIME)
    if cached and cached.get("data"):
        base = (cached.get("filename") or "laporan").rsplit(".", 1)[0]
        return _pdf_response(cached["data"], f"laporan-{base}.pdf", dl)

    original = result.get("original_text") or ""
    result_text = result.get("result_text") or result.get("result") or result.get("improved") or ""
    label = result.get("tool_label") or "Transformasi Teks"
    try:
        pdf = render_pdf(
            transform_report_html(
                original, result_text, {"tool_label": label, "title": item.get("title")}
            )
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"Render laporan gagal: {exc}") from exc
    try:
        save_tool_file(
            uid, history_id, result.get("source_filename"), TRANSFORM_REPORT_MIME, pdf, None
        )
    except Exception:  # noqa: BLE001, S110
        pass
    return _pdf_response(pdf, f"laporan-{history_id}.pdf", dl)


def _require_pdf_upload(filename: str | None) -> None:
    """Plagiarism Checker hanya menerima PDF.

    Laporan berformat identik (sorotan langsung di atas halaman asli) HANYA bisa
    dibuat dari PDF. Word/DOCX tidak bisa dibuat laporan berformat-asli, dan
    mengonversinya otomatis ke PDF membuat tata letak & posisi sorotan tidak
    akurat. Maka berkas non-PDF ditolak dengan panduan jelas; pengguna dapat
    menempel teks (paste) bila hanya ingin skor, atau menyimpan dokumennya
    sebagai PDF lalu mengunggah ulang.
    """
    if not (filename or "").lower().endswith(".pdf"):
        raise HTTPException(
            status_code=415,
            detail=(
                "Untuk Plagiarism Checker, unggah berkas PDF. Dokumen Word (.docx) "
                "tidak didukung karena laporan berformat identik tidak bisa dibuat. "
                "Simpan dokumen Anda sebagai PDF lalu unggah ulang — atau tempel "
                "teksnya langsung bila hanya ingin skor kemiripan."
            ),
        )


def _clean_doc_title(raw: str | None, fallback: str = "") -> str:
    """Judul dokumen dari input user: buang karakter kontrol/spasi ganda, maks 200."""
    t = re.sub(r"[\x00-\x1f\x7f]+", " ", raw or "")
    t = re.sub(r"\s+", " ", t).strip()[:200]
    return t or fallback


def _title_hint_from_filename(filename: str | None) -> str:
    """Judul perkiraan dari nama berkas unggahan (banyak PDF akademik dinamai
    sesuai judulnya). Buang ekstensi & pemisah umum agar jadi query judul."""
    import os
    import re as _re

    stem = os.path.splitext(filename or "")[0]
    stem = _re.sub(r"[_\-]+", " ", stem)
    stem = _re.sub(r"\s+", " ", stem).strip()
    return stem


async def _run_plagiarism_merged(
    text: str, top_k: int, title_hint: str = "", exclude: dict | None = None
) -> dict:
    """Jalankan cek plagiarisme korpus lokal, lalu—bila diaktifkan—gabungkan
    sumber daring (tanpa-unduh) ke dalam skor yang sama. Galat daring tidak
    membatalkan laporan; cukup turun ke hasil korpus lokal saja. `title_hint`
    (mis. nama berkas) membantu menemukan paper terbit yang identik. `exclude`
    adalah pengaturan Exclude pra-pengecekan yang dikunci pada hasil."""
    extra: list[dict] = []
    providers: dict = {}
    if settings.online_check_enabled:
        # 1) PASS IDENTITAS DULU (cepat, ~9–60 dtk): resolusi judul/DOI + unduh
        #    teks-penuh paper dokumen itu sendiri. WAJIB dijalankan SEBELUM
        #    pencarian luas, karena pencarian luas membanjiri Crossref/OpenAlex
        #    dengan ribuan permintaan → kueri identitas kena rate-limit (429)
        #    dan paper terbit milik user tak ditemukan. Mendahulukannya menjamin
        #    kandidat identitas selalu tertangkap, lalu digabung ke hasil luas.
        ident: list[dict] = []
        try:
            ident = await asyncio.wait_for(
                identity_candidates(text, title_hint),
                timeout=max(30, settings.online_identity_budget_seconds),
            )
        except Exception:  # noqa: BLE001
            ident = []
        # 2) Pencarian luas per-kalimat dengan sisa anggaran. Bila timeout, hasil
        #    identitas di atas tetap dipakai (laporan tak pernah kehilangan paper
        #    terbit hanya karena fase luas lambat).
        try:
            extra, providers = await asyncio.wait_for(
                online_candidates(text, title_hint),
                timeout=max(30, settings.online_budget_seconds),
            )
        except Exception:  # noqa: BLE001
            extra, providers = [], {}
        # Gabungkan: dedup per DOI/judul, pertahankan teks-penuh TERPANJANG agar
        # cakupan pencocokan maksimal (paper terbit sering hanya lengkap dari
        # pass identitas).
        merged: dict[str, dict] = {}
        for cand in list(extra) + list(ident):
            if not cand.get("_fulltext") or not cand.get("title"):
                continue
            key = (cand.get("doi") or cand["title"]).lower().strip()
            cur = merged.get(key)
            if cur is None or len(cand["_fulltext"]) > len(cur.get("_fulltext") or ""):
                if cur is not None and not cand.get("_oa_url") and cur.get("_oa_url"):
                    cand["_oa_url"] = cur["_oa_url"]
                merged[key] = cand
        extra = list(merged.values())
    res = await run_in_threadpool(check_plagiarism, text, top_k, extra, exclude)
    res["online_merged"] = bool(extra)
    res["online_providers"] = [
        {"name": k, "hits": v} for k, v in sorted(providers.items(), key=lambda kv: -kv[1])
    ]
    return res


@router.post("/plagiarism")
async def plagiarism_ep(body: PlagiarismIn, request: Request) -> dict:
    _guard(body.text)
    ex = body.exclude.model_dump() if body.exclude else None
    try:
        res = await _run_plagiarism_merged(body.text, body.top_k, exclude=ex)
        _log(request, "plagiarism-checker", "Cek Plagiarisme", body.text[:200], res)
        return res
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"Cek plagiarisme gagal: {exc}") from exc


@router.post("/plagiarism-online")
async def plagiarism_online_ep(body: PlagiarismIn, request: Request) -> dict:
    """Pemeriksaan daring tanpa-unduh terhadap sumber akademik gratis
    (OpenAlex/Crossref/arXiv/Wikipedia + CORE bila diizinkan). Pelengkap
    korpus lokal; tidak menyimpan data sumber."""
    if not settings.online_check_enabled:
        raise HTTPException(status_code=503, detail="Cek daring dinonaktifkan.")
    _guard(body.text)
    try:
        res = await online_check(body.text)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"Cek daring gagal: {exc}") from exc
    return res


def _exclude_from_query(
    exclude_bibliography: bool, exclude_quotes: bool, exclude_min_percent: float
) -> dict:
    """Bangun pengaturan Exclude dari query param (untuk endpoint unggah berkas)."""
    return {
        "bibliography": bool(exclude_bibliography),
        "quotes": bool(exclude_quotes),
        "min_source_percent": max(0.0, min(100.0, float(exclude_min_percent or 0.0))),
    }


@router.post("/plagiarism-file")
async def plagiarism_file_ep(  # noqa: B008
    request: Request,
    file: UploadFile = File(...),  # noqa: B008
    top_k: int = 30,
    exclude_bibliography: bool = False,
    exclude_quotes: bool = False,
    exclude_min_percent: float = 0.0,
    doc_title: str = "",
) -> dict:
    """Cek plagiarisme dari BERKAS asli; simpan PDF asli di VM untuk laporan
    berformat identik (sorotan di atas dokumen asli)."""
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Berkas kosong.")
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413, detail=f"Berkas melebihi {MAX_UPLOAD_BYTES // (1024 * 1024)} MB."
        )
    _require_pdf_upload(file.filename)
    try:
        text = extract_text(file.filename or "", data).strip()
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if not text:
        raise HTTPException(status_code=422, detail="Tidak ada teks yang dapat diekstrak.")
    _guard(text)
    ex = _exclude_from_query(exclude_bibliography, exclude_quotes, exclude_min_percent)
    try:
        res = await _run_plagiarism_merged(
            text, min(max(top_k, 1), 60), _title_hint_from_filename(file.filename), ex
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"Cek plagiarisme gagal: {exc}") from exc

    is_pdf = (file.filename or "").lower().endswith(".pdf")
    title = _clean_doc_title(doc_title, file.filename or "Cek Plagiarisme")
    res["has_original_pdf"] = is_pdf
    res["source_filename"] = file.filename
    res["doc_title"] = title
    try:
        user = optional_user_from_request(request)
        if user:
            hist_id = record_history(
                user["id"], "plagiarism-checker", title, text[:200], res,
            )
            if hist_id and is_pdf:
                save_tool_file(
                    user["id"], hist_id, file.filename, "application/pdf", data,
                    res.get("content_sha256"),
                )
    except Exception:  # noqa: BLE001, S110
        pass
    return res


# ── Pekerjaan latar-belakang (async) untuk cek plagiarisme ───────────────────
# Menghindari koneksi HTTP panjang (rawan timeout proxy): submit → job_id →
# polling status. Pemrosesan berjalan di event loop backend.
_BG_TASKS: set = set()


def _spawn(coro) -> None:
    task = asyncio.create_task(coro)
    _BG_TASKS.add(task)
    task.add_done_callback(_BG_TASKS.discard)


async def _job_run_text(
    job_id: str, user_id: int | None, text: str, top_k: int, title: str,
    exclude: dict | None = None,
) -> None:
    try:
        res = await _run_plagiarism_merged(text, top_k, exclude=exclude)
        res["doc_title"] = title
        hist_id = None
        if user_id is not None:
            hist_id = await run_in_threadpool(
                record_history, user_id, "plagiarism-checker", title, text[:200], res
            )
        complete_job(job_id, hist_id)
    except Exception as exc:  # noqa: BLE001
        fail_job(job_id, str(exc))


async def _job_run_file(
    job_id: str, user_id: int | None, text: str, data: bytes, filename: str | None,
    is_pdf: bool, top_k: int, exclude: dict | None = None, doc_title: str = "",
) -> None:
    try:
        res = await _run_plagiarism_merged(
            text, top_k, _title_hint_from_filename(filename), exclude
        )
        title = _clean_doc_title(doc_title, filename or "Cek Plagiarisme")
        res["has_original_pdf"] = is_pdf
        res["source_filename"] = filename
        res["doc_title"] = title
        hist_id = None
        if user_id is not None:
            hist_id = await run_in_threadpool(
                record_history, user_id, "plagiarism-checker", title, text[:200], res,
            )
            if hist_id and is_pdf:
                await run_in_threadpool(
                    save_tool_file, user_id, hist_id, filename, "application/pdf",
                    data, res.get("content_sha256"),
                )
        complete_job(job_id, hist_id)
    except Exception as exc:  # noqa: BLE001
        fail_job(job_id, str(exc))


@router.post("/plagiarism-async")
async def plagiarism_async_ep(body: PlagiarismIn, request: Request) -> dict:
    """Mulai cek plagiarisme di latar belakang; kembalikan `job_id` segera."""
    _guard(body.text)
    user = optional_user_from_request(request)
    uid = user["id"] if user else None
    title = _clean_doc_title(body.title, body.text[:60].strip() or "Cek Plagiarisme")
    ex = body.exclude.model_dump() if body.exclude else None
    job_id = create_job(uid, "plagiarism-checker", title)
    _spawn(_job_run_text(job_id, uid, body.text, body.top_k, title, ex))
    return {"job_id": job_id, "status": "processing"}


@router.post("/plagiarism-file-async")
async def plagiarism_file_async_ep(  # noqa: B008
    request: Request,
    file: UploadFile = File(...),  # noqa: B008
    top_k: int = 30,
    exclude_bibliography: bool = False,
    exclude_quotes: bool = False,
    exclude_min_percent: float = 0.0,
    doc_title: str = "",
) -> dict:
    """Versi async dari cek berkas; kembalikan `job_id` segera."""
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Berkas kosong.")
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413, detail=f"Berkas melebihi {MAX_UPLOAD_BYTES // (1024 * 1024)} MB."
        )
    _require_pdf_upload(file.filename)
    try:
        text = extract_text(file.filename or "", data).strip()
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if not text:
        raise HTTPException(status_code=422, detail="Tidak ada teks yang dapat diekstrak.")
    _guard(text)
    user = optional_user_from_request(request)
    uid = user["id"] if user else None
    is_pdf = (file.filename or "").lower().endswith(".pdf")
    ex = _exclude_from_query(exclude_bibliography, exclude_quotes, exclude_min_percent)
    title = _clean_doc_title(doc_title, file.filename or "Cek Plagiarisme")
    job_id = create_job(uid, "plagiarism-checker", title)
    _spawn(
        _job_run_file(
            job_id, uid, text, data, file.filename, is_pdf, min(max(top_k, 1), 60), ex,
            title,
        )
    )
    return {"job_id": job_id, "status": "processing"}


@router.get("/job/{job_id}")
def job_status_ep(job_id: str, request: Request) -> dict:
    """Status pekerjaan latar-belakang: processing | done | error."""
    user = optional_user_from_request(request)
    uid = user["id"] if user else None
    job = get_job(job_id, uid)
    if not job:
        raise HTTPException(status_code=404, detail="Job tidak ditemukan.")
    return job


@router.get("/plagiarism-report/{history_id}")
def plagiarism_report_ep(history_id: int, request: Request, dl: int = 0) -> Response:
    """Laporan PDF berformat identik dengan berkas asli (sorotan + sampul)."""
    user = optional_user_from_request(request)
    if not user:
        raise HTTPException(status_code=401, detail="Perlu login.")
    item = get_history_item(user["id"], history_id)
    if not item or item.get("tool") != "plagiarism-checker":
        raise HTTPException(status_code=404, detail="Riwayat tidak ditemukan.")
    f = get_tool_file_by_history(user["id"], history_id)
    if not f or not f.get("data"):
        raise HTTPException(
            status_code=404,
            detail="Dokumen asli tidak tersedia (kedaluwarsa atau bukan unggahan PDF).",
        )
    try:
        pdf = build_report_pdf(f["data"], item["result"] or {})
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"Render laporan gagal: {exc}") from exc
    base = (item.get("result") or {}).get("doc_title") or (
        (f.get("filename") or "laporan").rsplit(".", 1)[0]
    )
    base = re.sub(r"[^A-Za-z0-9._-]+", "-", base).strip("-")[:80] or "laporan"
    name = f"laporan-integritas-{base}.pdf"
    disp = "attachment" if dl else "inline"
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'{disp}; filename="{name}"'},
    )


def _report_history(request: Request, history_id: int, expect_tool: str) -> dict:
    user = optional_user_from_request(request)
    if not user:
        raise HTTPException(status_code=401, detail="Perlu login.")
    item = get_history_item(user["id"], history_id)
    if not item or item.get("tool") != expect_tool:
        raise HTTPException(status_code=404, detail="Riwayat tidak ditemukan.")
    return item


def _pdf_response(pdf: bytes, name: str, dl: int) -> Response:
    disp = "attachment" if dl else "inline"
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'{disp}; filename="{name}"'},
    )


@router.get("/ai-detect-report/{history_id}")
def ai_detect_report_ep(history_id: int, request: Request, dl: int = 0) -> Response:
    """Laporan PDF hasil deteksi AI dari riwayat pengguna.

    Urutan: (1) sajikan laporan overlay yang sudah di-cache (instan, dibangun
    saat deteksi) bila ada; (2) bila hanya PDF asli tersimpan, bangun overlay
    on-demand lalu cache untuk unduhan berikutnya; (3) bila tak ada PDF, pakai
    laporan HTML untuk teks tempel.
    """
    item = _report_history(request, history_id, "ai-detector")
    result = item.get("result") or {}
    user = optional_user_from_request(request)
    uid = user["id"] if user else None

    cached = get_tool_file_by_history(uid, history_id, AI_REPORT_MIME) if uid else None
    if cached and cached.get("data"):
        base = (cached.get("filename") or "laporan").rsplit(".", 1)[0]
        return _pdf_response(cached["data"], f"laporan-ai-detector-{base}.pdf", dl)

    orig = get_tool_file_by_history(uid, history_id, "application/pdf") if uid else None
    if orig and orig.get("data"):
        try:
            pdf = build_ai_report_pdf(orig["data"], result, {"title": item.get("title")})
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(
                status_code=502, detail=f"Render laporan gagal: {exc}"
            ) from exc
        if uid:
            try:
                save_tool_file(
                    uid, history_id, orig.get("filename"), AI_REPORT_MIME, pdf, None
                )
            except Exception:  # noqa: BLE001, S110
                pass
        base = (orig.get("filename") or "laporan").rsplit(".", 1)[0]
        return _pdf_response(pdf, f"laporan-ai-detector-{base}.pdf", dl)

    try:
        html = ai_detector_report_html(result, {"title": item.get("title")})
        pdf = render_pdf(html)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"Render laporan gagal: {exc}") from exc
    return _pdf_response(pdf, f"laporan-ai-detector-{history_id}.pdf", dl)


@router.get("/grammar-report/{history_id}")
def grammar_report_ep(history_id: int, request: Request, dl: int = 0) -> Response:
    """Laporan PDF hasil pemeriksaan tata bahasa dari riwayat pengguna.

    Urutan sama seperti deteksi AI: (1) sajikan laporan overlay ber-cache
    (instan) bila ada; (2) bila hanya PDF asli tersimpan, bangun overlay
    on-demand lalu cache; (3) bila tak ada PDF, pakai laporan HTML untuk teks
    tempel.
    """
    item = _report_history(request, history_id, "grammar-checker")
    result = item.get("result") or {}
    user = optional_user_from_request(request)
    uid = user["id"] if user else None

    cached = (
        get_tool_file_by_history(uid, history_id, GRAMMAR_REPORT_MIME) if uid else None
    )
    if cached and cached.get("data"):
        base = (cached.get("filename") or "laporan").rsplit(".", 1)[0]
        return _pdf_response(cached["data"], f"laporan-grammar-{base}.pdf", dl)

    orig = get_tool_file_by_history(uid, history_id, "application/pdf") if uid else None
    if orig and orig.get("data"):
        try:
            pdf = build_grammar_report_pdf(
                orig["data"], result, {"title": item.get("title")}
            )
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(
                status_code=502, detail=f"Render laporan gagal: {exc}"
            ) from exc
        if uid:
            try:
                save_tool_file(
                    uid, history_id, orig.get("filename"), GRAMMAR_REPORT_MIME, pdf, None
                )
            except Exception:  # noqa: BLE001, S110
                pass
        base = (orig.get("filename") or "laporan").rsplit(".", 1)[0]
        return _pdf_response(pdf, f"laporan-grammar-{base}.pdf", dl)

    try:
        html = grammar_report_html(result, {"title": item.get("title")})
        pdf = render_pdf(html)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"Render laporan gagal: {exc}") from exc
    return _pdf_response(pdf, f"laporan-grammar-{history_id}.pdf", dl)


@router.post("/rewrite")
def rewrite_ep(body: RewriteIn, request: Request) -> dict:
    _guard(body.text)
    try:
        res = rewrite(body.text, body.tone)
        _log(request, "ai-rewriter", "AI Rewriter", body.text[:200], res)
        return res
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"LLM gagal: {exc}") from exc


@router.post("/chat")
def chat_ep(body: ChatIn, request: Request) -> dict:
    total = sum(len(m.content) for m in body.messages)
    if total > MAX_CHARS:
        raise HTTPException(
            status_code=413,
            detail=f"Percakapan melebihi batas keamanan server ({MAX_CHARS:,} karakter).",
        )
    try:
        res = chat([m.model_dump() for m in body.messages], body.system)
        last = next((m.content for m in reversed(body.messages) if m.role == "user"), "")
        _log(request, "ai-chat", "AI Chat", last[:200], res)
        return res
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"LLM gagal: {exc}") from exc


@router.post("/grade")
def grade_ep(body: GradeIn, request: Request) -> dict:
    _guard(body.text)
    try:
        res = grade_essay(body.text, body.rubric)
        _log(request, "ai-grader", "AI Grader", body.text[:200], res)
        return res
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"LLM gagal: {exc}") from exc


@router.post("/reader-reactions")
def reader_reactions_ep(body: TextIn, request: Request) -> dict:
    _guard(body.text)
    try:
        res = reader_reactions(body.text)
        _log(request, "reader-reactions", "Reader Reactions", body.text[:200], res)
        return res
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"LLM gagal: {exc}") from exc


@router.post("/resume")
def resume_ep(body: ResumeIn, request: Request) -> dict:
    if len(body.info) > MAX_CHARS:
        raise HTTPException(
            status_code=413,
            detail=(
                f"Teks melebihi batas keamanan server ({MAX_CHARS:,} karakter). "
                "Pisahkan dokumen menjadi beberapa bagian."
            ),
        )
    try:
        res = build_resume(body.info, body.target_role)
        _log(request, "resume-builder", "Resume Builder", body.info[:200], res)
        return res
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"LLM gagal: {exc}") from exc


@router.post("/citations")
def citations_ep(body: CitationIn, request: Request) -> dict:
    _guard(body.text)
    try:
        res = find_citations(body.text, body.top_k)
        _log(request, "citation-finder", "Citation Finder", body.text[:200], res)
        return res
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"Pencarian sitasi gagal: {exc}") from exc


@router.post("/ai-detect")
def ai_detect_ep(body: TextIn, request: Request) -> dict:
    _guard(body.text)
    try:
        res = detect_ai(body.text)
        logged = {**res, "input_text": body.text}
        _log(request, "ai-detector", "AI Detector", body.text[:200], logged)
        return res
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"Deteksi AI gagal: {exc}") from exc


def _store_ai_file_result(
    user_id: int | None, text: str, data: bytes, filename: str | None, is_pdf: bool,
) -> tuple[dict, int | None]:
    """Jalankan deteksi AI pada teks penuh, simpan hasil + PDF asli (untuk laporan
    berformat identik dengan sorotan segmen). Mengembalikan (hasil, history_id)."""
    res = detect_ai(text)
    res["has_original_pdf"] = is_pdf
    res["source_filename"] = filename
    logged = {**res, "input_text": text}
    hist_id = None
    if user_id is not None:
        hist_id = record_history(
            user_id, "ai-detector", filename or "AI Detector", text[:200], logged
        )
        if hist_id and is_pdf:
            save_tool_file(user_id, hist_id, filename, "application/pdf", data, None)
            # Bangun laporan overlay SEKARANG (di latar belakang job, bebas batas
            # proxy) lalu cache — agar unduhan nanti instan & tak kena 524.
            try:
                report_pdf = build_ai_report_pdf(data, logged, {"title": filename})
                save_tool_file(
                    user_id, hist_id, filename, AI_REPORT_MIME, report_pdf, None
                )
            except Exception:  # noqa: BLE001, S110
                pass  # gagal-aman: endpoint laporan akan membangun on-demand
    return res, hist_id


async def _read_pdf_upload(file: UploadFile) -> tuple[bytes, str]:
    """Baca unggahan PDF, validasi, ekstrak teks penuh (tanpa pemotongan)."""
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Berkas kosong.")
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413, detail=f"Berkas melebihi {MAX_UPLOAD_BYTES // (1024 * 1024)} MB."
        )
    _require_pdf_upload(file.filename)
    try:
        text = extract_text(file.filename or "", data).strip()
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if not text:
        raise HTTPException(status_code=422, detail="Tidak ada teks yang dapat diekstrak.")
    _guard(text)
    return data, text


@router.post("/ai-detect-file")
async def ai_detect_file_ep(  # noqa: B008
    request: Request,
    file: UploadFile = File(...),  # noqa: B008
) -> dict:
    """Deteksi AI dari BERKAS PDF asli; simpan PDF untuk laporan berformat identik
    (sorotan segmen di atas dokumen asli, seperti cek plagiarisme)."""
    data, text = await _read_pdf_upload(file)
    is_pdf = (file.filename or "").lower().endswith(".pdf")
    try:
        user = optional_user_from_request(request)
        uid = user["id"] if user else None
        res, _ = await run_in_threadpool(
            _store_ai_file_result, uid, text, data, file.filename, is_pdf
        )
        return res
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"Deteksi AI gagal: {exc}") from exc


async def _job_run_ai_file(
    job_id: str, user_id: int | None, text: str, data: bytes, filename: str | None,
    is_pdf: bool,
) -> None:
    try:
        _, hist_id = await run_in_threadpool(
            _store_ai_file_result, user_id, text, data, filename, is_pdf
        )
        complete_job(job_id, hist_id)
    except Exception as exc:  # noqa: BLE001
        fail_job(job_id, str(exc))


@router.post("/ai-detect-file-async")
async def ai_detect_file_async_ep(  # noqa: B008
    request: Request,
    file: UploadFile = File(...),  # noqa: B008
) -> dict:
    """Versi async deteksi AI dari berkas; kembalikan `job_id` segera (aman dari
    timeout proxy untuk dokumen besar)."""
    data, text = await _read_pdf_upload(file)
    is_pdf = (file.filename or "").lower().endswith(".pdf")
    user = optional_user_from_request(request)
    uid = user["id"] if user else None
    job_id = create_job(uid, "ai-detector", file.filename or "AI Detector")
    _spawn(_job_run_ai_file(job_id, uid, text, data, file.filename, is_pdf))
    return {"job_id": job_id, "status": "processing"}


@router.post("/authorship")
def authorship_ep(body: AuthorshipIn, request: Request) -> dict:
    _guard(body.text)
    try:
        res = analyze_authorship(body.text, body.compare)
        _log(request, "authorship", "Authorship", body.text[:200], res)
        return res
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"Analisis kepenulisan gagal: {exc}") from exc


@router.post("/toc")
def toc_ep(body: TextIn, request: Request) -> dict:
    _guard(body.text)
    try:
        res = generate_toc(body.text)
        _log(request, "daftar-isi", "Daftar Isi Otomatis", body.text[:200], res)
        return res
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"LLM gagal: {exc}") from exc


def _store_toc_result(
    user_id: int | None, text: str, data: bytes | None, filename: str | None, is_pdf: bool,
) -> tuple[dict, int | None]:
    """Susun Daftar Isi, simpan riwayat + PDF asli (bila ada), bangun & cache
    laporan Daftar Isi PDF."""
    res = generate_toc(text)
    res["has_original_pdf"] = is_pdf
    res["source_filename"] = filename
    title = filename or "Daftar Isi Otomatis"
    hist_id = None
    if user_id is not None:
        hist_id = record_history(user_id, "daftar-isi", title, text[:200], res)
        if hist_id:
            if is_pdf and data is not None:
                save_tool_file(user_id, hist_id, filename, "application/pdf", data, None)
            try:
                report_pdf = render_pdf(toc_report_html(res, {"title": title}))
                save_tool_file(
                    user_id, hist_id, filename, TOC_REPORT_MIME, report_pdf, None
                )
            except Exception:  # noqa: BLE001, S110
                pass
    return res, hist_id


async def _job_run_toc(
    job_id: str, user_id: int | None, text: str, data: bytes | None,
    filename: str | None, is_pdf: bool,
) -> None:
    try:
        _, hist_id = await run_in_threadpool(
            _store_toc_result, user_id, text, data, filename, is_pdf
        )
        complete_job(job_id, hist_id)
    except Exception as exc:  # noqa: BLE001
        fail_job(job_id, str(exc))


@router.post("/toc-async")
async def toc_async_ep(body: TextIn, request: Request) -> dict:
    _guard(body.text)
    user = optional_user_from_request(request)
    uid = user["id"] if user else None
    job_id = create_job(uid, "daftar-isi", body.text[:60].strip() or "Daftar Isi Otomatis")
    _spawn(_job_run_toc(job_id, uid, body.text, None, None, False))
    return {"job_id": job_id, "status": "processing"}


@router.post("/toc-file-async")
async def toc_file_async_ep(  # noqa: B008
    request: Request,
    file: UploadFile = File(...),  # noqa: B008
) -> dict:
    data, text = await _read_pdf_upload(file)
    is_pdf = (file.filename or "").lower().endswith(".pdf")
    user = optional_user_from_request(request)
    uid = user["id"] if user else None
    job_id = create_job(uid, "daftar-isi", file.filename or "Daftar Isi Otomatis")
    _spawn(_job_run_toc(job_id, uid, text, data, file.filename, is_pdf))
    return {"job_id": job_id, "status": "processing"}


@router.get("/toc-report/{history_id}")
def toc_report_ep(history_id: int, request: Request, dl: int = 0) -> Response:
    """Laporan PDF Daftar Isi: sajikan cache bila ada, jika tidak bangun on-demand."""
    item = _report_history(request, history_id, "daftar-isi")
    result = item.get("result") or {}
    user = optional_user_from_request(request)
    uid = user["id"] if user else None

    cached = get_tool_file_by_history(uid, history_id, TOC_REPORT_MIME) if uid else None
    if cached and cached.get("data"):
        base = (cached.get("filename") or "daftar-isi").rsplit(".", 1)[0]
        return _pdf_response(cached["data"], f"laporan-daftar-isi-{base}.pdf", dl)

    try:
        pdf = render_pdf(toc_report_html(result, {"title": item.get("title")}))
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"Render laporan gagal: {exc}") from exc
    if uid:
        try:
            save_tool_file(
                uid, history_id, result.get("source_filename"), TOC_REPORT_MIME, pdf, None
            )
        except Exception:  # noqa: BLE001, S110
            pass
    return _pdf_response(pdf, f"laporan-daftar-isi-{history_id}.pdf", dl)


@router.post("/improve")
def improve_ep(body: ImproveIn, request: Request) -> dict:
    _guard(body.text)
    try:
        res = improve_document(body.text, body.goal)
        _log(request, "perbaikan-dokumen", "Perbaikan Dokumen", body.text[:200], res)
        return res
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"LLM gagal: {exc}") from exc


@router.post("/hidden-text")
def hidden_text_ep(body: HiddenTextIn, request: Request) -> dict:
    _guard(body.text)
    try:
        res = check_hidden_text(body.text, body.check_typos)
        _log(request, "hidden-text", "Cek Hidden Text & Typo", body.text[:200], res)
        return res
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"Pemindaian gagal: {exc}") from exc


@router.post("/doc-chat")
def doc_chat_ep(body: DocChatIn, request: Request) -> dict:
    total = len(body.context) + sum(len(m.content) for m in body.messages)
    if total > MAX_CHARS * 2:
        raise HTTPException(status_code=413, detail="Dokumen + percakapan terlalu panjang.")
    try:
        res = doc_chat(body.context, [m.model_dump() for m in body.messages])
        last = next((m.content for m in reversed(body.messages) if m.role == "user"), "")
        _log(request, "chat-pdf", "Chat PDF", last[:200], res)
        return res
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"LLM gagal: {exc}") from exc


@router.post("/publikasi")
def publikasi_ep(body: PublikasiIn, request: Request) -> dict:
    _guard(body.text)
    try:
        res = recommend_journals(body.text, body.top_k)
        _log(request, "publikasi-jurnal", "Publikasi Jurnal", body.text[:200], res)
        return res
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"Rekomendasi publikasi gagal: {exc}") from exc


@router.post("/transcribe")
async def transcribe_ep(
    request: Request,
    file: UploadFile = File(...),  # noqa: B008
    language: str | None = None,
) -> dict:
    if not is_supported(file.filename or ""):
        raise HTTPException(
            status_code=422,
            detail="Format tidak didukung. Gunakan mp3/wav/m4a/ogg/mp4/webm, dll.",
        )
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Berkas kosong.")
    if len(data) > MAX_AUDIO_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"Berkas melebihi {MAX_AUDIO_BYTES // (1024 * 1024)} MB.",
        )
    try:
        res = await asyncio.wait_for(
            run_in_threadpool(transcribe_audio, file.filename or "audio", data, language),
            timeout=TRANSCRIBE_TIMEOUT,
        )
    except asyncio.TimeoutError as exc:
        raise HTTPException(
            status_code=504,
            detail=(
                f"Transkripsi melebihi batas waktu {TRANSCRIBE_TIMEOUT} dtk. "
                "Coba berkas lebih pendek."
            ),
        ) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"Transkripsi gagal: {exc}") from exc
    _log(request, "transkrip-audio", "Transkrip Audio", file.filename or "audio", res)
    return res


class ReportPdfIn(BaseModel):
    html: str = Field(..., min_length=1)
    filename: str = Field(default="laporan.pdf", max_length=120)


@router.post("/report-pdf")
async def report_pdf_ep(body: ReportPdfIn) -> Response:
    if len(body.html.encode("utf-8")) > MAX_HTML_BYTES:
        raise HTTPException(status_code=413, detail="Konten laporan terlalu besar.")
    name = body.filename.strip() or "laporan.pdf"
    if not name.lower().endswith(".pdf"):
        name += ".pdf"
    try:
        pdf = render_pdf(body.html)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"Render PDF gagal: {exc}") from exc
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{name}"'},
    )
