from app.services.plagiarism import _chunk_match, _sentences, _shingles, _vec_literal


def test_vec_literal():
    assert _vec_literal([0.0, 1.5, -2.25]) == "[0.000000,1.500000,-2.250000]"


def test_shingles():
    words = ["a", "b", "c", "d", "e", "f"]
    sh = _shingles(words, n=5)
    assert "a b c d e" in sh
    assert "b c d e f" in sh
    assert _shingles(["x", "y"], n=5) == {"x y"}
    assert _shingles([], n=5) == set()


def test_sentences_filters_short():
    text = (
        "Ini kalimat yang cukup panjang untuk dihitung. Pendek. "
        "Kalimat kedua yang juga panjang sekali."
    )
    sents = _sentences(text)
    assert len(sents) == 2
    assert all(len(s) >= 20 for s in sents)


def test_chunk_match_detects_copy():
    sentence = (
        "Deep learning has fundamentally transformed modern medical image analysis pipelines."
    )
    candidates = [
        {
            "doc_id": 1,
            "title": "Sumber Uji",
            "doi": "10.0/abc",
            "_fulltext": sentence + " Additional unrelated trailing context here.",
        }
    ]
    res = _chunk_match(sentence, candidates, threshold=0.55)
    assert res["matched_sentences"] == 1
    assert res["similarity_index"] >= 90.0
    assert res["matched_passages"][0]["source_title"] == "Sumber Uji"


def test_chunk_match_no_false_positive():
    sentence = "The weather today is sunny with a gentle breeze over the coastal town."
    candidates = [
        {
            "doc_id": 2,
            "title": "Tak Terkait",
            "doi": None,
            "_fulltext": (
                "Quantum chromodynamics describes strong interactions "
                "between quarks and gluons."
            ),
        }
    ]
    res = _chunk_match(sentence, candidates, threshold=0.55)
    assert res["matched_sentences"] == 0
    assert res["similarity_index"] == 0.0
