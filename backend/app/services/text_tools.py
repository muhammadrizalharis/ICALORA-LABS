"""Word Count & metrik teks — murni Python, tanpa LLM (fitur paling ringan)."""

from __future__ import annotations

import re

_WORD_RE = re.compile(r"\b[\w'-]+\b", re.UNICODE)
_SENTENCE_RE = re.compile(r"[.!?]+(?:\s|$)")

# Singkatan umum (ID + EN) yang titiknya BUKAN akhir kalimat.
_ABBREV = {
    # gelar / sapaan Indonesia
    "dr", "drs", "dra", "ir", "prof", "hj", "h", "tn", "ny", "sdr", "sdri",
    "kpt", "kol", "jend", "letjen", "mayjen", "brigjen", "a.n", "u.p", "u.b",
    # gelar akademik (titik internal sudah ditangani pola M.Pd dsb.)
    "st", "se", "sh", "sp", "mt", "ma", "md",
    # kata singkatan Indonesia
    "dll", "dsb", "dst", "dkk", "yad", "yg", "tsb", "hal", "no", "jl", "gg", "rt", "rw",
    "kec", "kel", "kab", "prov", "pt", "cv", "ud", "tbk",
    # Inggris
    "mr", "mrs", "ms", "vs", "etc", "e.g", "i.e", "al", "fig", "eq", "vol",
    "pp", "ed", "eds", "cf", "ca", "approx", "dept", "univ", "inc", "ltd", "co",
    "jr", "sr", "phd",
}
# Pola yang titik-nya internal: desimal (3.14), inisial (A.), gelar (M.Pd),
# dan akronim bertitik (U.S.A). Titiknya dinetralkan sebelum hitung kalimat.
_DECIMAL_RE = re.compile(r"\d\.\d")
_INITIAL_RE = re.compile(r"\b[A-Z]\.")
_DOTTED_ABBR_RE = re.compile(r"\b(?:[A-Za-z]\.){2,}")
_ELLIPSIS_RE = re.compile(r"\.{2,}")

# Asumsi kecepatan rata-rata (kata per menit)
_READ_WPM = 200
_SPEAK_WPM = 130


def _count_sentences(text: str) -> int:
    """Hitung kalimat dengan mengabaikan titik pada singkatan/desimal/inisial."""
    if not text.strip():
        return 0
    masked = text
    # Netralkan elipsis, desimal, inisial, akronim bertitik.
    masked = _ELLIPSIS_RE.sub("\0", masked)
    masked = _DECIMAL_RE.sub(lambda m: m.group(0).replace(".", "\0"), masked)
    masked = _DOTTED_ABBR_RE.sub(lambda m: m.group(0).replace(".", "\0"), masked)
    masked = _INITIAL_RE.sub(lambda m: m.group(0).replace(".", "\0"), masked)

    # Netralkan titik tepat setelah kata singkatan dikenal.
    def _mask_abbrev(m: re.Match) -> str:
        word = m.group(1)
        if word.lower().strip(".") in _ABBREV:
            return word + "\0"
        return m.group(0)

    masked = re.sub(r"\b([A-Za-z]+)\.", _mask_abbrev, masked)

    sentences = [s for s in _SENTENCE_RE.split(masked) if s.strip()]
    return max(len(sentences), 1)


def analyze_text(text: str) -> dict:
    words = _WORD_RE.findall(text)
    word_count = len(words)
    char_count = len(text)
    char_count_no_spaces = len(re.sub(r"\s", "", text))
    sentence_count = _count_sentences(text)
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
