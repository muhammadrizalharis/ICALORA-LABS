"""Ekstraksi teks dari berkas unggahan (txt, pdf, docx)."""

from __future__ import annotations

import io
import re

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


def _extract_pdf(data: bytes) -> str:
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(data))
    parts = [page.extract_text() or "" for page in reader.pages]
    return _dehyphenate("\n".join(parts))


def _extract_docx(data: bytes) -> str:
    from docx import Document

    doc = Document(io.BytesIO(data))
    return "\n".join(p.text for p in doc.paragraphs)


def extract_text(filename: str, data: bytes) -> str:
    """Kembalikan teks mentah dari berkas. Melempar ValueError bila gagal."""
    name = (filename or "").lower()

    if any(name.endswith(ext) for ext in _TXT_EXT):
        for enc in ("utf-8", "latin-1"):
            try:
                return data.decode(enc)
            except UnicodeDecodeError:
                continue
        raise ValueError("Encoding berkas teks tidak dikenali.")

    if name.endswith(".pdf"):
        try:
            return _extract_pdf(data)
        except Exception as exc:  # noqa: BLE001
            raise ValueError(f"Gagal membaca PDF: {exc}") from exc

    if name.endswith(".docx"):
        try:
            return _extract_docx(data)
        except Exception as exc:  # noqa: BLE001
            raise ValueError(f"Gagal membaca DOCX: {exc}") from exc

    raise ValueError("Format tidak didukung. Gunakan .txt, .pdf, atau .docx.")
