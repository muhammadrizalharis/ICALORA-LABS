from app.services.ai_detector import (
    _bigram_repetition,
    _blend,
    _burstiness,
    _cliche_density,
    _personal_ratio,
    _sentences,
    _statistical_signals,
    _type_token_ratio,
)


def test_sentences_splits_on_terminators():
    assert _sentences("Halo dunia. Apa kabar? Baik!") == [
        "Halo dunia.",
        "Apa kabar?",
        "Baik!",
    ]


def test_burstiness_zero_for_uniform_lengths():
    assert _burstiness([5, 5, 5, 5]) == 0.0


def test_burstiness_positive_for_varied_lengths():
    assert _burstiness([2, 20, 3, 18]) > 0.0


def test_type_token_ratio_detects_repetition():
    assert _type_token_ratio(["a", "a", "a", "a"]) == 0.25
    assert _type_token_ratio(["a", "b", "c", "d"]) == 1.0


def test_bigram_repetition_flags_repeated_pairs():
    repeated = ["the", "cat", "the", "cat", "the", "cat"]
    varied = ["one", "two", "three", "four", "five", "six"]
    assert _bigram_repetition(repeated) > _bigram_repetition(varied)


def test_cliche_density_in_unit_range():
    val = _cliche_density(
        "Moreover, it is important to note that in conclusion this is crucial."
    )
    assert 0.0 <= val <= 1.0
    assert val > 0.0


def test_personal_ratio_counts_personal_markers():
    assert _personal_ratio(["i", "remember", "my", "home"]) > 0.0
    assert _personal_ratio(["the", "system", "processes", "data"]) == 0.0


def test_statistical_signals_contract():
    sig = _statistical_signals("I still remember that quiet morning at home. It felt warm.")
    for key in (
        "burstiness",
        "type_token_ratio",
        "avg_sentence_length",
        "bigram_repetition",
        "cliche_density",
        "personal_ratio",
        "sentence_count",
        "word_count",
        "stat_score",
    ):
        assert key in sig
    assert 0.0 <= sig["stat_score"] <= 1.0


def test_cliche_text_scores_higher_than_personal():
    ai_like = _statistical_signals(
        "Moreover, it is important to note that machine learning plays a crucial role. "
        "Furthermore, in conclusion these technologies are transformative and impactful."
    )
    human_like = _statistical_signals(
        "I still remember grandma's kitchen. She hummed while frying tempe, grease popping. "
        "We never had much, but those tiny mornings felt enormous to me."
    )
    assert ai_like["stat_score"] > human_like["stat_score"]


def test_blend_keeps_embedding_largest(monkeypatch):
    """Model embedding (akurasi 0.97) harus MENDOMINASI blending; model 6-fitur
    (akurasi 0.85, false-positive 16%) & heuristik stat berbobot kecil. Regresi:
    bobot 6-fitur yang terlalu besar dulu memvonis teks akademik manusia 'AI'.
    """
    import app.services.ai_detector as det

    long_text = ("This is a sufficiently long sample sentence for analysis. " * 8)
    # Semua komponen lemah berkata 'AI' (90), hanya embedding yang benar 'manusia' (10).
    monkeypatch.setattr(det, "_trained_probability", lambda sig: 90.0)
    monkeypatch.setattr(det, "_emb_trained_probability", lambda sig, txt: 10.0)
    monkeypatch.setattr(det, "_llm_analysis_timed", lambda txt: {"prob": None, "sentences": []})
    # Paksa heuristik stat tinggi juga.
    monkeypatch.setattr(det, "_statistical_signals", lambda txt: {
        "burstiness": 0.0, "type_token_ratio": 0.3, "avg_sentence_length": 20.0,
        "bigram_repetition": 0.5, "cliche_density": 1.0, "personal_ratio": 0.0,
        "sentence_count": 8, "word_count": 80, "stat_score": 0.9,
    })

    r = det.detect_ai(long_text)
    # Embedding tetap terbesar → skor akhir tidak boleh condong 'AI'. Karena
    # 6-fitur (90) dan embedding (10) bertentangan tajam, verdict menjadi
    # tinjauan manual, bukan vonis AI.
    assert r["ai_probability"] < 45, r
    assert r["needs_review"] is True
    assert r["verdict"] != "kemungkinan besar AI"


def test_blend_uhi_disagreement_needs_review():
    # Kasus nyata: emb 3.5% vs model 6-fitur 89.2%, LLM timeout.
    final, verdict, review = _blend(38.6, None, 89.2, 3.5)
    assert review is True
    assert "tinjauan manual" in verdict
    assert 0.0 <= final <= 100.0


def test_blend_agreeing_ai_signals():
    final, verdict, review = _blend(60.0, 90.0, 85.0, 92.0)
    assert review is False
    assert final >= 70
    assert verdict == "kemungkinan besar AI"


def test_blend_agreeing_human_signals():
    final, verdict, review = _blend(20.0, 10.0, 25.0, 5.0)
    assert review is False
    assert verdict == "kemungkinan besar manusia"


def test_blend_only_stat_available():
    final, verdict, review = _blend(55.0, None, None, None)
    assert final == 55.0
    assert review is False
    assert verdict == "campuran / tidak pasti"


def test_llm_timeout_does_not_block(monkeypatch):
    import time

    import app.services.ai_detector as det

    monkeypatch.setattr(det, "_LLM_ENABLED", True)
    monkeypatch.setattr(det, "_LLM_TIMEOUT", 0.2)
    monkeypatch.setattr(det, "_llm_analysis", lambda txt: time.sleep(2) or {"prob": 99.0})
    t0 = time.monotonic()
    r = det._llm_analysis_timed("x")
    assert r["prob"] is None
    assert time.monotonic() - t0 < 1.0
