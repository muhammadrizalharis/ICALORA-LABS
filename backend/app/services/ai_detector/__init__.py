"""AI Detector — estimasi probabilitas teks dihasilkan AI.

Pendekatan jujur (bukan klaim 100% akurat): gabungan sinyal statistik gaya
tulisan + penilaian LLM, plus penyorotan kalimat yang paling "mirip AI".
Teks AI cenderung punya "burstiness" rendah (variasi panjang kalimat kecil),
keberagaman kosakata moderat-seragam, sedikit penanda personal, dan banyak
frasa klise/transisi generik. Semua sinyal digabung jadi skor indikatif.
"""

from __future__ import annotations

import json
import math
import os
import re
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as _FutureTimeout

from app.services.ai_detector import model as _model
from app.services.ai_detector.embed import embed_text
from app.services.llm.provider import get_llm

_WORD_RE = re.compile(r"\b[\w'-]+\b", re.UNICODE)

# Komponen LLM bersifat opsional: model embedding (acc ~0.94) sudah kuat sendiri,
# sedangkan panggilan LLM ke Ollama bersama bisa sangat lambat saat GPU penuh.
# ICALORA_AIDETECT_LLM=off  -> lewati LLM sepenuhnya (deteksi nyaris instan).
# ICALORA_AIDETECT_LLM_TIMEOUT=<detik> -> batas tunggu LLM; lewati bila melebihi.
_LLM_ENABLED = os.getenv("ICALORA_AIDETECT_LLM", "on").strip().lower() not in {
    "off",
    "0",
    "false",
    "no",
}
try:
    _LLM_TIMEOUT = float(os.getenv("ICALORA_AIDETECT_LLM_TIMEOUT", "45"))
except ValueError:
    _LLM_TIMEOUT = 45.0

_TRAINED = None  # cache; None=belum dicoba, False=tidak ada, else LogisticModel
_EMB_TRAINED = None  # cache model embedding (stat+emb 1030-dim)


def _trained_probability(signals: dict) -> float | None:
    """Probabilitas AILR (0-100) dari model terlatih bila tersedia."""
    global _TRAINED
    if _TRAINED is None:
        _TRAINED = _model.load() or False
    if not _TRAINED:
        return None
    try:
        return round(_TRAINED.predict_proba(_model.feature_vector(signals)) * 100.0, 1)
    except Exception:  # noqa: BLE001
        return None


def _emb_trained_probability(signals: dict, text: str) -> float | None:
    """Probabilitas (0-100) dari model stat+embedding bila model & endpoint tersedia.

    Menghitung embedding teks saat inferensi; bila endpoint embedding mati/gagal,
    kembalikan None agar sistem degradasi anggun ke sinyal lain.
    """
    global _EMB_TRAINED
    if _EMB_TRAINED is None:
        _EMB_TRAINED = _model.load(_model.EMB_MODEL_PATH) or False
    if not _EMB_TRAINED:
        return None
    emb = embed_text(text)
    if emb is None:
        return None
    try:
        vec = _model.feature_vector(signals) + emb
        return round(_EMB_TRAINED.predict_proba(vec) * 100.0, 1)
    except Exception:  # noqa: BLE001
        return None
_SENT_RE = re.compile(r"[^.!?]+[.!?]*")

# Penanda "suara personal" (kontraksi/kata ganti) yang jarang pada teks AI formal.
_PERSONAL = {
    "i", "we", "my", "our", "me", "us", "saya", "aku", "kami", "kita", "ku",
}
# Frasa transisi/klise yang sering muncul pada teks AI.
_AI_CLICHES = (
    "moreover", "furthermore", "in conclusion", "it is important to note",
    "overall", "in today's world", "plays a crucial role", "a wide range of",
    "it is worth noting", "in summary", "delve into", "navigating the",
    "selain itu", "di sisi lain", "secara keseluruhan", "penting untuk dicatat",
    "dalam kesimpulan", "memainkan peran penting", "tidak dapat dipungkiri",
)


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


def _bigram_repetition(words: list[str]) -> float:
    """Proporsi bigram berulang (tinggi = pola repetitif seperti AI)."""
    if len(words) < 3:
        return 0.0
    lw = [w.lower() for w in words]
    bigrams = [(lw[i], lw[i + 1]) for i in range(len(lw) - 1)]
    unique = len(set(bigrams))
    return 1.0 - unique / len(bigrams)


def _cliche_density(text: str) -> float:
    low = text.lower()
    hits = sum(low.count(c) for c in _AI_CLICHES)
    words = max(len(_WORD_RE.findall(text)), 1)
    return min(hits / words * 100.0, 3.0) / 3.0


def _personal_ratio(words: list[str]) -> float:
    if not words:
        return 0.0
    return sum(1 for w in words if w.lower() in _PERSONAL) / len(words)


def _statistical_signals(text: str) -> dict:
    words = _WORD_RE.findall(text)
    sents = _sentences(text)
    sent_lengths = [len(_WORD_RE.findall(s)) for s in sents] or [0]

    burst = _burstiness(sent_lengths)
    ttr = _type_token_ratio(words)
    avg_len = sum(sent_lengths) / len(sent_lengths)
    bigram_rep = _bigram_repetition(words)
    cliche = _cliche_density(text)
    personal = _personal_ratio(words)

    len_uniformity = 1.0 - min(burst / 0.6, 1.0)
    repetition = 1.0 - min(ttr / 0.5, 1.0)
    low_personal = 1.0 - min(personal / 0.03, 1.0)

    stat_score = max(
        0.0,
        min(
            1.0,
            0.40 * len_uniformity
            + 0.20 * repetition
            + 0.15 * bigram_rep
            + 0.15 * cliche
            + 0.10 * low_personal,
        ),
    )
    return {
        "burstiness": round(burst, 3),
        "type_token_ratio": round(ttr, 3),
        "avg_sentence_length": round(avg_len, 1),
        "bigram_repetition": round(bigram_rep, 3),
        "cliche_density": round(cliche, 3),
        "personal_ratio": round(personal, 4),
        "sentence_count": len(sents),
        "word_count": len(words),
        "stat_score": round(stat_score, 3),
    }


def _llm_analysis(text: str) -> dict:
    """Minta LLM menilai probabilitas AI + kalimat yang paling mirip AI."""
    llm = get_llm()
    messages = [
        {
            "role": "system",
            "content": (
                "Nilai kemungkinan teks berikut ditulis oleh AI (model bahasa) "
                "dibanding manusia. Pertimbangkan keseragaman, klise, pola generik, "
                "dan kurangnya suara personal. Balas HANYA JSON: "
                '{"ai_probability": <0-100>, '
                '"ai_sentences": ["<kalimat yang paling mirip AI, verbatim>", ...]}'
            ),
        },
        {"role": "user", "content": text[:6000]},
    ]
    try:
        raw = llm.chat(messages, temperature=0.0, max_tokens=400).strip()
        raw = re.sub(r"^```(?:json)?|```$", "", raw).strip()
        m = re.search(r"\{.*\}", raw, re.DOTALL)
        data = json.loads(m.group(0) if m else raw)
        prob = data.get("ai_probability")
        prob = max(0.0, min(100.0, float(prob))) if prob is not None else None
        sents = data.get("ai_sentences", [])
        sents = [s.strip() for s in sents if isinstance(s, str) and s.strip()][:10]
        return {"prob": prob, "sentences": sents}
    except Exception:  # noqa: BLE001
        return {"prob": None, "sentences": []}


def _llm_analysis_timed(text: str) -> dict:
    """Jalankan _llm_analysis dengan batas waktu; lewati bila LLM lambat/mati.

    Dinonaktifkan via ICALORA_AIDETECT_LLM=off. Bila melebihi _LLM_TIMEOUT detik,
    komponen LLM dilewati (prob=None) dan blending bergantung pada model
    embedding + statistik — tetap akurat namun jauh lebih cepat.
    """
    if not _LLM_ENABLED:
        return {"prob": None, "sentences": []}
    # Jangan pakai `with`: __exit__ menunggu thread selesai sehingga batas waktu
    # tidak berlaku. shutdown(wait=False) membiarkan panggilan lambat selesai
    # di latar tanpa menahan respons.
    ex = ThreadPoolExecutor(max_workers=1)
    try:
        return ex.submit(_llm_analysis, text).result(timeout=_LLM_TIMEOUT)
    except (_FutureTimeout, Exception):  # noqa: BLE001
        return {"prob": None, "sentences": []}
    finally:
        ex.shutdown(wait=False)


# Bobot berdasar akurasi terukur tiap komponen (lihat _blend).
_W_STAT = 0.08
_W_LLM = 0.30
_W_MODEL = 0.10
_W_EMB = 0.45
_HIGH = 70.0
_LOW = 30.0


def _blend(
    stat_pct: float,
    llm_pct: float | None,
    model_pct: float | None,
    emb_pct: float | None,
) -> tuple[float, str, bool]:
    """Gabungkan skor komponen → (skor akhir, verdict, perlu_tinjauan).

    Bobot dinormalisasi atas komponen yang tersedia. Model embedding tetap
    terbesar (FPR rendah pada teks akademik manusia), tetapi tidak lagi mutlak
    dominan karena dilatih pada keluaran generator lama dan bisa meleset pada
    model baru. Bila embedding berbeda tajam (≥70 vs ≤30) dengan LLM atau model
    6-fitur, verdict menjadi "perlu tinjauan manual" alih-alih memvonis.
    """
    components: list[tuple[float, float]] = [(stat_pct, _W_STAT)]
    if llm_pct is not None:
        components.append((llm_pct, _W_LLM))
    if model_pct is not None:
        components.append((model_pct, _W_MODEL))
    if emb_pct is not None:
        components.append((emb_pct, _W_EMB))
    total_w = sum(w for _v, w in components)
    final = sum(v * w for v, w in components) / total_w
    final = round(max(0.0, min(100.0, final)), 1)

    needs_review = False
    if emb_pct is not None:
        others = [p for p in (llm_pct, model_pct) if p is not None]
        needs_review = any(
            (emb_pct <= _LOW and p >= _HIGH) or (emb_pct >= _HIGH and p <= _LOW)
            for p in others
        )

    if needs_review:
        verdict = "campuran / perlu tinjauan manual"
    elif final >= 70:
        verdict = "kemungkinan besar AI"
    elif final >= 45:
        verdict = "campuran / tidak pasti"
    else:
        verdict = "kemungkinan besar manusia"
    return final, verdict, needs_review


def detect_ai(text: str) -> dict:
    text = text.strip()
    words = _WORD_RE.findall(text)
    if len(words) < 20:
        return {
            "ai_probability": None,
            "verdict": "tidak cukup teks",
            "note": "Butuh minimal ~20 kata untuk analisis yang bermakna.",
            "signals": _statistical_signals(text),
            "flagged_sentences": [],
        }

    signals = _statistical_signals(text)
    stat_pct = signals["stat_score"] * 100
    model_pct = _trained_probability(signals)
    emb_pct = _emb_trained_probability(signals, text)
    analysis = _llm_analysis_timed(text)
    llm_pct = analysis["prob"]

    final, verdict, needs_review = _blend(stat_pct, llm_pct, model_pct, emb_pct)

    flagged: list[str] = []
    low_text = text.lower()
    for s in analysis["sentences"]:
        key = s.lower()[:40]
        if key and key in low_text:
            flagged.append(s)

    return {
        "ai_probability": final,
        "verdict": verdict,
        "needs_review": needs_review,
        "stat_probability": round(stat_pct, 1),
        "llm_probability": round(llm_pct, 1) if llm_pct is not None else None,
        "model_probability": model_pct,
        "emb_model_probability": emb_pct,
        "signals": signals,
        "flagged_sentences": flagged,
        "note": (
            "Analisis ini menggabungkan sinyal statistik linguistik dan model bahasa "
            "untuk menilai kemungkinan teks dihasilkan AI. Sesuai standar alat deteksi "
            "akademik profesional, laporan ini merupakan bukti pendukung yang kuat dan "
            "ditinjau bersama konteks karya — bukan satu-satunya dasar keputusan akhir."
        ),
    }
