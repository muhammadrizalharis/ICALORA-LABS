"""Authorship — analisis gaya penulisan (stylometry) & perbandingan kepenulisan.

Menghitung ciri gaya terukur (panjang kalimat, keragaman kosakata, kata fungsi,
tanda baca, keterbacaan). Dapat juga membandingkan dua teks untuk mengestimasi
kemiripan gaya (indikasi penulis sama) via cosine pada vektor ciri.
"""

from __future__ import annotations

import math
import re

_WORD_RE = re.compile(r"\b[\w'-]+\b", re.UNICODE)
_SENT_RE = re.compile(r"[^.!?]+[.!?]*")

# Kata fungsi (ID + EN) — penanda gaya yang kuat dalam stylometry
_FUNCTION_WORDS = [
    "yang", "dan", "di", "ke", "dari", "untuk", "dengan", "pada", "adalah",
    "ini", "itu", "tidak", "akan", "atau", "karena", "sebagai", "oleh",
    "the", "and", "of", "to", "in", "a", "is", "that", "for", "with", "as",
]


def _syllables_id(word: str) -> int:
    return max(1, len(re.findall(r"[aeiouAEIOU]", word)))


def _stylometry(text: str) -> dict:
    words = _WORD_RE.findall(text)
    sents = [s.strip() for s in _SENT_RE.findall(text) if s.strip()]
    n_words = len(words)
    n_sents = max(len(sents), 1)
    lower = [w.lower() for w in words]

    sent_lengths = [len(_WORD_RE.findall(s)) for s in sents] or [0]
    mean_sl = sum(sent_lengths) / len(sent_lengths)
    var_sl = sum((x - mean_sl) ** 2 for x in sent_lengths) / len(sent_lengths)

    word_lengths = [len(w) for w in words] or [0]
    mean_wl = sum(word_lengths) / len(word_lengths)

    ttr = len(set(lower)) / n_words if n_words else 0.0
    hapax = sum(1 for w in set(lower) if lower.count(w) == 1)
    hapax_ratio = hapax / n_words if n_words else 0.0

    total_syll = sum(_syllables_id(w) for w in words) or 1
    # Flesch Reading Ease (perkiraan, netral bahasa)
    flesch = 206.835 - 1.015 * (n_words / n_sents) - 84.6 * (total_syll / max(n_words, 1))

    punct = {
        "koma": text.count(","),
        "titik": text.count("."),
        "titik_koma": text.count(";"),
        "tanda_tanya": text.count("?"),
        "tanda_seru": text.count("!"),
        "tanda_kutip": text.count('"') + text.count("'"),
    }

    fw_freq = {
        w: round(lower.count(w) / n_words * 100, 2) for w in _FUNCTION_WORDS if lower.count(w)
    }
    fw_freq = dict(sorted(fw_freq.items(), key=lambda x: x[1], reverse=True)[:10])

    return {
        "word_count": n_words,
        "sentence_count": len(sents),
        "avg_sentence_length": round(mean_sl, 2),
        "sentence_length_std": round(math.sqrt(var_sl), 2),
        "avg_word_length": round(mean_wl, 2),
        "type_token_ratio": round(ttr, 3),
        "hapax_ratio": round(hapax_ratio, 3),
        "readability_flesch": round(flesch, 1),
        "punctuation": punct,
        "top_function_words": fw_freq,
    }


def _feature_vector(s: dict) -> list[float]:
    return [
        s["avg_sentence_length"],
        s["sentence_length_std"],
        s["avg_word_length"],
        s["type_token_ratio"] * 100,
        s["hapax_ratio"] * 100,
        s["readability_flesch"],
    ]


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=False))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


def analyze_authorship(text: str, compare: str | None = None) -> dict:
    text = text.strip()
    result: dict = {"profile": _stylometry(text)}
    if compare and compare.strip():
        prof_b = _stylometry(compare.strip())
        sim = _cosine(_feature_vector(result["profile"]), _feature_vector(prof_b))
        sim_pct = round(sim * 100, 1)
        if sim_pct >= 92:
            verdict = "gaya sangat mirip (kemungkinan penulis sama)"
        elif sim_pct >= 80:
            verdict = "gaya mirip"
        else:
            verdict = "gaya berbeda (kemungkinan penulis berbeda)"
        result["comparison"] = {
            "profile_b": prof_b,
            "style_similarity": sim_pct,
            "verdict": verdict,
        }
    return result
