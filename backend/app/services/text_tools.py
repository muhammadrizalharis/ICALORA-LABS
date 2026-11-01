"""Word Count & metrik teks — murni Python, tanpa LLM (fitur paling ringan)."""

from __future__ import annotations

import re

_WORD_RE = re.compile(r"\b[\w'-]+\b", re.UNICODE)
_SENTENCE_RE = re.compile(r"[.!?]+(?:\s|$)")

# Asumsi kecepatan rata-rata (kata per menit)
_READ_WPM = 200
_SPEAK_WPM = 130


def analyze_text(text: str) -> dict:
    words = _WORD_RE.findall(text)
    word_count = len(words)
    char_count = len(text)
    char_count_no_spaces = len(re.sub(r"\s", "", text))
    sentences = [s for s in _SENTENCE_RE.split(text) if s.strip()]
    sentence_count = max(len(sentences), 1 if text.strip() else 0)
    paragraphs = [p for p in re.split(r"\n\s*\n", text) if p.strip()]

    reading_seconds = round(word_count / _READ_WPM * 60) if word_count else 0
    speaking_seconds = round(word_count / _SPEAK_WPM * 60) if word_count else 0

    return {
        "characters": char_count,
        "characters_no_spaces": char_count_no_spaces,
        "words": word_count,
        "sentences": sentence_count,
        "paragraphs": len(paragraphs),
        "reading_time_seconds": reading_seconds,
        "speaking_time_seconds": speaking_seconds,
    }
