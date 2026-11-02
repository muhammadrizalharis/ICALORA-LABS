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
    "\ufeff": "ZERO WIDTH NO-BREAK SPACE (BOM)",
    "\u00ad": "SOFT HYPHEN",
    "\u180e": "MONGOLIAN VOWEL SEPARATOR",
}

# Kontrol arah teks (bidi) yang bisa menyamarkan isi.
_BIDI = {
    "\u202a": "LEFT-TO-RIGHT EMBEDDING",
    "\u202b": "RIGHT-TO-LEFT EMBEDDING",
    "\u202d": "LEFT-TO-RIGHT OVERRIDE",
    "\u202e": "RIGHT-TO-LEFT OVERRIDE",
    "\u2066": "LEFT-TO-RIGHT ISOLATE",
    "\u2067": "RIGHT-TO-LEFT ISOLATE",
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

    # Karakter kontrol lain (selain newline/tab).
    control = [
        {
            "category": "control",
            "char": unicodedata.name(ch, "UNKNOWN"),
            "codepoint": f"U+{ord(ch):04X}",
            "position": idx,
        }
        for idx, ch in enumerate(text)
        if unicodedata.category(ch) == "Cc" and ch not in "\n\r\t"
    ]

    findings = invisible + bidi + odd_spaces + homoglyphs + control
    typos: list[dict] = []
    if check_typos and len(text.split()) >= 3:
        try:
            typos = _llm_typos(text)
        except Exception:  # noqa: BLE001, S110
            typos = []

    # Teks bersih (karakter tersembunyi dihapus).
    drop = set(_INVISIBLE) | set(_BIDI)
    cleaned = "".join(c for c in text if c not in drop)
    for src in _ODD_SPACES:
        cleaned = cleaned.replace(src, " ")

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
