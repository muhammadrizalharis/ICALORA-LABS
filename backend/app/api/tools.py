"""Endpoint fitur ringan Fase 1."""

from fastapi import APIRouter, File, HTTPException, Request, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, Field

from app.services.ai_detector import detect_ai
from app.services.auth import optional_user_from_request, record_history
from app.services.authorship import analyze_authorship
from app.services.citation import find_citations
from app.services.file_extract import MAX_UPLOAD_BYTES, extract_text
from app.services.hidden_text import check_hidden_text
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
from app.services.publikasi import recommend_journals
from app.services.report import MAX_HTML_BYTES, render_pdf
from app.services.text_tools import analyze_text
from app.services.transkrip import (
    MAX_AUDIO_BYTES,
    is_supported,
    transcribe_audio,
)

router = APIRouter(prefix="/tools", tags=["tools"])

MAX_CHARS = 50_000


class TextIn(BaseModel):
    text: str = Field(..., min_length=1)


class ParaphraseIn(TextIn):
    style: str = Field(default="standar")


class PlagiarismIn(TextIn):
    top_k: int = Field(default=10, ge=1, le=50)


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
    top_k: int = Field(default=8, ge=1, le=30)


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
    top_k: int = Field(default=10, ge=1, le=30)


def _guard(text: str) -> None:
    if len(text) > MAX_CHARS:
        raise HTTPException(status_code=413, detail=f"Teks melebihi {MAX_CHARS} karakter.")


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


@router.post("/plagiarism")
def plagiarism_ep(body: PlagiarismIn, request: Request) -> dict:
    _guard(body.text)
    try:
        res = check_plagiarism(body.text, body.top_k)
        _log(request, "plagiarism-checker", "Cek Plagiarisme", body.text[:200], res)
        return res
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"Cek plagiarisme gagal: {exc}") from exc


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
        raise HTTPException(status_code=413, detail=f"Percakapan melebihi {MAX_CHARS} karakter.")
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
        raise HTTPException(status_code=413, detail=f"Teks melebihi {MAX_CHARS} karakter.")
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
