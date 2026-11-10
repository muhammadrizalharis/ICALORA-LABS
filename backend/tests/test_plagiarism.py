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

    verbatim = "Kalimat biasa tanpa penanda apa pun di sini."
    structural = "Menurut Smith (2020), pembelajaran mesin penting."
    bib_entry = "Smith J. 2020."

    # Tanpa atribusi, kekuatan kecocokan menentukan kategori.
    assert (
        _classify_match(verbatim, doc.find(verbatim), 0.9, qs, cs, bib_start)["group"]
        == "salinan_langsung"
    )
    assert (
        _classify_match(verbatim, doc.find(verbatim), 0.5, qs, cs, bib_start)["group"]
        == "kemiripan_kuat"
    )
    assert (
        _classify_match(verbatim, doc.find(verbatim), 0.35, qs, cs, bib_start)["group"]
        == "indikasi_parafrase"
    )
    assert (
        _classify_match(structural, doc.find(structural), 0.9, qs, cs, bib_start)["cited"]
        is True
    )
    assert (
        _classify_match(bib_entry, doc.find(bib_entry), 0.9, qs, cs, bib_start)[
            "in_bibliography"
        ]
        is True
    )


def test_classify_cited_and_quoted():
    from app.services.plagiarism import _classify_match

    doc = '"Model ini memberikan akurasi tinggi pada data uji" (Jones, 2019).'
    qs, cs, bib_start = _spans(doc)
    sent = '"Model ini memberikan akurasi tinggi pada data uji"'
    st = _classify_match(sent, doc.find(sent), 0.95, qs, cs, bib_start)
    assert st["group"] == "sumber_terkredit"
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
    res = _chunk_match(sentence, candidates)
    assert "match_groups" in res
    assert {g["type"] for g in res["match_groups"]} == {
        "salinan_langsung",
        "kemiripan_kuat",
        "indikasi_parafrase",
        "sumber_terkredit",
    }
    assert res["matched_passages"][0]["group"] == "salinan_langsung"
    assert res["matched_passages"][0]["char_len"] > 0


def test_chunk_match_exclude_bibliography():
    """Exclude daftar pustaka: kecocokan di bagian referensi tak dihitung."""
    copied = (
        "Deep learning has fundamentally transformed modern medical image analysis pipelines."
    )
    doc = (
        "Pendahuluan singkat yang orisinal tanpa kecocokan apa pun di sini.\n"
        "Daftar Pustaka\n" + copied
    )
    candidates = [{"doc_id": 1, "title": "Sumber Uji", "doi": "10.0/abc",
                   "_fulltext": copied + " trailing context."}]
    base = _chunk_match(doc, candidates, threshold=0.55)
    assert base["matched_sentences"] == 1
    excl = _chunk_match(doc, candidates, threshold=0.55, exclude={"bibliography": True})
    assert excl["matched_sentences"] == 0
    assert excl["similarity_index"] == 0.0


def test_chunk_match_exclude_min_source_percent():
    """Exclude sumber di bawah ambang persen yang diisi user."""
    copied = (
        "Deep learning has fundamentally transformed modern medical image analysis pipelines."
    )
    candidates = [{"doc_id": 1, "title": "Sumber Uji", "doi": "10.0/abc",
                   "_fulltext": copied + " trailing context."}]
    base = _chunk_match(copied, candidates, threshold=0.55)
    assert base["matched_sentences"] == 1
    # Sumber menyumbang ~100% dokumen; ambang 100% tak mengecualikannya,
    # tetapi ambang di atas kontribusi (>100 mustahil) → pakai dokumen besar.
    big_doc = copied + " " + ("Kalimat orisinal yang panjang dan tak cocok. " * 40)
    base2 = _chunk_match(big_doc, candidates, threshold=0.55)
    pct = next(iter(base2["source_percent"].values()))
    excl = _chunk_match(
        big_doc, candidates, threshold=0.55,
        exclude={"min_source_percent": pct + 5},
    )
    assert excl["matched_sentences"] == 0
    assert excl["excluded_sources"]
