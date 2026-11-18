"""Penanda 'paper terbit' dan judul dokumen pada laporan plagiarisme."""

from app.api.tools import _clean_doc_title
from app.services.plagiarism import _coverage_publication
from app.services.plagiarism.report_pdf import _cover_html, _publication_block

_SRC = {
    "title": "Hydrodynamic Effects of Porous-Net Density",
    "doi": "10.18280/ijht.440419",
    "url": "https://doi.org/10.18280/ijht.440419",
    "source": "OpenAlex (teks penuh OA)",
    "fulltext_oa": True,
    "match_percent": 96.9,
    "source_containment": 42.6,
}


def test_coverage_marks_document_that_is_part_of_fulltext_source():
    pm = _coverage_publication([_SRC])
    assert pm and pm["by_coverage"] and pm["doc_coverage"] == 96.9
    assert pm["doi"] == "10.18280/ijht.440419"


def test_coverage_requires_fulltext_and_high_match():
    assert _coverage_publication([{**_SRC, "fulltext_oa": False}]) is None
    assert _coverage_publication([{**_SRC, "match_percent": 40.0}]) is None
    assert _coverage_publication([]) is None


def test_coverage_picks_highest_cover_source():
    other = {**_SRC, "doi": "10.1/other", "match_percent": 80.0}
    assert _coverage_publication([other, _SRC])["doi"] == "10.18280/ijht.440419"


def test_clean_doc_title_uses_user_title_and_falls_back():
    assert _clean_doc_title("  Judul \x00 Saya\n\nBaru  ", "x.pdf") == "Judul Saya Baru"
    assert _clean_doc_title("", "x.pdf") == "x.pdf"
    assert _clean_doc_title("   ", "x.pdf") == "x.pdf"
    assert len(_clean_doc_title("a" * 500)) == 200


def test_cover_shows_user_title_escaped_and_publication_banner():
    report = {
        "doc_title": "Studi <b>Gerusan</b> & Pilar",
        "source_filename": "file.pdf",
        "publication_match": {**_SRC, "by_coverage": True, "doc_coverage": 96.9},
        "sources": [],
        "match_groups": [],
    }
    html = _cover_html(report)
    assert "Judul Dokumen" in html
    assert "Studi &lt;b&gt;Gerusan&lt;/b&gt; &amp; Pilar" in html
    assert "<b>Gerusan</b>" not in html
    assert "identik dengan paper yang sudah terbit" in html
    assert "10.18280/ijht.440419" in html
    assert "97% isi dokumen" in html


def test_cover_without_title_or_match_has_no_banner():
    html = _cover_html({"sources": [], "match_groups": []})
    assert "Judul Dokumen" not in html
    assert "identik dengan paper" not in html
    assert _publication_block(None) == ""


def test_cover_falls_back_to_filename_for_old_reports():
    html = _cover_html({"source_filename": "lama.pdf", "sources": [], "match_groups": []})
    assert "lama" in html and "Judul Dokumen" in html
