"""Fitur ringan berbasis LLM: grammar check, paraphrase, humanize."""

from __future__ import annotations

from app.services.llm.provider import get_llm


def grammar_check(text: str) -> dict:
    llm = get_llm()
    messages = [
        {
            "role": "system",
            "content": (
                "Anda editor bahasa. Perbaiki ejaan, tata bahasa, dan tanda baca "
                "tanpa mengubah makna atau bahasa asli teks. Balas HANYA teks hasil "
                "perbaikan, tanpa penjelasan tambahan."
            ),
        },
        {"role": "user", "content": text},
    ]
    corrected = llm.chat(messages, temperature=0.1)
    return {"corrected": corrected}


def paraphrase(text: str, style: str = "standar") -> dict:
    llm = get_llm()
    messages = [
        {
            "role": "system",
            "content": (
                f"Parafrasekan teks pengguna dengan gaya '{style}', pertahankan makna "
                "dan bahasa aslinya. Balas HANYA hasil parafrase."
            ),
        },
        {"role": "user", "content": text},
    ]
    result = llm.chat(messages, temperature=0.7)
    return {"result": result, "style": style}


def humanize(text: str) -> dict:
    llm = get_llm()
    messages = [
        {
            "role": "system",
            "content": (
                "Tulis ulang teks agar terdengar lebih alami dan manusiawi: variasikan "
                "panjang kalimat, kurangi pola kaku, pertahankan makna dan bahasa asli. "
                "Balas HANYA hasil tulisan ulang."
            ),
        },
        {"role": "user", "content": text},
    ]
    result = llm.chat(messages, temperature=0.8)
    return {"result": result}
