"""Uji laporan PDF beranotasi: sorotan di SEMUA halaman + warna per-sumber,
serta sampul tanpa penomoran & tanpa caption provider daring."""

import fitz

from app.services.plagiarism.report_pdf import (
    _SOURCE_COLORS,
    _cover_html,
    _source_color_map,
    _src_key,
    annotate_pdf,
)


def _make_pdf(pages: list[str]) -> bytes:
    """Bangun PDF sederhana multi-halaman dengan teks yang bisa dicari."""
    doc = fitz.open()
    for body in pages:
        page = doc.new_page()
        page.insert_text((72, 100), body, fontsize=11)
    data = doc.tobytes()
    doc.close()
    return data


def test_annotate_highlights_every_page_not_just_first():
    """Sorotan harus muncul di SEMUA halaman yang memuat kecocokan, bukan
    hanya halaman pertama (regresi: dulu passage dibatasi ~50 → halaman akhir
    luput)."""
    s_a = "The analytical design follows a structured step by step workflow."
    s_b = "These stages operate sequentially to ensure analytical continuity."
    pdf = _make_pdf([f"Page one. {s_a}", f"Page two. {s_b}", f"Page three. {s_a}"])
    report = {
        "sources": [
            {"title": "Source A", "doi": "10.1/a", "doc_id": None, "similarity": 90},
            {"title": "Source B", "doi": "10.2/b", "doc_id": None, "similarity": 40},
        ],
        "matched_passages": [
            {"sentence": s_a, "source_title": "Source A", "source_doi": "10.1/a", "doc_id": None},
            {"sentence": s_b, "source_title": "Source B", "source_doi": "10.2/b", "doc_id": None},
        ],
        "report_id": "T1",
    }
    out = annotate_pdf(pdf, report)
    doc = fitz.open(stream=out, filetype="pdf")
    per_page = []
    for pno in range(doc.page_count):
        cnt = sum(1 for a in doc[pno].annots() if a.type[0] == 8)
        per_page.append(cnt)
    doc.close()
    # Halaman 1 (s_a), 2 (s_b) dan 3 (s_a) semuanya harus tersorot.
    assert per_page[0] > 0
    assert per_page[1] > 0
    assert per_page[2] > 0


def test_annotate_no_passage_cap_large_document():
    """Dokumen besar: TIAP halaman dengan kecocokan harus tersorot, walau
    jumlah passage jauh melebihi batas lama (regresi: cap 50/5000 membuat
    halaman akhir luput pada naskah puluhan/ratusan halaman)."""
    n_pages = 80
    sentences = [
        f"Unique analytical passage number {i} describing a distinct finding here."
        for i in range(n_pages)
    ]
    pdf = _make_pdf([f"Page {i}. {sentences[i]}" for i in range(n_pages)])
    report = {
        "sources": [{"title": "Src", "doi": "10.1/s", "doc_id": None, "similarity": 90}],
        "matched_passages": [
            {"sentence": s, "source_title": "Src", "source_doi": "10.1/s", "doc_id": None}
            for s in sentences
        ],
        "report_id": "BIG",
    }
    out = annotate_pdf(pdf, report)
    doc = fitz.open(stream=out, filetype="pdf")
    highlighted_pages = sum(
        1 for pno in range(doc.page_count)
        if any(a.type[0] == 8 for a in doc[pno].annots())
    )
    doc.close()
    # Setiap halaman memuat satu passage unik → semua halaman tersorot.
    assert highlighted_pages == n_pages


def test_annotate_colors_by_source():
    """Tiap sumber memakai warna berbeda, bukan warna kategori seragam."""
    s_a = "The analytical design follows a structured step by step workflow."
    s_b = "These stages operate sequentially to ensure analytical continuity."
    pdf = _make_pdf([s_a, s_b])
    report = {
        "sources": [
            {"title": "Source A", "doi": "10.1/a", "doc_id": None, "similarity": 90},
            {"title": "Source B", "doi": "10.2/b", "doc_id": None, "similarity": 40},
        ],
        "matched_passages": [
            {"sentence": s_a, "source_title": "Source A", "source_doi": "10.1/a", "doc_id": None},
            {"sentence": s_b, "source_title": "Source B", "source_doi": "10.2/b", "doc_id": None},
        ],
        "report_id": "T2",
    }
    out = annotate_pdf(pdf, report)
    doc = fitz.open(stream=out, filetype="pdf")
    colors = set()
    for pno in range(doc.page_count):
        for a in doc[pno].annots():
            if a.type[0] == 8:
                c = a.colors.get("stroke")
                if c:
                    colors.add(tuple(round(x, 2) for x in c))
    doc.close()
    assert len(colors) >= 2  # dua sumber → dua warna


def test_source_color_map_matches_source_order():
    report = {
        "sources": [
            {"title": "First", "doi": None, "doc_id": None},
            {"title": "Second", "doi": None, "doc_id": None},
        ],
        "matched_passages": [],
    }
    cmap = _source_color_map(report)
    assert cmap[_src_key("First", None, None)] == 0
    assert cmap[_src_key("Second", None, None)] == 1
    assert _SOURCE_COLORS[0]["hex"] != _SOURCE_COLORS[1]["hex"]


def test_cover_has_no_numbering_or_online_caption():
    report = {
        "integrity_index": 50.0,
        "copy_similarity": 50.0,
        "paraphrase_similarity": 30.0,
        "word_count": 100,
        "char_count": 600,
        "matched_sentences": 10,
        "total_sentences": 20,
        "report_id": "RID",
        "content_sha256": "deadbeef",
        "match_groups": [{"type": "salinan_langsung", "percent": 50, "count": 5}],
        "sources": [
            {"title": "Regional Urban Heat", "doi": "10.1/x", "doc_id": None,
             "similarity": 94.4, "source": "Crossref", "online": True},
        ],
        "matched_passages": [],
        "online_merged": True,
        "online_providers": [{"name": "Crossref", "hits": 5}, {"name": "CORE", "hits": 3}],
        "exclude_settings": {"bibliography": True, "quotes": False, "min_source_percent": 0},
    }
    html = _cover_html(report)
    assert "Indeks ini juga mencakup" not in html
    assert "1. Regional Urban Heat" not in html
    # Swatch warna sumber (lingkaran) hadir di baris sumber.
    assert "border-radius:50%;background:#" in html
    # Keterangan merujuk warna sumber, bukan kategori.
    assert "warna" in html and "sumbernya" in html
