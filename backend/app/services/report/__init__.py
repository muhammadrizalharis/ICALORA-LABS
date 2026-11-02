"""Konversi HTML laporan menjadi PDF memakai WeasyPrint."""

from __future__ import annotations

from weasyprint import HTML

MAX_HTML_BYTES = 2_000_000


def render_pdf(html: str) -> bytes:
    """Render string HTML (mandiri, inline CSS) menjadi byte PDF."""
    return HTML(string=html).write_pdf()
