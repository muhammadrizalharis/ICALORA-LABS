"""Endpoint fitur ringan Fase 1."""

from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel, Field

from app.services.ai_detector import detect_ai
from app.services.authorship import analyze_authorship
from app.services.citation import find_citations
from app.services.file_extract import MAX_UPLOAD_BYTES, extract_text
from app.services.llm.tasks import (
    build_resume,
    chat,
    grade_essay,
    grammar_check,
    humanize,
    paraphrase,
    reader_reactions,
    rewrite,
)
from app.services.plagiarism import check_plagiarism
from app.services.text_tools import analyze_text

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


def _guard(text: str) -> None:
    if len(text) > MAX_CHARS:
        raise HTTPException(status_code=413, detail=f"Teks melebihi {MAX_CHARS} karakter.")


@router.post("/word-count")
def word_count(body: TextIn) -> dict:
    return analyze_text(body.text)


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
def grammar(body: TextIn) -> dict:
    _guard(body.text)
    try:
        return grammar_check(body.text)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"LLM gagal: {exc}") from exc


@router.post("/paraphrase")
def paraphrase_ep(body: ParaphraseIn) -> dict:
    _guard(body.text)
    try:
        return paraphrase(body.text, body.style)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"LLM gagal: {exc}") from exc


@router.post("/humanize")
def humanize_ep(body: TextIn) -> dict:
    _guard(body.text)
    try:
        return humanize(body.text)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"LLM gagal: {exc}") from exc


@router.post("/plagiarism")
def plagiarism_ep(body: PlagiarismIn) -> dict:
    _guard(body.text)
    try:
        return check_plagiarism(body.text, body.top_k)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"Cek plagiarisme gagal: {exc}") from exc


@router.post("/rewrite")
def rewrite_ep(body: RewriteIn) -> dict:
    _guard(body.text)
    try:
        return rewrite(body.text, body.tone)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"LLM gagal: {exc}") from exc


@router.post("/chat")
def chat_ep(body: ChatIn) -> dict:
    total = sum(len(m.content) for m in body.messages)
    if total > MAX_CHARS:
        raise HTTPException(status_code=413, detail=f"Percakapan melebihi {MAX_CHARS} karakter.")
    try:
        return chat([m.model_dump() for m in body.messages], body.system)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"LLM gagal: {exc}") from exc


@router.post("/grade")
def grade_ep(body: GradeIn) -> dict:
    _guard(body.text)
    try:
        return grade_essay(body.text, body.rubric)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"LLM gagal: {exc}") from exc


@router.post("/reader-reactions")
def reader_reactions_ep(body: TextIn) -> dict:
    _guard(body.text)
    try:
        return reader_reactions(body.text)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"LLM gagal: {exc}") from exc


@router.post("/resume")
def resume_ep(body: ResumeIn) -> dict:
    if len(body.info) > MAX_CHARS:
        raise HTTPException(status_code=413, detail=f"Teks melebihi {MAX_CHARS} karakter.")
    try:
        return build_resume(body.info, body.target_role)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"LLM gagal: {exc}") from exc


@router.post("/citations")
def citations_ep(body: CitationIn) -> dict:
    _guard(body.text)
    try:
        return find_citations(body.text, body.top_k)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"Pencarian sitasi gagal: {exc}") from exc


@router.post("/ai-detect")
def ai_detect_ep(body: TextIn) -> dict:
    _guard(body.text)
    try:
        return detect_ai(body.text)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"Deteksi AI gagal: {exc}") from exc


@router.post("/authorship")
def authorship_ep(body: AuthorshipIn) -> dict:
    _guard(body.text)
    try:
        return analyze_authorship(body.text, body.compare)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"Analisis kepenulisan gagal: {exc}") from exc
