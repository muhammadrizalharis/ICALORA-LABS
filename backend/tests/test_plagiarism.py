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


def _spans(doc):
    from app.services.plagiarism import _BIB_RE, _CITATION_RE, _QUOTE_RE

    qs = [(m.start(), m.end()) for m in _QUOTE_RE.finditer(doc)]
    cs = [(m.start(), m.end()) for m in _CITATION_RE.finditer(doc)]
    bib = _BIB_RE.search(doc)
    return qs, cs, (bib.start() if bib else None)


def test_classify_match_groups():
    from app.services.plagiarism import _classify_match

    doc = (
        'Menurut Smith (2020), pembelajaran mesin penting. '
        '"Deep learning mengubah analisis citra medis modern." '
        'Kalimat biasa tanpa penanda apa pun di sini.\n\n'
        'Daftar Pustaka\nSmith J. 2020.'
    )
    qs, cs, bib_start = _spans(doc)

    cited_unquoted = "Menurut Smith (2020), pembelajaran mesin penting."
    quoted_uncited = '"Deep learning mengubah analisis citra medis modern."'
    plain = "Kalimat biasa tanpa penanda apa pun di sini."
    bib_entry = "Smith J. 2020."

    assert _classify_match(cited_unquoted, doc.find(cited_unquoted), qs, cs, bib_start)["group"] == "missing_quote"
    assert _classify_match(quoted_uncited, doc.find(quoted_uncited), qs, cs, bib_start)["group"] == "missing_citation"
    assert _classify_match(plain, doc.find(plain), qs, cs, bib_start)["group"] == "uncited"
    assert _classify_match(bib_entry, doc.find(bib_entry), qs, cs, bib_start)["in_bibliography"] is True


def test_classify_cited_and_quoted():
    from app.services.plagiarism import _classify_match

    doc = '"Model ini memberikan akurasi tinggi pada data uji" (Jones, 2019).'
    qs, cs, bib_start = _spans(doc)
    sent = '"Model ini memberikan akurasi tinggi pada data uji"'
    st = _classify_match(sent, doc.find(sent), qs, cs, bib_start)
    assert st["group"] == "cited_quoted"
    assert st["quoted"] and st["cited"]


def test_chunk_match_includes_group_metadata():
    sentence = "Deep learning has fundamentally transformed modern medical image analysis pipelines."
    candidates = [
        {
            "doc_id": 1,
            "title": "Sumber Uji",
            "doi": "10.0/abc",
            "_fulltext": sentence + " Additional unrelated trailing context here.",
        }
    ]
    res = _chunk_match(sentence, candidates, threshold=0.55)
    assert "match_groups" in res
    assert {g["type"] for g in res["match_groups"]} == {
        "uncited",
        "missing_quote",
        "missing_citation",
        "cited_quoted",
    }
    assert res["matched_passages"][0]["group"] == "uncited"
    assert res["matched_passages"][0]["char_len"] > 0
