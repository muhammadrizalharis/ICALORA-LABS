"""Cek Hidden Text & Typo.

Mendeteksi teks tersembunyi / manipulatif yang umum dipakai untuk mengelabui
pemeriksa plagiarisme atau pembaca, serta potensi salah ketik:

  * Karakter zero-width / tak terlihat (ZWSP, ZWNJ, ZWJ, BOM, dll.)
  * Spasi/garis non-standar (NBSP, spasi tipis, dsb.)
  * Homoglyph Cyrillic/Yunani yang menyerupai huruf Latin.
  * Kontrol bidi (RLO/LRO) yang dapat menyamarkan teks.
  * Potensi typo via LLM (opsional, tidak memblokir bila gagal).
"""

from __future__ import annotations

import unicodedata

# Karakter tak terlihat / zero-width yang mencurigakan.
_INVISIBLE = {
    "\u200b": "ZERO WIDTH SPACE",
    "\u200c": "ZERO WIDTH NON-JOINER",
    "\u200d": "ZERO WIDTH JOINER",
    "\u2060": "WORD JOINER",
    "\u2061": "FUNCTION APPLICATION",
    "\u2062": "INVISIBLE TIMES",
    "\u2063": "INVISIBLE SEPARATOR",
    "\u2064": "INVISIBLE PLUS",
    "\ufeff": "ZERO WIDTH NO-BREAK SPACE (BOM)",
    "\u00ad": "SOFT HYPHEN",
    "\u034f": "COMBINING GRAPHEME JOINER",
    "\u180e": "MONGOLIAN VOWEL SEPARATOR",
    "\u115f": "HANGUL CHOSEONG FILLER",
    "\u1160": "HANGUL JUNGSEONG FILLER",
    "\u3164": "HANGUL FILLER",
    "\uffa0": "HALFWIDTH HANGUL FILLER",
    "\u17b4": "KHMER VOWEL INHERENT AQ",
    "\u17b5": "KHMER VOWEL INHERENT AA",
}

# Kontrol arah teks (bidi) yang bisa menyamarkan isi — termasuk penanda &
# penutup serangan "Trojan Source" (mark/override/isolate + pop).
_BIDI = {
    "\u200e": "LEFT-TO-RIGHT MARK",
    "\u200f": "RIGHT-TO-LEFT MARK",
    "\u061c": "ARABIC LETTER MARK",
    "\u202a": "LEFT-TO-RIGHT EMBEDDING",
    "\u202b": "RIGHT-TO-LEFT EMBEDDING",
    "\u202c": "POP DIRECTIONAL FORMATTING",
    "\u202d": "LEFT-TO-RIGHT OVERRIDE",
    "\u202e": "RIGHT-TO-LEFT OVERRIDE",
    "\u2066": "LEFT-TO-RIGHT ISOLATE",
    "\u2067": "RIGHT-TO-LEFT ISOLATE",
    "\u2068": "FIRST STRONG ISOLATE",
    "\u2069": "POP DIRECTIONAL ISOLATE",
}

# Spasi non-standar.
_ODD_SPACES = {
    "\u00a0": "NO-BREAK SPACE",
    "\u2007": "FIGURE SPACE",
    "\u202f": "NARROW NO-BREAK SPACE",
    "\u2009": "THIN SPACE",
    "\u200a": "HAIR SPACE",
    "\u3000": "IDEOGRAPHIC SPACE",
}

# Homoglyph umum (Cyrillic/Yunani) -> Latin yang menyerupainya.
_HOMOGLYPHS = {
    "\u0430": "a", "\u0435": "e", "\u043e": "o", "\u0440": "p", "\u0441": "c",
    "\u0443": "y", "\u0445": "x", "\u0456": "i", "\u0410": "A", "\u0412": "B",
    "\u0415": "E", "\u041a": "K", "\u041c": "M", "\u041d": "H", "\u041e": "O",
    "\u0420": "P", "\u0421": "C", "\u0422": "T", "\u0425": "X",
    "\u0391": "A", "\u0392": "B", "\u0395": "E", "\u0396": "Z", "\u0397": "H",
    "\u0399": "I", "\u039a": "K", "\u039c": "M", "\u039d": "N", "\u039f": "O",
    "\u03a1": "P", "\u03a4": "T", "\u03a7": "X",
}


def _find(text: str, table: dict[str, str], category: str) -> list[dict]:
    hits: list[dict] = []
    for idx, ch in enumerate(text):
        if ch in table:
            hits.append(
                {
                    "category": category,
                    "char": table[ch],
                    "codepoint": f"U+{ord(ch):04X}",
                    "position": idx,
                }
            )
    return hits


def _llm_typos(text: str) -> list[dict]:
    from app.services.llm.provider import get_llm
    from app.services.llm.tasks import _extract_json

    llm = get_llm()
    messages = [
        {
            "role": "system",
            "content": (
                "Temukan salah ketik/ejaan dalam teks pengguna (maks 25). Balas HANYA JSON: "
                '{"typos": [{"wrong": "<kata salah>", "suggestion": "<koreksi>"}]}'
            ),
        },
        {"role": "user", "content": text[:6000]},
    ]
    raw = llm.chat(messages, temperature=0.1, max_tokens=800)
    try:
        data = _extract_json(raw)
        items = data.get("typos", []) if isinstance(data, dict) else []
        return [t for t in items if isinstance(t, dict) and t.get("wrong")][:25]
    except Exception:  # noqa: BLE001
        return []


def check_hidden_text(text: str, check_typos: bool = True) -> dict:
    """Pindai teks untuk karakter tersembunyi/mencurigakan dan typo."""
    invisible = _find(text, _INVISIBLE, "invisible")
    bidi = _find(text, _BIDI, "bidi_control")
    odd_spaces = _find(text, _ODD_SPACES, "odd_space")
    homoglyphs = _find(text, _HOMOGLYPHS, "homoglyph")

    # Karakter kontrol/format/pemisah baris lain yang tak tertangani tabel di
    # atas: kategori Unicode Cc (kontrol), Cf (format tak terlihat), Zl/Zp
    # (pemisah baris/paragraf U+2028/U+2029). Dulu hanya Cc yang terdeteksi,
    # sehingga banyak karakter format tersembunyi lolos sebagai "bersih".
    _known = set(_INVISIBLE) | set(_BIDI) | set(_ODD_SPACES)
    control = [
        {
            "category": "control",
            "char": unicodedata.name(ch, "UNKNOWN"),
            "codepoint": f"U+{ord(ch):04X}",
            "position": idx,
        }
        for idx, ch in enumerate(text)
        if ch not in _known
        and ch not in "\n\r\t"
        and unicodedata.category(ch) in {"Cc", "Cf", "Zl", "Zp"}
    ]

    findings = invisible + bidi + odd_spaces + homoglyphs + control
    typos: list[dict] = []
    if check_typos and len(text.split()) >= 3:
        try:
            typos = _llm_typos(text)
        except Exception:  # noqa: BLE001, S110
            typos = []

    # Teks bersih: buang karakter tersembunyi, PETAKAN homoglyph → Latin, dan
    # buang kontrol/format lain (Cc/Cf/Zl/Zp) agar hasil benar-benar bersih
    # untuk analisis ulang (dulu homoglyph & kontrol masih tersisa).
    drop = set(_INVISIBLE) | set(_BIDI)
    out_chars: list[str] = []
    for c in text:
        if c in drop:
            continue
        if c in _HOMOGLYPHS:
            out_chars.append(_HOMOGLYPHS[c])
            continue
        if c in _ODD_SPACES:
            out_chars.append(" ")
            continue
        if c not in "\n\r\t" and unicodedata.category(c) in {"Cc", "Cf", "Zl", "Zp"}:
            continue
        out_chars.append(c)
    cleaned = "".join(out_chars)

    risk = "bersih"
    if invisible or bidi or homoglyphs:
        risk = "tinggi"
    elif odd_spaces or control:
        risk = "sedang"

    return {
        "risk": risk,
        "total_hidden": len(findings),
        "counts": {
            "invisible": len(invisible),
            "bidi_control": len(bidi),
            "odd_space": len(odd_spaces),
            "homoglyph": len(homoglyphs),
            "control": len(control),
        },
        "findings": findings[:200],
        "typos": typos,
        "cleaned_text": cleaned,
        "note": (
            "Karakter tak terlihat & homoglyph sering dipakai untuk mengelabui "
            "pemeriksa plagiarisme. Gunakan 'teks bersih' untuk analisis ulang."
        ),
    }
