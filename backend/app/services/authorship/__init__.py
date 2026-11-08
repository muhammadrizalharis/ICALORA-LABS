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

# Kata fungsi (ID + EN) — penanda gaya kuat dalam stylometry. Mencakup kata
# ganti, kata bantu, preposisi, konjungsi, dan partikel yang dipakai di luar
# kesadaran penulis & relatif tak bergantung topik.
_FUNCTION_WORDS = [
    # Indonesia
    "yang", "dan", "di", "ke", "dari", "untuk", "dengan", "pada", "adalah",
    "ini", "itu", "tidak", "akan", "atau", "karena", "sebagai", "oleh",
    "saya", "aku", "kita", "kami", "dia", "mereka", "kamu", "anda", "nya",
    "juga", "sudah", "telah", "masih", "bisa", "dapat", "harus", "agar",
    "jika", "namun", "tetapi", "serta", "dalam", "tersebut", "ialah",
    # Inggris
    "the", "and", "of", "to", "in", "a", "is", "that", "for", "with", "as",
    "i", "you", "he", "she", "it", "we", "they", "me", "my", "your", "his",
    "her", "its", "our", "their", "this", "these", "those", "was", "were",
    "be", "been", "are", "am", "have", "has", "had", "do", "does", "did",
    "not", "but", "or", "if", "so", "than", "then", "on", "at", "by", "an",
    "from", "which", "who", "what", "when", "there", "would", "could", "should",
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


# Skala referensi (perkiraan simpangan baku prosa umum) untuk menormalkan tiap
# fitur struktural sebelum cosine — agar tiap ciri berkontribusi setara dan
# cosine mengukur "bentuk gaya", bukan sekadar didominasi nilai terbesar (flesch).
_STRUCT_SCALE = [10.0, 8.0, 1.0, 15.0, 15.0, 30.0]


def _struct_vector_norm(s: dict) -> list[float]:
    return [v / sc for v, sc in zip(_feature_vector(s), _STRUCT_SCALE, strict=False)]


def _fw_vector(text: str) -> list[float]:
    """Vektor frekuensi kata fungsi (per 100 kata) atas daftar tetap.

    Kata fungsi (the/and/yang/dan/…) adalah penanda kepenulisan terkuat dalam
    stilometri karena dipakai di luar kesadaran penulis dan tak bergantung topik.
    """
    words = [w.lower() for w in _WORD_RE.findall(text)]
    n = len(words) or 1
    counts = {w: 0 for w in _FUNCTION_WORDS}
    for w in words:
        if w in counts:
            counts[w] += 1
    return [counts[w] / n * 100.0 for w in _FUNCTION_WORDS]


def _fw_similarity(a: str, b: str) -> float:
    """Kemiripan distribusi kata fungsi via cosine vektor frekuensi (0..1).

    Cosine stabil pada daftar kata fungsi yang kaya (kata ganti, kata bantu,
    preposisi, konjungsi): penulis berbeda memakai kata fungsi dengan proporsi
    berbeda sehingga sudut antar-vektor melebar.
    """
    return _cosine(_fw_vector(a), _fw_vector(b))


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
        comp = compare.strip()
        prof_b = _stylometry(comp)
        # Dua sinyal digabung: (1) distribusi kata fungsi — penanda kepenulisan
        # terkuat; (2) ciri struktural ternormalisasi. Bobot condong ke kata
        # fungsi karena paling diskriminatif & tak bergantung topik.
        fw_sim = _fw_similarity(text, comp)
        struct_sim = _cosine(_struct_vector_norm(result["profile"]), _struct_vector_norm(prof_b))
        sim = 0.5 * fw_sim + 0.5 * struct_sim
        sim_pct = round(sim * 100, 1)
        # Kepercayaan bergantung panjang sampel: di bawah ~300 kata, frekuensi
        # kata fungsi belum stabil -> hasil hanya indikatif.
        min_words = min(result["profile"]["word_count"], prof_b["word_count"])
        if min_words >= 300:
            confidence = "tinggi"
        elif min_words >= 120:
            confidence = "sedang"
        else:
            confidence = "rendah"
        if sim_pct >= 85:
            verdict = "gaya sangat mirip (kemungkinan penulis sama)"
        elif sim_pct >= 70:
            verdict = "gaya mirip (tidak konklusif)"
        else:
            verdict = "gaya berbeda (kemungkinan penulis berbeda)"
        if confidence == "rendah":
            verdict += " — kepercayaan rendah (sampel terlalu pendek)"
        result["comparison"] = {
            "profile_b": prof_b,
            "style_similarity": sim_pct,
            "function_word_similarity": round(fw_sim * 100, 1),
            "structural_similarity": round(struct_sim * 100, 1),
            "confidence": confidence,
            "verdict": verdict,
            "note": (
                "Stilometri bersifat indikatif, bukan bukti. Butuh sampel cukup "
                "panjang (idealnya >300 kata) agar frekuensi kata fungsi stabil; "
                "register yang sama (mis. sama-sama formal) dapat menaikkan "
                "kemiripan meski penulis berbeda."
            ),
        }
    return result
