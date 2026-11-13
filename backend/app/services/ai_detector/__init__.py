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
from app.services.ai_detector.embed import embed_text, embed_texts
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


_PROB_RE = re.compile(r'"ai_probability"\s*:\s*(-?\d+(?:\.\d+)?)')
_SENT_ITEM_RE = re.compile(r'"((?:[^"\\]|\\.){15,})"')


def _parse_llm_json(raw: str) -> dict:
    """Baca balasan JSON LLM; tahan terhadap JSON terpotong (batas token)."""
    raw = re.sub(r"^```(?:json)?|```$", "", raw.strip()).strip()
    m = re.search(r"\{.*\}", raw, re.DOTALL)
    try:
        data = json.loads(m.group(0) if m else raw)
        prob = data.get("ai_probability")
        sents = data.get("ai_sentences", [])
    except Exception:  # noqa: BLE001
        pm = _PROB_RE.search(raw)
        prob = pm.group(1) if pm else None
        tail = raw.split("ai_sentences", 1)[1] if "ai_sentences" in raw else ""
        sents = [x.group(1) for x in _SENT_ITEM_RE.finditer(tail)]
    try:
        prob = max(0.0, min(100.0, float(prob))) if prob is not None else None
    except (TypeError, ValueError):
        prob = None
    sents = [x.strip() for x in sents if isinstance(x, str) and x.strip()][:5]
    return {"prob": prob, "sentences": sents}


def _llm_analysis(text: str) -> dict:
    """Minta LLM menilai probabilitas AI + kalimat yang paling mirip AI."""
    llm = get_llm()
    messages = [
        {
            "role": "system",
            "content": (
                "Nilai kemungkinan teks berikut ditulis oleh AI (model bahasa) "
                "dibanding manusia. Pertimbangkan keseragaman, klise, pola generik, "
                "dan kurangnya suara personal. Ingat: tulisan akademik manusia juga "
                "formal; formalitas saja bukan bukti AI. Balas HANYA JSON: "
                '{"ai_probability": <0-100>, '
                '"ai_sentences": ["<maks 5 kalimat paling mirip AI, verbatim>"]}'
            ),
        },
        {"role": "user", "content": text[:6000]},
    ]
    try:
        raw = llm.chat(messages, temperature=0.0, max_tokens=600)
        return _parse_llm_json(raw)
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
_W_LLM = 0.17
_W_MODEL = 0.10
_W_EMB = 0.65

# LLM judge (qwen3.6) terukur menuduh 12/15 teks akademik manusia berbahasa
# Indonesia sebagai AI (median 85%), sementara model embedding hanya 1/15.
# Untuk teks Indonesia LLM tidak dipanggil (hemat VRAM & waktu, tanpa salah tuduh).
_ID_MARKERS = re.compile(
    r"\b(yang|dengan|dari|untuk|pada|adalah|dan|ini|dalam|tidak|dapat|akan|telah|"
    r"secara|terhadap|merupakan|bahwa|sehingga|oleh|serta|juga|sebagai|atau)\b",
    re.IGNORECASE,
)


_EN_MARKERS = re.compile(
    r"\b(the|of|and|to|in|is|that|for|with|as|on|are|this|by|be|from|which|"
    r"it|an|or|was|were|has|have)\b",
    re.IGNORECASE,
)


def _marker_ratio(pattern: re.Pattern, text: str) -> float:
    sample = text[:3000]
    n = len(_WORD_RE.findall(sample))
    return len(pattern.findall(sample)) / n if n else 0.0


def _is_indonesian(text: str) -> bool:
    return _marker_ratio(_ID_MARKERS, text) >= 0.06


def _detect_language(text: str) -> str:
    """'id', 'en', atau 'other' (bahasa di luar data latih → hasil kurang andal)."""
    if _is_indonesian(text):
        return "id"
    if _marker_ratio(_EN_MARKERS, text) >= 0.06:
        return "en"
    return "other"
_HIGH = 70.0
_LOW = 30.0
_CALIB = None  # None=belum dimuat, False=tidak ada, else (a, b, ambang_ai, ambang_campuran)


def _load_calib():
    global _CALIB
    if _CALIB is None:
        try:
            c = json.loads(_model.EMB_MODEL_PATH.read_text(encoding="utf-8"))["meta"]["calibration"]
            _CALIB = (float(c["a"]), float(c["b"]),
                      float(c.get("threshold_ai", _HIGH)), float(c.get("threshold_mixed", 45.0)))
        except Exception:  # noqa: BLE001
            _CALIB = False
    return _CALIB


def _thresholds() -> tuple[float, float]:
    """Ambang verdict (AI, campuran); dipilih di set validasi dengan batas FPR."""
    c = _load_calib()
    return (c[2], c[3]) if c and len(c) > 2 else (_HIGH, 45.0)


def _calibrate(score: float) -> float:
    """Kalibrasi Platt seimbang (dipasang evaluate.py di meta model)."""
    c = _load_calib()
    if not c:
        return score
    a, b = c[0], c[1]
    p = min(max(score / 100.0, 1e-4), 1 - 1e-4)
    return 100.0 / (1.0 + math.exp(-(a * math.log(p / (1 - p)) + b)))


def _blend(
    stat_pct: float,
    llm_pct: float | None,
    model_pct: float | None,
    emb_pct: float | None,
) -> tuple[float, str, bool]:
    """Gabungkan skor komponen → (skor akhir, verdict, perlu_tinjauan).

    Bobot dinormalisasi atas komponen yang tersedia; model embedding dominan
    (akurasi & FPR terbaik pada evaluasi). Bila embedding dan model 6-fitur
    berbeda tajam (≥70 vs ≤30), verdict menjadi "perlu tinjauan manual" —
    menangkap teks AI yang diparafrase tanpa memvonis. LLM tidak ikut aturan ini
    karena kerap menuduh tulisan akademik manusia yang formal.
    """
    components: list[tuple[float, float]] = [(stat_pct, _W_STAT)]
    if llm_pct is not None:
        components.append((llm_pct, _W_LLM))
    if model_pct is not None:
        components.append((model_pct, _W_MODEL))
    if emb_pct is not None:
        components.append((emb_pct, _W_EMB))
    total_w = sum(w for _v, w in components)
    final = _calibrate(sum(v * w for v, w in components) / total_w)
    final = round(max(0.0, min(100.0, final)), 1)

    needs_review = (
        emb_pct is not None
        and model_pct is not None
        and (
            (emb_pct <= _LOW and model_pct >= _HIGH)
            or (emb_pct >= _HIGH and model_pct <= _LOW)
        )
    )

    thr_ai, thr_mix = _thresholds()
    if needs_review:
        verdict = "campuran / perlu tinjauan manual"
    elif final >= thr_ai:
        verdict = "kemungkinan besar AI"
    elif final >= thr_mix:
        verdict = "campuran / tidak pasti"
    else:
        verdict = "kemungkinan besar manusia"
    return final, verdict, needs_review


# Dokumen panjang dinilai per segmen (~250 kata, mengikuti batas kalimat) agar
# seluruh isi ikut dinilai — bukan hanya 8.000 karakter pertama — dan agar bagian
# yang terindikasi AI bisa ditunjukkan. Ukuran segmen mengikuti distribusi data
# latih (80-400 kata per sampel).
_SEG_TARGET_WORDS = 250
_SEG_MIN_WORDS = 80
_MAX_SEGMENTS = 300
_LLM_SAMPLE_CHARS = 6000
_SHARE_MIN = 15.0
_SEG_TEXT_CAP = 1500

_NOTE = (
    "Skor adalah estimasi statistik dari pola teks, bukan bukti kepengarangan. "
    "Tulisan manusia yang sangat formal atau generik dapat ditandai, dan teks AI "
    "yang disunting dapat lolos. Gunakan sebagai sinyal awal yang ditinjau bersama "
    "konteks (draf, riwayat revisi, rujukan, wawancara penulis) — bukan satu-satunya "
    "dasar keputusan."
)


def _score_definition() -> str:
    thr_ai, thr_mix = _thresholds()
    cal = (
        "dikalibrasi (Platt, prior AI:manusia 50:50) pada set validasi terpisah"
        if _load_calib() else "belum dikalibrasi"
    )
    return (
        f"ai_probability: skor gabungan 0-100 (model embedding dominan), {cal}. "
        f"Verdict AI bila ≥ {thr_ai:g}, campuran bila ≥ {thr_mix:g} — ambang dipilih "
        "pada data validasi dengan batas false-positive rate. ai_share: persentase "
        f"kata pada segmen dengan skor ≥ {thr_ai:g}."
    )
_SHORT_WORDS = 80
_MODEL_INFO: dict | None = None


def _model_info() -> dict:
    """Ringkasan versi & validasi model embedding (untuk transparansi laporan)."""
    global _MODEL_INFO
    if _MODEL_INFO is None:
        info: dict = {}
        try:
            meta = json.loads(_model.EMB_MODEL_PATH.read_text(encoding="utf-8")).get("meta", {})
            val = meta.get("validation") or {}
            info = {
                "kind": meta.get("kind"),
                "trained_at": meta.get("trained_at"),
                "training_samples": meta.get("n_human", 0) + meta.get("n_ai", 0) or None,
                "generators": meta.get("generators"),
                "validation_accuracy": val.get("accuracy"),
                "validation_fpr": val.get("false_positive_rate"),
                "calibrated": bool(meta.get("calibration")),
                "calibration_test": (meta.get("calibration") or {}).get("test"),
            }
        except Exception:  # noqa: BLE001
            info = {}
        _MODEL_INFO = info
    return _MODEL_INFO


def _annotate(res: dict, n_words: int, language: str) -> dict:
    """Tambahkan peringatan, tingkat keandalan, dan metadata laporan."""
    warnings: list[str] = []
    if n_words < _SHORT_WORDS:
        warnings.append(
            f"Teks pendek ({n_words} kata < {_SHORT_WORDS}): pola statistik belum stabil, "
            "hasil kurang andal."
        )
    if language == "other":
        warnings.append(
            "Bahasa teks tidak terdeteksi sebagai Indonesia/Inggris; model hanya "
            "dilatih untuk dua bahasa tersebut."
        )
    if res.get("llm_probability") is None and language == "en":
        warnings.append("Penilaian LLM tidak tersedia (timeout/nonaktif); skor dari model lain.")
    low = n_words < _SHORT_WORDS or language == "other"
    reliability = "rendah" if low else "normal"
    if reliability == "rendah" and res.get("verdict") == "kemungkinan besar AI":
        res["needs_review"] = True
    components = [
        name for key, name in (
            ("stat_probability", "statistik"),
            ("llm_probability", "llm"),
            ("model_probability", "model_6_fitur"),
            ("emb_model_probability", "model_embedding"),
        ) if res.get(key) is not None
    ]
    res["warnings"] = warnings
    res["reliability"] = reliability
    res["report"] = {
        "words_analyzed": n_words,
        "segments": len(res.get("segments") or []) or 1,
        "language": language,
        "supported_languages": ["id", "en"],
        "components": components,
        "llm_skipped_reason": (
            "LLM tidak dipakai untuk teks Indonesia (terukur sering salah menuduh tulisan "
            "akademik manusia)." if language == "id" else None
        ),
        "score_definition": _score_definition(),
        "model": _model_info(),
    }
    return res


def _segment_spans(text: str) -> list[tuple[int, int]]:
    """Pecah teks menjadi rentang karakter ~_SEG_TARGET_WORDS kata per segmen."""
    total = len(_WORD_RE.findall(text))
    target = max(_SEG_TARGET_WORDS, math.ceil(total / _MAX_SEGMENTS))
    spans: list[list[int]] = []
    start: int | None = None
    end = 0
    count = 0
    for m in _SENT_RE.finditer(text):
        n = len(_WORD_RE.findall(m.group(0)))
        if n == 0:
            continue
        if start is None:
            start = m.start()
        end = m.end()
        count += n
        gap = text[end : end + 8]
        para_break = "\n\n" in gap or "\n \n" in gap or "\r\n\r\n" in gap
        if count >= target or (para_break and count >= 0.6 * target):
            spans.append([start, end])
            start, count = None, 0
    if start is not None:
        if spans and count < _SEG_MIN_WORDS:
            spans[-1][1] = end
        else:
            spans.append([start, end])
    return [(a, b) for a, b in spans]


def _emb_probabilities(sigs: list[dict], texts: list[str]) -> list[float | None]:
    """Probabilitas model embedding untuk banyak teks (embedding berbatch)."""
    global _EMB_TRAINED
    if _EMB_TRAINED is None:
        _EMB_TRAINED = _model.load(_model.EMB_MODEL_PATH) or False
    if not _EMB_TRAINED:
        return [None] * len(texts)
    out: list[float | None] = []
    for sig, emb in zip(sigs, embed_texts(texts), strict=True):
        if emb is None:
            out.append(None)
            continue
        try:
            vec = _model.feature_vector(sig) + emb
            out.append(round(_EMB_TRAINED.predict_proba(vec) * 100.0, 1))
        except Exception:  # noqa: BLE001
            out.append(None)
    return out


def _wmean(values: list[float | None], weights: list[int]) -> float | None:
    pairs = [(v, w) for v, w in zip(values, weights, strict=True) if v is not None]
    total = sum(w for _v, w in pairs)
    if not pairs or total == 0:
        return None
    return round(sum(v * w for v, w in pairs) / total, 1)


def _llm_sample(seg_texts: list[str]) -> str:
    """Cuplikan merata dari seluruh dokumen (≤ _LLM_SAMPLE_CHARS) untuk LLM."""
    if not seg_texts:
        return ""
    per = max(1, _LLM_SAMPLE_CHARS // max(1, len(seg_texts)))
    if per >= 600:
        return "\n\n".join(seg_texts)[:_LLM_SAMPLE_CHARS]
    k = max(1, _LLM_SAMPLE_CHARS // 1200)
    step = len(seg_texts) / k
    picks = sorted({int(i * step) for i in range(k)})
    return "\n\n".join(seg_texts[i][:1200] for i in picks)[:_LLM_SAMPLE_CHARS]


def _flagged(sentences: list[str], text: str) -> list[str]:
    low_text = text.lower()
    return [s for s in sentences if (key := s.lower()[:40]) and key in low_text]


def _seg_label(score: float) -> str:
    thr_ai, thr_mix = _thresholds()
    if score >= thr_ai:
        return "ai"
    if score >= thr_mix:
        return "mixed"
    return "human"


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
    spans = _segment_spans(text)
    language = _detect_language(text)

    def judge(sample: str) -> dict:
        if language != "en":
            return {"prob": None, "sentences": []}
        return _llm_analysis_timed(sample)

    if len(spans) <= 1:
        model_pct = _trained_probability(signals)
        emb_pct = _emb_trained_probability(signals, text)
        analysis = judge(text)
        llm_pct = analysis["prob"]
        final, verdict, needs_review = _blend(stat_pct, llm_pct, model_pct, emb_pct)
        return _annotate({
            "ai_probability": final,
            "verdict": verdict,
            "needs_review": needs_review,
            "ai_share": None,
            "segments": [],
            "language": language,
            "stat_probability": round(stat_pct, 1),
            "llm_probability": round(llm_pct, 1) if llm_pct is not None else None,
            "model_probability": model_pct,
            "emb_model_probability": emb_pct,
            "signals": signals,
            "flagged_sentences": _flagged(analysis["sentences"], text),
            "note": _NOTE,
        }, len(words), language)

    seg_texts = [text[a:b].strip() for a, b in spans]
    seg_sigs = [_statistical_signals(t) for t in seg_texts]
    seg_words = [max(1, int(sg["word_count"])) for sg in seg_sigs]
    seg_model = [_trained_probability(sg) for sg in seg_sigs]
    seg_emb = _emb_probabilities(seg_sigs, seg_texts)
    seg_scores = [
        _blend(sg["stat_score"] * 100, None, m, e)[0]
        for sg, m, e in zip(seg_sigs, seg_model, seg_emb, strict=True)
    ]

    model_pct = _wmean(seg_model, seg_words)
    emb_pct = _wmean(seg_emb, seg_words)
    analysis = judge(_llm_sample(seg_texts))
    llm_pct = analysis["prob"]
    final, verdict, needs_review = _blend(stat_pct, llm_pct, model_pct, emb_pct)

    total_w = sum(seg_words)
    ai_w = sum(w for w, sc in zip(seg_words, seg_scores, strict=True) if sc >= _thresholds()[0])
    ai_share = round(100.0 * ai_w / total_w, 1) if total_w else 0.0
    if verdict == "kemungkinan besar manusia" and ai_share >= _SHARE_MIN:
        verdict = "sebagian terindikasi AI"
        needs_review = True

    segments = []
    for i, ((a, b), t, w, sc) in enumerate(
        zip(spans, seg_texts, seg_words, seg_scores, strict=True)
    ):
        label = _seg_label(sc)
        segments.append({
            "index": i,
            "start": a,
            "end": b,
            "words": w,
            "ai_probability": sc,
            "label": label,
            "preview": t[:140],
            "text": t[:_SEG_TEXT_CAP] if label != "human" else None,
        })

    return _annotate({
        "ai_probability": final,
        "verdict": verdict,
        "needs_review": needs_review,
        "ai_share": ai_share,
        "segments": segments,
        "language": language,
        "stat_probability": round(stat_pct, 1),
        "llm_probability": round(llm_pct, 1) if llm_pct is not None else None,
        "model_probability": model_pct,
        "emb_model_probability": emb_pct,
        "signals": signals,
        "flagged_sentences": _flagged(analysis["sentences"], text),
        "note": _NOTE,
    }, len(words), language)
