"""PDF hasil pindaian: deteksi, pesan jelas, dan OCR."""

import pymupdf
import pytest

from app.services import file_extract
from app.services.file_extract import (
    OcrUnavailableError,
    is_scanned_pdf,
    ocr_available,
    ocr_pdf,
)

_TEXT = "Local scour around bridge piers is a major cause of foundation instability. " * 6


def _text_pdf() -> bytes:
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_textbox(pymupdf.Rect(40, 40, 555, 800), _TEXT, fontsize=11)
    return doc.tobytes()


def _scanned_pdf() -> bytes:
    """PDF berisi HANYA gambar halaman (tanpa lapisan teks) = pindaian."""
    src = pymupdf.open(stream=_text_pdf(), filetype="pdf")
    pix = src[0].get_pixmap(dpi=200)
    doc = pymupdf.open()
    page = doc.new_page(width=595, height=842)
    page.insert_image(page.rect, pixmap=pix)
    return doc.tobytes()


def test_text_pdf_is_not_scanned_and_image_pdf_is():
    text_pdf, scan_pdf = _text_pdf(), _scanned_pdf()
    assert not is_scanned_pdf(text_pdf, pymupdf.open(stream=text_pdf)[0].get_text())
    assert is_scanned_pdf(scan_pdf, pymupdf.open(stream=scan_pdf)[0].get_text())
    assert not is_scanned_pdf(b"bukan pdf", "")


def test_ocr_unavailable_gives_clear_error(monkeypatch):
    monkeypatch.setattr(file_extract, "ocr_available", lambda: False)
    with pytest.raises(OcrUnavailableError) as e:
        ocr_pdf(_scanned_pdf())
    assert "OCR belum tersedia" in str(e.value)


def test_ocr_rejects_too_many_pages(monkeypatch):
    from app.core.config import get_settings

    monkeypatch.setattr(file_extract, "ocr_available", lambda: True)
    monkeypatch.setattr(get_settings(), "ocr_max_pages", 1)
    doc = pymupdf.open()
    doc.new_page()
    doc.new_page()
    with pytest.raises(ValueError, match="batas OCR 1 halaman"):
        ocr_pdf(doc.tobytes())


@pytest.mark.skipif(not ocr_available(), reason="data bahasa Tesseract tidak terpasang")
def test_ocr_recovers_text_and_makes_pdf_searchable():
    pdf, text = ocr_pdf(_scanned_pdf())
    assert "scour" in text.lower() and "bridge piers" in text.lower()
    doc = pymupdf.open(stream=pdf, filetype="pdf")
    assert doc[0].search_for("foundation instability")
