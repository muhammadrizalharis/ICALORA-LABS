from app.services.citation import (
    _bibtex_key,
    _format_apa,
    _format_bibtex,
    _format_harvard,
    _format_ieee,
    _format_mla,
    _format_ris,
    _format_vancouver,
    _vec_literal,
)


def test_vec_literal():
    assert _vec_literal([0.0, 1.5, -2.25]) == "[0.000000,1.500000,-2.250000]"


def test_bibtex_key():
    assert _bibtex_key("Deep Learning Methods", 2021, 42) == "deep2021_42"
    assert _bibtex_key(None, None, 7) == "ref_7"
    assert _bibtex_key("", 2019, 9) == "ref2019_9"


def test_format_apa():
    out = _format_apa("Deep Learning", 2021, "10.1/abc", "arxiv")
    assert out == "(2021). Deep Learning. arXiv. https://doi.org/10.1/abc"
    assert _format_apa(None, None, None, "oa") == "(n.d.). [Judul tidak tersedia]. OA."


def test_format_bibtex():
    out = _format_bibtex("Deep Learning", 2021, "10.1/abc", "arxiv", 42)
    assert out.startswith("@article{deep2021_42,")
    assert "title = {Deep Learning}," in out
    assert "year = {2021}," in out
    assert "doi = {10.1/abc}," in out
    assert out.rstrip().endswith("}")


def test_format_ieee():
    assert (
        _format_ieee("Deep Learning", 2021, "10.1/abc", "arxiv")
        == '"Deep Learning," arXiv, 2021, doi: 10.1/abc.'
    )


def test_format_mla():
    assert (
        _format_mla("Deep Learning", 2021, "10.1/abc", "arxiv")
        == '"Deep Learning." arXiv, 2021, https://doi.org/10.1/abc.'
    )


def test_format_harvard():
    out = _format_harvard("Deep Learning", 2021, "10.1/abc", "arxiv")
    assert out == "2021. 'Deep Learning', arXiv. Available at: https://doi.org/10.1/abc"
    assert _format_harvard(None, None, None, "oa") == "n.d. '[Judul tidak tersedia]', OA."


def test_format_vancouver():
    out = _format_vancouver("Deep Learning", 2021, "10.1/abc", "arxiv")
    assert out == "Deep Learning. arXiv. 2021. Available from: https://doi.org/10.1/abc"


def test_format_vancouver_no_year_no_double_period():
    out = _format_vancouver("Deep Learning", None, "10.1/abc", "arxiv")
    assert ".." not in out
    assert out == "Deep Learning. arXiv. Available from: https://doi.org/10.1/abc"


def test_format_ris():
    out = _format_ris("Deep Learning", 2021, "10.1/abc", "arxiv")
    assert out.splitlines()[0] == "TY  - JOUR"
    assert "TI  - Deep Learning" in out
    assert "PY  - 2021" in out
    assert "DO  - 10.1/abc" in out
    assert "UR  - https://doi.org/10.1/abc" in out
    assert out.rstrip().endswith("ER  -")
