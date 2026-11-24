"""Ekstraksi teks dari berkas unggahan (txt, pdf, docx)."""

from __future__ import annotations

import io
import os
import re
import threading

MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10 MB

_TXT_EXT = {".txt", ".md", ".csv", ".tex"}

# Tanda hubung patah-baris pada PDF (teks justified/2-kolom) kerap terekstrak
# sebagai "reduc- ing" / "effi-\ncient" — kata yang sebenarnya UTUH terpecah.
# Ini menurunkan kecocokan teks secara keliru (pemeriksaan plagiarisme menilai
# TEKS, bukan tata letak), jadi disatukan kembali. Hanya menyatukan bila tanda
# hubung diikuti spasi/baris-baru lalu HURUF KECIL — pola khas pemenggalan kata;
# tanda hubung majemuk sah ("inter-cluster", tanpa spasi) tidak terpengaruh.
_HYPHEN_BREAK_RE = re.compile(r"(\w)-\s+([a-z])")


def _dehyphenate(text: str) -> str:
    return _HYPHEN_BREAK_RE.sub(r"\1\2", text or "")


# Karakter kontrol C0 (kecuali tab/baris-baru/carriage-return) kerap muncul
# sebagai sampah dari ekstraksi PDF rusak. NUL (\x00) KHUSUSNYA tidak bisa
# disimpan Postgres di kolom text/jsonb ("unsupported Unicode escape \u0000"),
# sehingga riwayat tool GAGAL disimpan. Buang semua agar teks aman diproses
# maupun disimpan, tanpa mengubah konten yang bermakna.
_CONTROL_CHARS_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")
# Ligatur tipografi PDF ("ﬁ" dst.) tak cocok dengan teks sumber/kueri pencarian. Sengaja BUKAN NFKC
# penuh: NFKC juga mengubah superskrip/satuan ("m²" -> "m2") yang merusak pencocokan rumus.
_LIGATURES = {
    0xFB00: "ff",
    0xFB01: "fi",
    0xFB02: "fl",
    0xFB03: "ffi",
    0xFB04: "ffl",
    0xFB05: "st",
    0xFB06: "st",
}


def expand_ligatures(text: str) -> str:
    """Urai ligatur tipografi ("ﬁ" -> "fi"); dipakai juga untuk teks yang ditempel."""
    return (text or "").translate(_LIGATURES)


def sanitize_text(text: str) -> str:
    """Buang NUL & karakter kontrol C0 non-cetak, dan urai ligatur tipografi."""
    return expand_ligatures(_CONTROL_CHARS_RE.sub("", text or ""))


def _tika_extract(data: bytes, content_type: str) -> str:
    """Ekstrak teks via Apache Tika lokal (PDFBox) sebagai cadangan tangguh.

    Tika sering menangkap PDF 2-kolom/tabel lebih lengkap daripada pypdf.
    Dipakai hanya bila diaktifkan & hasil pypdf terlalu pendek. Gagal-aman:
    kembalikan "" bila port Tika mati (fitur mundur ke hasil pypdf).
    """
    from app.core.config import get_settings

    s = get_settings()
    if not s.tika_enabled or not s.tika_url:
        return ""
    import httpx

    try:
        resp = httpx.put(
            f"{s.tika_url.rstrip('/')}/tika",
            content=data,
            headers={"Content-Type": content_type, "Accept": "text/plain"},
            timeout=60.0,
        )
        if resp.status_code != 200:
            return ""
        return resp.text or ""
    except Exception:  # noqa: BLE001
        return ""


def _extract_pdf(data: bytes) -> str:
    from pypdf import PdfReader

    try:
        reader = PdfReader(io.BytesIO(data))
        text = "\n".join(page.extract_text() or "" for page in reader.pages)
    except Exception:  # noqa: BLE001
        text = ""
    # Bila pypdf menghasilkan sedikit teks (PDF kompleks/2-kolom/berbasis
    # layer aneh), coba Tika yang kerap lebih lengkap; pakai yang lebih panjang.
    from app.core.config import get_settings

    if len(text) < get_settings().tika_fallback_min_chars:
        tika_text = _tika_extract(data, "application/pdf")
        if len(tika_text) > len(text):
            text = tika_text
    return _dehyphenate(text)


def _extract_docx(data: bytes) -> str:
    from docx import Document

    try:
        doc = Document(io.BytesIO(data))
        text = "\n".join(p.text for p in doc.paragraphs)
    except Exception:  # noqa: BLE001
        text = ""
    # Bila python-docx gagal/menghasilkan sedikit teks (mis. isi di tabel atau
    # text-box), coba Tika yang membaca struktur docx lebih lengkap.
    from app.core.config import get_settings

    if len(text) < get_settings().tika_fallback_min_chars:
        tika_text = _tika_extract(
            data,
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
        if len(tika_text) > len(text):
            text = tika_text
    return text


def extract_text(filename: str, data: bytes) -> str:
    """Kembalikan teks mentah dari berkas. Melempar ValueError bila gagal."""
    name = (filename or "").lower()

    if any(name.endswith(ext) for ext in _TXT_EXT):
        for enc in ("utf-8", "latin-1"):
            try:
                return sanitize_text(data.decode(enc))
            except UnicodeDecodeError:
                continue
        raise ValueError("Encoding berkas teks tidak dikenali.")

    if name.endswith(".pdf"):
        try:
            return sanitize_text(_extract_pdf(data))
        except Exception as exc:  # noqa: BLE001
            raise ValueError(f"Gagal membaca PDF: {exc}") from exc

    if name.endswith(".docx"):
        try:
            return sanitize_text(_extract_docx(data))
        except Exception as exc:  # noqa: BLE001
            raise ValueError(f"Gagal membaca DOCX: {exc}") from exc

    raise ValueError("Format tidak didukung. Gunakan .txt, .pdf, atau .docx.")


# ── OCR untuk PDF hasil pindaian ─────────────────────────────────────────────
# Satu OCR dalam satu waktu: Tesseract memakai banyak CPU di server bersama.
_OCR_LOCK = threading.Semaphore(1)
os.environ.setdefault("OMP_THREAD_LIMIT", "2")


class OcrUnavailableError(RuntimeError):
    """OCR tidak aktif atau data bahasa Tesseract tidak terpasang."""


def ocr_available() -> bool:
    """True bila OCR diaktifkan dan data bahasa Tesseract tersedia."""
    from app.core.config import get_settings

    if not get_settings().ocr_enabled:
        return False
    try:
        import pymupdf

        return bool(pymupdf.get_tessdata())
    except Exception:  # noqa: BLE001
        return False


def pdf_page_count(data: bytes) -> int:
    try:
        import pymupdf

        with pymupdf.open(stream=data, filetype="pdf") as doc:
            return doc.page_count
    except Exception:  # noqa: BLE001
        return 0


def is_scanned_pdf(data: bytes, text: str = "") -> bool:
    """PDF yang lapisan teks ASLI-nya hampir kosong per halaman = hasil pindaian.

    Yang dinilai lapisan teks PDF itu sendiri, BUKAN hasil `extract_text`: Tika
    (cadangan ekstraksi) bisa mengenali gambar halaman sehingga teks tampak ada,
    padahal PDF asli yang disimpan untuk laporan hanya gambar — tak bisa diberi
    sorotan. `text` hanya dipakai bila PDF tak bisa dibuka.
    """
    from app.core.config import get_settings

    threshold = get_settings().scanned_min_chars_per_page
    try:
        import pymupdf

        with pymupdf.open(stream=data, filetype="pdf") as doc:
            if doc.page_count <= 0:
                return False
            native = sum(len(page.get_text().strip()) for page in doc)
            return native / doc.page_count < threshold
    except Exception:  # noqa: BLE001
        pages = pdf_page_count(data)
        return pages > 0 and len((text or "").strip()) / pages < threshold


def ocr_pdf(data: bytes) -> tuple[bytes, str]:
    """OCR PDF pindaian -> (PDF yang bisa dicari, teks).

    PDF hasil memuat gambar halaman + lapisan teks tak kasat mata, sehingga
    pencarian teks (dan sorotan laporan) bekerja di atasnya.
    Melempar OcrUnavailableError / ValueError dengan pesan siap-tampil.
    """
    import pymupdf

    from app.core.config import get_settings

    st = get_settings()
    if not ocr_available():
        raise OcrUnavailableError(
            "OCR belum tersedia di server. Unggah PDF yang memuat teks (bukan hasil pindaian)."
        )
    pages = pdf_page_count(data)
    if pages <= 0:
        raise ValueError("PDF tidak dapat dibaca.")
    if pages > st.ocr_max_pages:
        raise ValueError(
            f"PDF pindaian berisi {pages} halaman; batas OCR {st.ocr_max_pages} halaman. "
            "Pisahkan dokumen lalu unggah ulang."
        )
    with _OCR_LOCK:
        src = pymupdf.open(stream=data, filetype="pdf")
        out = pymupdf.open()
        try:
            for page in src:
                pix = page.get_pixmap(dpi=st.ocr_dpi)
                page_pdf = pymupdf.open(
                    "pdf", pix.pdfocr_tobytes(compress=True, language=st.ocr_lang)
                )
                out.insert_pdf(page_pdf)
                page_pdf.close()
            text = "\n".join(p.get_text() for p in out)
            pdf_bytes = out.tobytes(deflate=True, garbage=3)
        finally:
            src.close()
            out.close()
    return pdf_bytes, _dehyphenate(sanitize_text(text))
