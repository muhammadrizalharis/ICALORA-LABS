from app.services.ai_detector import (
    _bigram_repetition,
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


def test_blend_is_embedding_dominant(monkeypatch):
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
    # Embedding dominan → hasil akhir harus condong 'manusia', bukan 'AI'.
    assert r["ai_probability"] < 45, r
    assert r["verdict"] == "kemungkinan besar manusia"
