"""Laporan PDF grammar checker berformat SAMA dengan berkas asli.

Seperti laporan plagiarisme & deteksi AI, modul ini TIDAK membangun ulang
dokumen dari teks (yang akan menghilangkan tata letak). Sebaliknya ia
menempelkan sorotan (highlight) DI ATAS PDF asli memakai PyMuPDF pada setiap
potongan teks yang bermasalah — sehingga kolom, font, gambar, dan format asli
tetap utuh. Warna sorotan mengikuti tingkat kesalahan: merah = kritis
(mengubah makna/ejaan fatal), oranye = lanjutan (perbaikan gaya). Tidak ada
pemotongan: SELURUH halaman diperiksa terhadap SEMUA masalah, berapa pun
panjang dokumen.
"""

from __future__ import annotations

import re

import fitz  # PyMuPDF

from app.services.report import render_pdf
from app.services.report.reports import grammar_report_html

# Warna sorotan per tingkat: (fill RGB 0..1, opacity).
_SEV_STYLE: dict[str, tuple[tuple[float, float, float], float]] = {
    "critical": ((0.984, 0.792, 0.792), 0.42),  # merah lembut
    "advanced": ((0.996, 0.925, 0.733), 0.40),  # oranye lembut
}
_DEFAULT_STYLE = _SEV_STYLE["advanced"]

_WS_RE = re.compile(r"\s+")


def _probe(snippet: str) -> str:
    """Potongan pendek untuk pra-filter cepat teks halaman."""
    return _WS_RE.sub(" ", snippet).strip()[:60].lower()


def annotate_grammar_pdf(original_pdf: bytes, result: dict) -> bytes:
    """Tempel sorotan pada setiap potongan 'original' bermasalah di PDF asli.

    Setiap potongan dicari di SELURUH halaman dan disorot sesuai tingkatnya.
    Pra-filter teks halaman menjaga kecepatan walau dokumen ratusan halaman.
    """
    doc = fitz.open(stream=original_pdf, filetype="pdf")
    total = doc.page_count

    # (snippet, probe_lower, fill_rgb, opacity) — dedup snippet identik.
    items: list[tuple[str, str, tuple, float]] = []
    seen: set[str] = set()
    for it in result.get("issues") or []:
        snippet = _WS_RE.sub(" ", str(it.get("original") or "")).strip()
        if len(snippet) < 4:
            continue
        key = snippet[:80].lower()
        if key in seen:
            continue
        seen.add(key)
        fill, op = _SEV_STYLE.get(str(it.get("severity") or ""), _DEFAULT_STYLE)
        items.append((snippet, _probe(snippet), fill, op))

    for pno in range(total):
        page = doc[pno]
        page_text = page.get_text("text").lower()
        for snippet, probe, fill, op in items:
            if probe and probe not in page_text:
                continue
            quads = page.search_for(snippet, quads=True)
            if not quads:
                frag = snippet[:60]
                if len(frag) >= 8:
                    quads = page.search_for(frag, quads=True)
            for q in quads[:8]:
                try:
                    annot = page.add_highlight_annot(q)
                    annot.set_colors(stroke=fill)
                    annot.update(opacity=op)
                except Exception:  # noqa: BLE001, S110
                    continue

    out = doc.tobytes(deflate=True, garbage=3)
    doc.close()
    return out


def build_grammar_report_pdf(
    original_pdf: bytes, result: dict, meta: dict | None = None
) -> bytes:
    """Gabungkan sampul Ringkasan Tata Bahasa + PDF asli bersorotan masalah."""
    cover = render_pdf(grammar_report_html(result, meta))
    annotated = annotate_grammar_pdf(original_pdf, result)

    merged = fitz.open(stream=cover, filetype="pdf")
    body = fitz.open(stream=annotated, filetype="pdf")
    merged.insert_pdf(body)
    out = merged.tobytes(deflate=True, garbage=3)
    merged.close()
    body.close()
    return out
