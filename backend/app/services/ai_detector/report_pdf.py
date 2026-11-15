"""Laporan PDF deteksi AI berformat SAMA dengan berkas asli.

Seperti laporan plagiarisme, modul ini TIDAK membangun ulang dokumen dari teks
(yang akan menghilangkan tata letak). Sebaliknya ia menempelkan sorotan
(highlight) per-segmen DI ATAS PDF asli memakai PyMuPDF — sehingga kolom, font,
gambar, dan format asli tetap utuh. Warna sorotan mengikuti klasifikasi segmen:
merah = terindikasi AI, kuning = campuran, hijau = manusia — identik dengan
"Peta Segmen Dokumen" pada tampilan web. Tidak ada pemotongan teks: SELURUH
halaman diperiksa terhadap SEMUA segmen, berapa pun panjang dokumen.
"""

from __future__ import annotations

import html as _html
import re

import fitz  # PyMuPDF

from app.services.report import render_pdf

# Pemisah kalimat sederhana (mandiri agar modul laporan tak bergantung internal
# detektor). search_for PyMuPDF paling andal pada potongan sepanjang kalimat.
_SENT_RE = re.compile(r"[^.!?\n]+[.!?]*")

# Warna sorotan per-kategori: (fill RGB 0..1 untuk highlight, hex untuk swatch).
_LABEL_STYLE: dict[str, dict] = {
    "ai": {"fill": (0.984, 0.792, 0.792), "hex": "#ef4444", "name": "Terindikasi AI"},
    "mixed": {"fill": (0.996, 0.925, 0.733), "hex": "#f59e0b", "name": "Campuran"},
    "human": {"fill": (0.835, 0.976, 0.886), "hex": "#10b981", "name": "Manusia"},
}
_OPACITY = {"ai": 0.42, "mixed": 0.40, "human": 0.28}


def _esc(s: object) -> str:
    return _html.escape("" if s is None else str(s))


def _ring_tone(v: float) -> str:
    if v >= 60:
        return "#e11d48"
    if v >= 40:
        return "#f59e0b"
    return "#16a34a"


def _segment_texts(result: dict) -> list[tuple[str, str]]:
    """(teks_segmen, label) untuk tiap segmen, diambil dari input_text via offset.

    Bila ``input_text`` tak tersimpan (riwayat lama), jatuh ke ``text``/``preview``
    per segmen. Tidak ada batas panjang — seluruh dokumen diproses.
    """
    segments = result.get("segments") or []
    full = result.get("input_text")
    out: list[tuple[str, str]] = []
    for s in segments:
        label = str(s.get("label") or "human")
        txt = ""
        if isinstance(full, str) and s.get("start") is not None and s.get("end") is not None:
            txt = full[int(s["start"]): int(s["end"])]
        if not txt:
            txt = str(s.get("text") or s.get("preview") or "")
        if txt.strip():
            out.append((txt, label))
    return out


def _cover_html(result: dict, meta: dict | None = None) -> str:
    """Halaman sampul 'Ringkasan Deteksi AI' (desain orisinal)."""
    meta = meta or {}
    prob = float(result.get("ai_probability") or 0)
    verdict = str(result.get("verdict") or "—")
    bd = result.get("breakdown") or {}
    ai_p = max(0.0, min(100.0, float(bd.get("ai") or 0)))
    unc_p = max(0.0, min(100.0, float(bd.get("uncertain") or 0)))
    hum_p = max(0.0, min(100.0, float(bd.get("human") or 0)))
    segs = result.get("segments") or []
    n_seg = len(segs)
    sig = result.get("signals") or {}
    words = sig.get("word_count") or meta.get("words") or "—"
    lang = str(result.get("language") or "-").upper()
    rid = result.get("report_id", "") or meta.get("history_id", "") or ""
    tone = _ring_tone(prob)
    title = _esc(str(meta.get("title") or result.get("source_filename") or "Dokumen"))

    counts = {"ai": 0, "mixed": 0, "human": 0}
    for s in segs:
        counts[str(s.get("label") or "human")] = counts.get(
            str(s.get("label") or "human"), 0) + 1

    legend_rows = ""
    for key in ("ai", "mixed", "human"):
        st = _LABEL_STYLE[key]
        legend_rows += (
            f'<tr><td style="width:14px"><span style="display:inline-block;width:11px;'
            f'height:11px;border-radius:3px;background:{st["hex"]}"></span></td>'
            f'<td style="font-weight:700;width:120px">{st["name"]}</td>'
            f'<td style="color:#64748b">{counts.get(key, 0)} segmen</td></tr>'
        )

    reason = (result.get("report") or {}).get("llm_skipped_reason")
    reason_html = (
        f'<div style="margin-top:10px;font-size:11px;color:#64748b">{_esc(reason)}</div>'
        if reason else ""
    )
    warnings = result.get("warnings") or []
    warn_html = ""
    if warnings:
        lis = "".join(f"<li>{_esc(str(w))}</li>" for w in warnings)
        warn_html = (
            '<div style="margin-top:10px;padding:8px 12px;border-left:3px solid #f59e0b;'
            f'background:#fffbeb;border-radius:6px;font-size:11px"><b>Peringatan</b>'
            f'<ul style="margin:4px 0 0 16px;padding:0">{lis}</ul></div>'
        )

    return f"""
    <div style="font-family:Helvetica,Arial,sans-serif;color:#0f172a">
      <div style="display:flex;justify-content:space-between;align-items:center;
                  border-bottom:2px solid {tone};padding-bottom:8px;margin-bottom:14px">
        <div style="font-size:20px;font-weight:800">Ringkasan Deteksi AI</div>
        <div style="font-size:11px;color:#64748b">ICALORA-LABS{f' · ID {rid}' if rid else ''}</div>
      </div>
      <div style="font-size:13px;margin-bottom:12px;color:#334155">{title}</div>

      <div style="display:flex;gap:18px;align-items:center;margin-bottom:16px">
        <div style="width:120px;height:120px;border-radius:50%;border:12px solid {tone};
                    display:flex;align-items:center;justify-content:center;flex-direction:column">
          <div style="font-size:26px;font-weight:800;color:{tone}">{prob:.1f}%</div>
          <div style="font-size:10px;color:#64748b">Probabilitas AI</div>
        </div>
        <div>
          <div style="font-size:11px;color:#64748b;margin-bottom:4px">Kesimpulan</div>
          <div style="font-size:16px;font-weight:800;color:{tone}">{_esc(verdict)}</div>
          <div style="font-size:11px;color:#64748b;margin-top:8px">
            Bahasa {_esc(lang)} · {_esc(words)} kata · {n_seg} segmen</div>
        </div>
      </div>

      <div style="font-weight:700;font-size:12px;margin-bottom:6px">Komposisi Teks</div>
      <div style="display:flex;width:100%;border-radius:6px;overflow:hidden;
                  margin-bottom:6px;height:16px">
        <span style="width:{ai_p:.1f}%;background:#ef4444"></span>
        <span style="width:{unc_p:.1f}%;background:#f59e0b"></span>
        <span style="width:{hum_p:.1f}%;background:#10b981"></span>
      </div>
      <div style="font-size:11px;color:#64748b;margin-bottom:16px">
        <span style="color:#ef4444">&#9679;</span> AI {ai_p:.1f}% &nbsp;
        <span style="color:#f59e0b">&#9679;</span> tidak pasti {unc_p:.1f}% &nbsp;
        <span style="color:#10b981">&#9679;</span> manusia {hum_p:.1f}%</div>

      <div style="font-weight:700;font-size:12px;margin-bottom:6px">
        Penanda Sorotan pada Dokumen</div>
      <table style="font-size:12px;border-collapse:collapse;width:100%">{legend_rows}</table>
      {warn_html}
      {reason_html}
      <div style="margin-top:14px;font-size:10px;color:#94a3b8">
        Sorotan ditempel di atas berkas asli tanpa mengubah tata letak. Skor adalah
        estimasi statistik pola teks, bukan bukti kepengarangan.</div>
    </div>
    """


def _add_header_footer(page: fitz.Page, rid: str, page_no: int, total: int) -> None:
    rect = page.rect
    gray = (0.42, 0.45, 0.50)
    try:
        page.insert_text(
            (rect.x0 + 18, rect.y0 + 14),
            "ICALORA-LABS · Deteksi AI · Dokumen dengan Sorotan",
            fontsize=7, color=gray,
        )
        if rid:
            page.insert_text(
                (rect.x1 - 150, rect.y0 + 14), f"ID {rid}", fontsize=7, color=gray
            )
        page.insert_text(
            (rect.x1 - 70, rect.y1 - 10),
            f"Hal. {page_no}/{total}", fontsize=7, color=gray,
        )
    except Exception:  # noqa: BLE001, S110
        pass


def annotate_ai_pdf(original_pdf: bytes, result: dict) -> bytes:
    """Tempel sorotan per-segmen (per kalimat) di atas PDF asli.

    Setiap segmen dipecah jadi kalimat; tiap kalimat dicari di SELURUH halaman
    dan disorot sesuai warna kategori segmen. Pra-filter teks halaman menjaga
    kecepatan walau dokumen ratusan halaman.
    """
    doc = fitz.open(stream=original_pdf, filetype="pdf")
    total = doc.page_count
    rid = str(result.get("report_id", "") or "")

    # (kalimat, probe_lower, fill_rgb, opacity) — dedup kalimat identik.
    items: list[tuple[str, str, tuple, float]] = []
    seen: set[str] = set()
    for seg_text, label in _segment_texts(result):
        style = _LABEL_STYLE.get(label, _LABEL_STYLE["human"])
        op = _OPACITY.get(label, 0.3)
        for m in _SENT_RE.finditer(seg_text):
            sent = m.group(0).strip()
            if len(sent) < 12:
                continue
            key = sent[:80].lower()
            if key in seen:
                continue
            seen.add(key)
            items.append((sent, sent[:60].lower(), style["fill"], op))

    for pno in range(total):
        page = doc[pno]
        page_text = page.get_text("text").lower()
        for sent, probe, fill, op in items:
            if probe and probe not in page_text:
                continue
            quads = page.search_for(sent, quads=True)
            if not quads:
                frag = sent[:60]
                if len(frag) >= 12:
                    quads = page.search_for(frag, quads=True)
            for q in quads[:8]:
                try:
                    annot = page.add_highlight_annot(q)
                    annot.set_colors(stroke=fill)
                    annot.update(opacity=op)
                except Exception:  # noqa: BLE001, S110
                    continue
        _add_header_footer(page, rid, pno + 1, total)

    out = doc.tobytes(deflate=True, garbage=3)
    doc.close()
    return out


def build_ai_report_pdf(original_pdf: bytes, result: dict, meta: dict | None = None) -> bytes:
    """Gabungkan sampul Ringkasan Deteksi AI + PDF asli bersorotan segmen."""
    cover = render_pdf(_cover_html(result, meta))
    annotated = annotate_ai_pdf(original_pdf, result)

    merged = fitz.open(stream=cover, filetype="pdf")
    body = fitz.open(stream=annotated, filetype="pdf")
    merged.insert_pdf(body)
    out = merged.tobytes(deflate=True, garbage=3)
    merged.close()
    body.close()
    return out
