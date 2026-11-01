"""Endpoint fitur ringan Fase 1."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.services.llm.tasks import grammar_check, humanize, paraphrase
from app.services.text_tools import analyze_text

router = APIRouter(prefix="/tools", tags=["tools"])

MAX_CHARS = 50_000


class TextIn(BaseModel):
    text: str = Field(..., min_length=1)


class ParaphraseIn(TextIn):
    style: str = Field(default="standar")


def _guard(text: str) -> None:
    if len(text) > MAX_CHARS:
        raise HTTPException(status_code=413, detail=f"Teks melebihi {MAX_CHARS} karakter.")


@router.post("/word-count")
def word_count(body: TextIn) -> dict:
    return analyze_text(body.text)


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
