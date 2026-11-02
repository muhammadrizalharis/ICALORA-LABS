"""Fitur ringan berbasis LLM: grammar, paraphrase, humanize, rewrite,
chat, grader, reader-reactions, resume-builder."""

from __future__ import annotations

import json
import re

from app.services.llm.provider import get_llm

_JSON_RE = re.compile(r"\{.*\}|\[.*\]", re.DOTALL)


def _extract_json(raw: str):
    """Ambil blok JSON pertama dari balasan LLM (toleran terhadap teks tambahan)."""
    raw = raw.strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw, flags=re.IGNORECASE).strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        m = _JSON_RE.search(raw)
        if m:
            return json.loads(m.group(0))
        raise


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


# Gaya penulisan ulang yang didukung AI Rewriter
REWRITE_TONES = {
    "formal": "formal dan profesional",
    "akademik": "akademik dan ilmiah",
    "kasual": "santai dan ramah",
    "ringkas": "ringkas dan padat",
    "persuasif": "persuasif dan meyakinkan",
    "sederhana": "sederhana dan mudah dipahami",
}


def rewrite(text: str, tone: str = "formal") -> dict:
    """AI Rewriter: rombak gaya tulisan sesuai nada yang dipilih."""
    desc = REWRITE_TONES.get(tone, REWRITE_TONES["formal"])
    llm = get_llm()
    messages = [
        {
            "role": "system",
            "content": (
                f"Tulis ulang teks pengguna dengan gaya {desc}. Pertahankan makna inti "
                "dan bahasa asli teks. Balas HANYA hasil tulisan ulang tanpa penjelasan."
            ),
        },
        {"role": "user", "content": text},
    ]
    result = llm.chat(messages, temperature=0.7)
    return {"result": result, "tone": tone}


def chat(messages: list[dict], system: str | None = None) -> dict:
    """AI Chat: asisten tulis akademik multi-giliran berbasis LLM lokal."""
    llm = get_llm()
    sys_prompt = system or (
        "Anda adalah asisten penulisan akademik ICALORA-LABS. Jawab dengan jelas, "
        "akurat, dan dalam bahasa yang sama dengan pengguna. Bantu menulis, merangkum, "
        "menjelaskan, dan menyusun argumen secara ilmiah."
    )
    convo = [{"role": "system", "content": sys_prompt}]
    for m in messages[-20:]:
        role = m.get("role")
        content = (m.get("content") or "").strip()
        if role in ("user", "assistant") and content:
            convo.append({"role": role, "content": content})
    reply = llm.chat(convo, temperature=0.5, max_tokens=1024)
    return {"reply": reply}


def grade_essay(text: str, rubric: str | None = None) -> dict:
    """AI Grader: nilai esai dengan rubrik otomatis (0-100 per kriteria)."""
    llm = get_llm()
    rubric_line = (
        f"Gunakan rubrik khusus berikut: {rubric}."
        if rubric
        else "Gunakan rubrik umum: Isi & Argumen, Struktur & Organisasi, "
        "Tata Bahasa & Gaya, Orisinalitas & Kedalaman."
    )
    messages = [
        {
            "role": "system",
            "content": (
                "Anda penilai esai akademik. " + rubric_line + " Nilai esai pengguna. "
                "Balas HANYA JSON valid dengan bentuk: "
                '{"overall_score": <0-100>, "grade": "<A/B/C/D/E>", '
                '"criteria": [{"name": "<nama>", "score": <0-100>, '
                '"feedback": "<umpan balik singkat>"}], '
                '"summary": "<ringkasan evaluasi 1-2 kalimat>", '
                '"suggestions": ["<saran perbaikan>", ...]}'
            ),
        },
        {"role": "user", "content": text},
    ]
    raw = llm.chat(messages, temperature=0.2, max_tokens=1200)
    try:
        data = _extract_json(raw)
    except json.JSONDecodeError:
        return {
            "overall_score": None,
            "grade": None,
            "criteria": [],
            "summary": raw[:500],
            "suggestions": [],
        }
    return data


def reader_reactions(text: str) -> dict:
    """Reader Reactions: prediksi reaksi beberapa persona pembaca."""
    llm = get_llm()
    messages = [
        {
            "role": "system",
            "content": (
                "Prediksi bagaimana beragam pembaca akan bereaksi terhadap teks pengguna. "
                "Balas HANYA JSON valid: "
                '{"reactions": [{"persona": "<tipe pembaca>", '
                '"reaction": "<reaksi singkat>", "sentiment": "<positif/netral/negatif>"}], '
                '"overall_sentiment": "<positif/netral/negatif>", '
                '"clarity_score": <0-100>, "engagement_score": <0-100>, '
                '"summary": "<ringkasan 1 kalimat>"}'
            ),
        },
        {"role": "user", "content": text},
    ]
    raw = llm.chat(messages, temperature=0.4, max_tokens=900)
    try:
        return _extract_json(raw)
    except json.JSONDecodeError:
        return {
            "reactions": [],
            "overall_sentiment": None,
            "clarity_score": None,
            "engagement_score": None,
            "summary": raw[:500],
        }


def build_resume(info: str, target_role: str | None = None) -> dict:
    """Resume Builder: susun CV profesional (Markdown) dari informasi mentah."""
    llm = get_llm()
    role_line = f" Sesuaikan untuk posisi: {target_role}." if target_role else ""
    messages = [
        {
            "role": "system",
            "content": (
                "Anda penulis CV profesional. Dari informasi pengguna, susun CV yang rapi "
                "dalam format Markdown (judul nama, kontak, Ringkasan, Pengalaman, "
                "Pendidikan, Keahlian, dll. jika tersedia). Gunakan bahasa yang sama dengan "
                "pengguna. Jangan mengarang data yang tidak diberikan." + role_line + " "
                "Balas HANYA isi CV dalam Markdown."
            ),
        },
        {"role": "user", "content": info},
    ]
    result = llm.chat(messages, temperature=0.4, max_tokens=1200)
    return {"resume_markdown": result, "target_role": target_role}
