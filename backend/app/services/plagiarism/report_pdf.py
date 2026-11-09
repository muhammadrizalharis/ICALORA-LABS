"""Bangun laporan PDF integritas berformat SAMA dengan berkas asli.

Alih-alih membangun ulang dokumen dari teks (kehilangan tata letak), modul ini
menempelkan sorotan (highlight) sebagai anotasi DI ATAS PDF asli memakai
PyMuPDF — sehingga kolom, font, gambar, dan format asli tetap utuh. Yang
ditambahkan hanya: sorotan per-temuan, header, footer, dan satu halaman
sampul "Ringkasan Integritas" (desain orisinal, bukan tiruan alat komersial).
"""

from __future__ import annotations

import html as _html

import fitz  # PyMuPDF

from app.services.report import render_pdf

# Warna sorotan per kategori temuan (RGB 0..1) — skema orisinal.
_GROUP_COLOR = {
    "salinan_langsung": (0.98, 0.45, 0.45),
    "kemiripan_kuat": (0.98, 0.65, 0.30),
    "indikasi_parafrase": (0.98, 0.86, 0.35),
    "sumber_terkredit": (0.45, 0.80, 0.55),
}
_GROUP_HEX = {
    "salinan_langsung": "#e11d48",
    "kemiripan_kuat": "#f97316",
    "indikasi_parafrase": "#eab308",
    "sumber_terkredit": "#22c55e",
}
_GROUP_LABEL = {
    "salinan_langsung": "Salinan Langsung",
    "kemiripan_kuat": "Kemiripan Kuat",
    "indikasi_parafrase": "Indikasi Parafrase",
    "sumber_terkredit": "Sumber Terkredit",
}
_GROUP_DESC = {
    "salinan_langsung": "Teks nyaris identik dengan sumber, tanpa atribusi.",
    "kemiripan_kuat": "Tumpang-tindih kata tinggi walau sebagian ditata ulang.",
    "indikasi_parafrase": "Kemiripan makna dengan sebagian kata diubah.",
    "sumber_terkredit": "Dikutip dan disitasi dengan benar — bukan risiko.",
}


def _esc(s: str) -> str:
    return _html.escape(s or "")


def _ring_tone(v: float) -> str:
    if v >= 30:
        return "#e11d48"
    if v >= 15:
        return "#f97316"
    return "#16a34a"


def _cover_html(report: dict) -> str:
    """Halaman sampul 'Ringkasan Integritas' — tata letak & istilah orisinal."""
    idx = float(report.get("integrity_index", report.get("overall_similarity", 0)) or 0)
    idx_display = ("&lt;1%" if 0 < idx < 1 else f"{idx:.1f}%" if idx < 10 else f"{idx:.0f}%")
    copy_sim = float(report.get("copy_similarity", 0) or 0)
    para = float(report.get("paraphrase_similarity", 0) or 0)
    wc = int(report.get("word_count", 0) or 0)
    cc = int(report.get("char_count", 0) or 0)
    matched = int(report.get("matched_sentences", 0) or 0)
    total = int(report.get("total_sentences", 0) or 0)
    rid = report.get("report_id", "") or ""
    sha = (report.get("content_sha256", "") or "")[:16]
    tone = _ring_tone(idx)

    groups = {g.get("type"): g for g in report.get("match_groups", [])}
    rows = ""
    for key in ["salinan_langsung", "kemiripan_kuat", "indikasi_parafrase", "sumber_terkredit"]:
        g = groups.get(key, {})
        pct = float(g.get("percent", 0) or 0)
        cnt = int(g.get("count", 0) or 0)
        rows += (
            f'<tr>'
            f'<td style="width:14px"><span style="display:inline-block;width:11px;height:11px;'
            f'border-radius:50%;background:{_GROUP_HEX[key]}"></span></td>'
            f'<td style="font-weight:700;width:70px">{pct:.1f}%</td>'
            f'<td><b>{_GROUP_LABEL[key]}</b><div style="color:#64748b;font-size:11px">'
            f'{_GROUP_DESC[key]} · {cnt} bagian</div></td>'
            f'</tr>'
        )

    srcs = report.get("sources", [])[:10]
    src_rows = ""
    for i, s in enumerate(srcs, 1):
        sim = float(s.get("similarity", 0) or 0)
        title = _esc(str(s.get("title") or "Tanpa judul"))
        meta = _esc(str(s.get("source") or ""))
        yr = s.get("pub_year")
        badge = (
            ' <span style="background:#0ea5e9;color:#fff;border-radius:3px;'
            'padding:0 5px;font-size:9px;font-weight:700">DARING</span>'
            if s.get("online")
            else ""
        )
        contain = float(s.get("source_containment", 0) or 0)
        contain_txt = (
            f" · abstrak {contain:.0f}% termuat" if s.get("online") and contain else ""
        )
        src_rows += (
            f'<tr><td style="font-weight:700;width:60px">{sim:.1f}%</td>'
            f'<td><b>{i}. {title}</b>{badge}<div style="color:#64748b;font-size:11px">'
            f'{meta}{(" · " + str(yr)) if yr else ""}{contain_txt}</div></td></tr>'
        )

    online_note = ""
    providers = report.get("online_providers") or []
    if report.get("online_merged") and providers:
        names = _esc(", ".join(str(p.get("name")) for p in providers))
        online_note = (
            '<div class="note" style="margin-top:6px">🌐 Indeks ini juga mencakup '
            f"pencocokan real-time tanpa-unduh ke sumber daring: {names}.</div>"
        )

    pub_banner = ""
    pm = report.get("publication_match")
    if pm:
        contain = float(pm.get("containment", 0) or 0)
        src_label = _esc(str(pm.get("title") or pm.get("doi") or "(tanpa judul)"))
        src_meta = _esc(str(pm.get("source") or ""))
        online_tag = " (abstrak daring)" if pm.get("online") else ""
        if pm.get("by_doi"):
            pub_banner = (
                '<div class="pubmatch"><b>⚠️ Terdeteksi sebagai publikasi terindeks (identitas DOI).</b> '
                "Dokumen ini mencantumkan DOI yang sama dengan karya terbit di korpus — "
                "kemungkinan besar merupakan karya yang sudah dipublikasikan itu sendiri "
                "(atau duplikasi/self-plagiarism). Sumber: "
                f"<b>{src_label}</b>{(' · ' + src_meta) if src_meta else ''}. "
                "<span style=\"color:#7c2d12\">Catatan: korpus daring umumnya hanya memaparkan "
                "abstrak (teks penuh berbayar/berhak cipta), sehingga Indeks Kemiripan "
                "baris-per-baris tetap rendah; identitas publikasi ini dihitung terpisah.</span></div>"
            )
        else:
            pub_banner = (
                '<div class="pubmatch"><b>⚠️ Terdeteksi sebagai publikasi terindeks.</b> '
                f"{contain:.0f}% teks sumber{online_tag} termuat di dokumen ini — kemungkinan "
                "karya sudah dipublikasikan (atau self-plagiarism/duplikasi). Sumber: "
                f"<b>{src_label}</b>{(' · ' + src_meta) if src_meta else ''}. "
                "<span style=\"color:#7c2d12\">Catatan: sumber daring hanya memaparkan abstrak, "
                "sehingga Indeks Kemiripan baris-per-baris tetap rendah; sinyal identitas ini "
                "dihitung terpisah.</span></div>"
            )

    return f"""<!doctype html><html><head><meta charset="utf-8"><style>
    @page {{ size: A4; margin: 24mm 18mm; }}
    body {{ font-family: 'Helvetica','Arial',sans-serif; color:#0f172a; font-size:12px; }}
    .head {{ display:flex; justify-content:space-between; border-bottom:2px solid #0f172a;
             padding-bottom:8px; margin-bottom:16px; }}
    .brand {{ font-size:18px; font-weight:800; }}
    .sub {{ color:#64748b; font-size:11px; }}
    .rid {{ text-align:right; color:#475569; font-size:11px; }}
    .hero {{ display:flex; gap:20px; align-items:center; margin:18px 0; }}
    .ring {{ width:120px; height:120px; border-radius:50%; border:10px solid {tone};
             display:flex; flex-direction:column; align-items:center; justify-content:center; }}
    .ring .n {{ font-size:30px; font-weight:800; color:{tone}; }}
    .ring .l {{ font-size:9px; letter-spacing:1px; color:#64748b; }}
    h2 {{ font-size:13px; margin:18px 0 8px; text-transform:uppercase; letter-spacing:.5px; }}
    table {{ width:100%; border-collapse:collapse; }}
    td {{ padding:6px 4px; border-bottom:1px solid #eef2f7; vertical-align:top; }}
    .stat {{ display:inline-block; margin-right:18px; }}
    .stat b {{ font-size:15px; }}
    .note {{ color:#64748b; font-size:11px; margin-top:6px; }}
    .pubmatch {{ background:#fff7ed; border:1px solid #fdba74; border-left:4px solid #ea580c;
                 border-radius:8px; padding:9px 13px; margin:12px 0; font-size:11px;
                 color:#9a3412; line-height:1.5; }}
    </style></head><body>
    <div class="head">
      <div><div class="brand">Ringkasan Integritas</div>
      <div class="sub">ICALORA-LABS · MRH INNOVEX — pemeriksaan mandiri (self-hosted)</div></div>
      <div class="rid">ID: <b>{_esc(rid)}</b><br>Hash: {_esc(sha)}<br>Korpus akses-terbuka</div>
    </div>
    {pub_banner}
    <div class="hero">
      <div class="ring"><div class="n">{idx_display}</div><div class="l">INTEGRITAS</div></div>
      <div>
        <div style="font-size:16px;font-weight:700">Indeks Integritas {idx:.1f}%</div>
        <div class="note">Gabungan tumpang-tindih teks ({copy_sim:.1f}%) dan indikasi
        parafrase semantik (hingga {para:.0f}%). Angka adalah alat bantu tinjauan,
        bukan vonis akhir.</div>
        <div style="margin-top:10px">
          <span class="stat"><b>{wc:,}</b> kata</span>
          <span class="stat"><b>{cc:,}</b> karakter</span>
          <span class="stat"><b>{matched}/{total}</b> kalimat cocok</span>
        </div>
      </div>
    </div>
    <h2>Kategori Temuan</h2>
    <table>{rows}</table>
    <h2>Sumber Teratas</h2>
    <table>{src_rows or '<tr><td class="note">Tidak ada sumber dengan kemiripan berarti.</td></tr>'}</table>
    {online_note}
    <div class="note" style="margin-top:18px">Halaman berikut menampilkan dokumen asli
    Anda dengan format utuh; bagian yang cocok diberi sorotan sesuai warna kategori di atas.</div>
    </body></html>"""


def _add_header_footer(page: fitz.Page, report: dict, page_no: int, total: int) -> None:
    rect = page.rect
    rid = str(report.get("report_id", "") or "")
    gray = (0.42, 0.45, 0.50)
    try:
        page.insert_text(
            (rect.x0 + 18, rect.y0 + 14),
            "ICALORA-LABS · Dokumen dengan Sorotan",
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


def annotate_pdf(original_pdf: bytes, report: dict) -> bytes:
    """Tempel sorotan per-temuan di atas PDF asli + header/footer tiap halaman."""
    doc = fitz.open(stream=original_pdf, filetype="pdf")
    passages = report.get("matched_passages", []) or []
    total = doc.page_count

    for pno in range(total):
        page = doc[pno]
        for p in passages:
            sent = (p.get("sentence") or "").strip()
            if len(sent) < 12:
                continue
            color = _GROUP_COLOR.get(p.get("group"), (0.98, 0.86, 0.35))
            quads = page.search_for(sent, quads=True)
            if not quads:
                # Fallback: cari fragmen awal kalimat (lebih tahan lipatan baris).
                frag = sent[:60]
                if len(frag) >= 12:
                    quads = page.search_for(frag, quads=True)
            for q in quads[:8]:
                try:
                    annot = page.add_highlight_annot(q)
                    annot.set_colors(stroke=color)
                    annot.update(opacity=0.45)
                except Exception:  # noqa: BLE001, S110
                    continue
        _add_header_footer(page, report, pno + 1, total)

    out = doc.tobytes(deflate=True, garbage=3)
    doc.close()
    return out


def build_report_pdf(original_pdf: bytes, report: dict) -> bytes:
    """Gabungkan sampul Ringkasan Integritas + PDF asli bersorotan."""
    cover = render_pdf(_cover_html(report))
    annotated = annotate_pdf(original_pdf, report)

    merged = fitz.open(stream=cover, filetype="pdf")
    body = fitz.open(stream=annotated, filetype="pdf")
    merged.insert_pdf(body)
    out = merged.tobytes(deflate=True, garbage=3)
    merged.close()
    body.close()
    return out
