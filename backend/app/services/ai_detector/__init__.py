"""AI Detector — estimasi probabilitas teks dihasilkan AI.

Pendekatan jujur (bukan klaim 100% akurat): gabungan sinyal statistik gaya
tulisan + penilaian LLM. Teks AI cenderung punya "burstiness" rendah (variasi
panjang kalimat kecil), keberagaman kosakata moderat-seragam, dan sedikit
penanda personal. Semua sinyal digabung jadi skor indikatif.
"""

from __future__ import annotations

import math
import re

from app.services.llm.provider import get_llm

_WORD_RE = re.compile(r"\b[\w'-]+\b", re.UNICODE)
_SENT_RE = re.compile(r"[^.!?]+[.!?]*")


def _sentences(text: str) -> list[str]:
    return [s.strip() for s in _SENT_RE.findall(text) if s.strip()]


def _burstiness(sent_lengths: list[int]) -> float:
    """Koefisien variasi panjang kalimat (tinggi = lebih manusiawi)."""
    n = len(sent_lengths)
    if n < 2:
        return 0.0
    mean = sum(sent_lengths) / n
    if mean == 0:
        return 0.0
    var = sum((x - mean) ** 2 for x in sent_lengths) / n
    return math.sqrt(var) / mean


def _type_token_ratio(words: list[str]) -> float:
    if not words:
        return 0.0
    return len({w.lower() for w in words}) / len(words)


def _statistical_signals(text: str) -> dict:
    words = _WORD_RE.findall(text)
    sents = _sentences(text)
    sent_lengths = [len(_WORD_RE.findall(s)) for s in sents] or [0]

    burst = _burstiness(sent_lengths)
    ttr = _type_token_ratio(words)
    avg_len = sum(sent_lengths) / len(sent_lengths)
    # variasi panjang kalimat rendah -> indikasi AI
    len_uniformity = 1.0 - min(burst / 0.6, 1.0)
    # TTR sangat rendah (repetitif) sedikit menaikkan skor
    repetition = 1.0 - min(ttr / 0.5, 1.0)

    stat_score = max(0.0, min(1.0, 0.65 * len_uniformity + 0.35 * repetition))
    return {
        "burstiness": round(burst, 3),
        "type_token_ratio": round(ttr, 3),
        "avg_sentence_length": round(avg_len, 1),
        "sentence_count": len(sents),
        "word_count": len(words),
        "stat_score": round(stat_score, 3),
    }


def _llm_judgment(text: str) -> float | None:
    """Minta LLM menilai 0-100 kemungkinan teks ditulis AI."""
    import json

    llm = get_llm()
    messages = [
        {
            "role": "system",
            "content": (
                "Nilai kemungkinan teks berikut ditulis oleh AI (model bahasa) "
                "dibanding manusia. Pertimbangkan keseragaman, klise, dan kurangnya "
                'suara personal. Balas HANYA JSON: {"ai_probability": <0-100>}'
            ),
        },
        {"role": "user", "content": text[:6000]},
    ]
    try:
        raw = llm.chat(messages, temperature=0.0, max_tokens=60).strip()
        raw = re.sub(r"^```(?:json)?|```$", "", raw).strip()
        m = re.search(r"\{.*\}", raw, re.DOTALL)
        data = json.loads(m.group(0) if m else raw)
        val = float(data.get("ai_probability"))
        return max(0.0, min(100.0, val))
    except Exception:  # noqa: BLE001
        return None


def detect_ai(text: str) -> dict:
    text = text.strip()
    words = _WORD_RE.findall(text)
    if len(words) < 20:
        return {
            "ai_probability": None,
            "verdict": "tidak cukup teks",
            "note": "Butuh minimal ~20 kata untuk analisis yang bermakna.",
            "signals": _statistical_signals(text),
        }

    signals = _statistical_signals(text)
    stat_pct = signals["stat_score"] * 100
    llm_pct = _llm_judgment(text)

    if llm_pct is None:
        final = stat_pct
    else:
        final = 0.45 * stat_pct + 0.55 * llm_pct

    final = round(max(0.0, min(100.0, final)), 1)
    if final >= 70:
        verdict = "kemungkinan besar AI"
    elif final >= 45:
        verdict = "campuran / tidak pasti"
    else:
        verdict = "kemungkinan besar manusia"

    return {
        "ai_probability": final,
        "verdict": verdict,
        "stat_probability": round(stat_pct, 1),
        "llm_probability": round(llm_pct, 1) if llm_pct is not None else None,
        "signals": signals,
        "note": (
            "Hasil bersifat indikatif, bukan bukti absolut. Deteksi AI tidak pernah "
            "100% akurat; gunakan sebagai pertimbangan, bukan vonis."
        ),
    }
