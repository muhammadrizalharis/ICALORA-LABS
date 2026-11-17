"""Regresi: paper terbit tetap ditemukan saat judul/header dihapus dari dokumen."""

from app.services.plagiarism.online import _abstract_queries, _distinct_term_queries

_DOC = (
    "ABSTRACT\n"
    "Local scour around bridge piers is a major cause of foundation instability under "
    "strong hydraulic loading. This study experimentally evaluates porous-net "
    "configurations as flow-modifying countermeasures for reducing local scour around "
    "a cylindrical bridge pier. The porous-net configuration reduced scour depth.\n"
    "Keywords: local scour, cylindrical bridge pier, porous-net structure\n"
)


def test_abstract_queries_use_keywords_and_leading_sentences():
    qs = _abstract_queries(_DOC)
    assert any("porous-net structure" in q for q in qs)
    assert any(q.startswith("Local scour around bridge piers") for q in qs)
    assert all(len(q) <= 300 for q in qs)


def test_distinct_term_queries_are_short_and_pick_specific_terms():
    qs = _distinct_term_queries(_DOC)
    assert qs
    joined = " ".join(qs)
    assert "scour" in joined and "porous-net" in joined
    assert all(len(q.split()) <= 4 for q in qs)


def test_no_queries_for_empty_doc():
    assert _abstract_queries("") == []
    assert _distinct_term_queries("") == []


_INTRO_ONLY = (
    "1. INTRODUCTION\n"
    "Rice distribution is critical for food security across provinces. "
    "The rice-distribution network depends on logistics performance. "
    "Rice production differs across provinces and rice logistics varies.\n"
    "2. METHODS\nWe cluster rice distribution data with rice-distribution indicators.\n"
    "References\n[1] Someone-Else-Name, Unrelated-Hyphen. 2020.\n"
)


def test_term_queries_use_whole_doc_pairs_and_four_letter_terms():
    qs = _distinct_term_queries(_INTRO_ONLY)
    assert any(q.split()[0] == "rice-distribution" and len(q.split()) == 2 for q in qs)
    assert any("rice" in q.split() for q in qs)
    assert len(qs) <= 12
    # daftar pustaka tidak boleh mencemari istilah khas
    assert not any("someone" in q for q in qs)


def test_openalex_params_include_key_only_when_configured(monkeypatch):
    from app.services.plagiarism import online

    monkeypatch.setattr(online.settings, "openalex_api_key", "")
    assert "api_key" not in online._oa_params({"search": "x"})
    monkeypatch.setattr(online.settings, "openalex_api_key", "k123")
    p = online._oa_params({"search": "x"})
    assert p["api_key"] == "k123" and p["search"] == "x" and "mailto" in p
