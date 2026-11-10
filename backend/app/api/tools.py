"""Endpoint fitur ringan Fase 1."""

import asyncio

from fastapi import APIRouter, File, HTTPException, Request, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import Response
from pydantic import BaseModel, Field

from app.core.config import get_settings
from app.services.ai_detector import detect_ai
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
from app.services.plagiarism.online import online_candidates, online_check
from app.services.plagiarism.report_pdf import build_report_pdf
from app.services.publikasi import recommend_journals
from app.services.report import MAX_HTML_BYTES, render_pdf
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
settings = get_settings()


class TextIn(BaseModel):
    text: str = Field(..., min_length=1)


class ParaphraseIn(TextIn):
    style: str = Field(default="standar")


class PlagiarismIn(TextIn):
    top_k: int = Field(default=30, ge=1, le=60)


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


def _title_hint_from_filename(filename: str | None) -> str:
    """Judul perkiraan dari nama berkas unggahan (banyak PDF akademik dinamai
    sesuai judulnya). Buang ekstensi & pemisah umum agar jadi query judul."""
    import os
    import re as _re

    stem = os.path.splitext(filename or "")[0]
    stem = _re.sub(r"[_\-]+", " ", stem)
    stem = _re.sub(r"\s+", " ", stem).strip()
    return stem


async def _run_plagiarism_merged(text: str, top_k: int, title_hint: str = "") -> dict:
    """Jalankan cek plagiarisme korpus lokal, lalu—bila diaktifkan—gabungkan
    sumber daring (tanpa-unduh) ke dalam skor yang sama. Galat daring tidak
    membatalkan laporan; cukup turun ke hasil korpus lokal saja. `title_hint`
    (mis. nama berkas) membantu menemukan paper terbit yang identik."""
    extra: list[dict] = []
    providers: dict = {}
    if settings.online_check_enabled:
        try:
            extra, providers = await online_candidates(text, title_hint)
        except Exception:  # noqa: BLE001, S110
            extra, providers = [], {}
    res = await run_in_threadpool(check_plagiarism, text, top_k, extra)
    res["online_merged"] = bool(extra)
    res["online_providers"] = [
        {"name": k, "hits": v} for k, v in sorted(providers.items(), key=lambda kv: -kv[1])
    ]
    return res


@router.post("/plagiarism")
async def plagiarism_ep(body: PlagiarismIn, request: Request) -> dict:
    _guard(body.text)
    try:
        res = await _run_plagiarism_merged(body.text, body.top_k)
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


@router.post("/plagiarism-file")
async def plagiarism_file_ep(  # noqa: B008
    request: Request,
    file: UploadFile = File(...),  # noqa: B008
    top_k: int = 30,
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
    try:
        text = extract_text(file.filename or "", data).strip()
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if not text:
        raise HTTPException(status_code=422, detail="Tidak ada teks yang dapat diekstrak.")
    _guard(text)
    try:
        res = await _run_plagiarism_merged(
            text, min(max(top_k, 1), 60), _title_hint_from_filename(file.filename)
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"Cek plagiarisme gagal: {exc}") from exc

    is_pdf = (file.filename or "").lower().endswith(".pdf")
    res["has_original_pdf"] = is_pdf
    res["source_filename"] = file.filename
    try:
        user = optional_user_from_request(request)
        if user:
            hist_id = record_history(
                user["id"], "plagiarism-checker", file.filename or "Cek Plagiarisme",
                text[:200], res,
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


async def _job_run_text(job_id: str, user_id: int | None, text: str, top_k: int, title: str) -> None:
    try:
        res = await _run_plagiarism_merged(text, top_k)
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
    is_pdf: bool, top_k: int,
) -> None:
    try:
        res = await _run_plagiarism_merged(text, top_k, _title_hint_from_filename(filename))
        res["has_original_pdf"] = is_pdf
        res["source_filename"] = filename
        hist_id = None
        if user_id is not None:
            hist_id = await run_in_threadpool(
                record_history, user_id, "plagiarism-checker",
                filename or "Cek Plagiarisme", text[:200], res,
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
    title = body.text[:60].strip() or "Cek Plagiarisme"
    job_id = create_job(uid, "plagiarism-checker", title)
    _spawn(_job_run_text(job_id, uid, body.text, body.top_k, title))
    return {"job_id": job_id, "status": "processing"}


@router.post("/plagiarism-file-async")
async def plagiarism_file_async_ep(  # noqa: B008
    request: Request,
    file: UploadFile = File(...),  # noqa: B008
    top_k: int = 30,
) -> dict:
    """Versi async dari cek berkas; kembalikan `job_id` segera."""
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Berkas kosong.")
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413, detail=f"Berkas melebihi {MAX_UPLOAD_BYTES // (1024 * 1024)} MB."
        )
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
    job_id = create_job(uid, "plagiarism-checker", file.filename or "Cek Plagiarisme")
    _spawn(
        _job_run_file(
            job_id, uid, text, data, file.filename, is_pdf, min(max(top_k, 1), 60)
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
    base = (f.get("filename") or "laporan").rsplit(".", 1)[0]
    name = f"laporan-integritas-{base}.pdf"
    disp = "attachment" if dl else "inline"
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'{disp}; filename="{name}"'},
    )


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
        _log(request, "ai-detector", "AI Detector", body.text[:200], res)
        return res
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"Deteksi AI gagal: {exc}") from exc


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
        res = transcribe_audio(file.filename or "audio", data, language)
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
