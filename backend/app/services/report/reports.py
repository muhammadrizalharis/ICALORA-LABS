"""Template HTML (mandiri, inline CSS) untuk laporan PDF fitur.

Dipakai AI-Detector dan Grammar Checker. Di-render ke PDF oleh
``render_pdf`` (WeasyPrint). Semua gaya inline agar tidak bergantung aset luar.
"""

from __future__ import annotations

import html
from datetime import datetime, timezone
from typing import Any

BRAND = "#6366f1"
_INK = "#1b2130"
_MUTE = "#6b7280"
_LINE = "#e5e7eb"


def _esc(v: Any) -> str:
    return html.escape(str(v if v is not None else ""))


def _now_str() -> str:
    return datetime.now(timezone.utc).astimezone().strftime("%d %b %Y, %H:%M")


def _shell(title: str, subtitle: str, body: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="id"><head><meta charset="utf-8"><style>
  @page {{ size: A4; margin: 22mm 18mm; }}
  * {{ box-sizing: border-box; }}
  body {{ font-family: 'Helvetica Neue', Arial, sans-serif; color: {_INK};
         font-size: 11px; line-height: 1.5; }}
  .head {{ border-bottom: 3px solid {BRAND}; padding-bottom: 12px; margin-bottom: 18px; }}
  .brand {{ font-size: 10px; letter-spacing: 2px; text-transform: uppercase;
            color: {BRAND}; font-weight: 700; }}
  h1 {{ font-size: 20px; margin: 4px 0 2px; }}
  .sub {{ color: {_MUTE}; font-size: 10px; }}
  .cards {{ display: flex; gap: 10px; margin: 16px 0; }}
  .card {{ flex: 1; border: 1px solid {_LINE}; border-radius: 10px; padding: 12px; }}
  .card .k {{ font-size: 9px; text-transform: uppercase; letter-spacing: 1px;
             color: {_MUTE}; }}
  .card .v {{ font-size: 22px; font-weight: 700; margin-top: 4px; }}
  h2 {{ font-size: 12px; text-transform: uppercase; letter-spacing: 1px;
        color: {_MUTE}; margin: 22px 0 8px; border-bottom: 1px solid {_LINE};
        padding-bottom: 4px; }}
  table {{ width: 100%; border-collapse: collapse; }}
  th, td {{ text-align: left; padding: 6px 8px; border-bottom: 1px solid {_LINE};
            vertical-align: top; }}
  th {{ font-size: 9px; text-transform: uppercase; letter-spacing: 1px; color: {_MUTE}; }}
  .pill {{ display: inline-block; padding: 2px 8px; border-radius: 999px;
           font-size: 9px; font-weight: 700; }}
  .muted {{ color: {_MUTE}; }}
  .bar {{ height: 8px; border-radius: 999px; background: #eef0f6; overflow: hidden; }}
  .bar > span {{ display: block; height: 100%; background: {BRAND}; }}
  .note {{ margin-top: 20px; padding: 10px 12px; border-left: 3px solid {BRAND};
           background: #f6f7fb; border-radius: 6px; color: {_MUTE}; font-size: 9.5px; }}
  .doc {{ border: 1px solid {_LINE}; border-radius: 8px; padding: 12px;
          white-space: pre-wrap; word-wrap: break-word; font-size: 10px;
          line-height: 1.65; margin-top: 6px; }}
  .doc span {{ border-radius: 3px; padding: 0 1px; }}
  .legend {{ font-size: 9.5px; color: {_MUTE}; margin: 2px 0 2px; }}
  .legend b {{ padding: 1px 7px; border-radius: 4px; font-weight: 700;
               color: {_INK}; margin-right: 4px; }}
  .foot {{ margin-top: 26px; border-top: 1px solid {_LINE}; padding-top: 8px;
           color: {_MUTE}; font-size: 9px; display: flex; justify-content: space-between; }}
</style></head><body>
  <div class="head">
    <div class="brand">ICALORA&nbsp;LABS</div>
    <h1>{_esc(title)}</h1>
    <div class="sub">{_esc(subtitle)}</div>
  </div>
  {body}
  <div class="foot"><span>Dihasilkan {_now_str()}</span>
    <span>icalora-lab.calyzr-ai.my.id</span></div>
</body></html>"""


def _verdict_tone(prob: float) -> str:
    if prob >= 86:
        return "background:#fee2e2;color:#b91c1c;"
    if prob >= 50:
        return "background:#fef3c7;color:#b45309;"
    return "background:#dcfce7;color:#15803d;"


_SEG_BG = {"ai": "#fee2e2", "mixed": "#fef3c7", "human": "#ecfdf5"}
_SEG_NAME = {"ai": "AI", "mixed": "Campuran", "human": "Manusia"}


def _seg_tone(label: str) -> str:
    return f"background:{_SEG_BG.get(label, '#ecfdf5')};"


def _ai_highlight_html(result: dict) -> str:
    """Bagian 'Teks Dianalisis & Peta Segmen': teks penuh dengan sorotan per
    segmen (merah=AI, kuning=campuran, hijau=manusia) + tabel rincian segmen.

    Teks penuh hanya tersedia bila ``input_text`` tersimpan (analisis baru).
    Untuk riwayat lama, tampilkan tabel segmen dari cuplikan yang tersimpan.
    """
    segments = result.get("segments") or []
    if not segments:
        return ""

    legend = (
        "<div class='legend'>Sorotan: "
        "<b style='background:#fee2e2'>AI</b>"
        "<b style='background:#fef3c7'>Campuran</b>"
        "<b style='background:#ecfdf5'>Manusia</b></div>"
    )

    input_text = result.get("input_text")
    doc_html = ""
    if isinstance(input_text, str) and input_text.strip():
        # Tanpa pemotongan: tampilkan seluruh teks (hingga batas keamanan input 2M).
        cap = 2_000_000
        txt = input_text[:cap]
        ordered = sorted(
            (s for s in segments if s.get("start") is not None),
            key=lambda s: int(s.get("start") or 0),
        )
        parts: list[str] = []
        cursor = 0
        for s in ordered:
            st = int(s.get("start") or 0)
            en = min(int(s.get("end") or 0), len(txt))
            if st >= len(txt):
                break
            if st > cursor:
                parts.append(_esc(txt[cursor:st]))
            label = str(s.get("label") or "human")
            ap = s.get("ai_probability")
            title = f"{_SEG_NAME.get(label, label)}"
            if ap is not None:
                title += f" · AI {float(ap):.0f}%"
            parts.append(
                f"<span style='{_seg_tone(label)}' title='{_esc(title)}'>"
                f"{_esc(txt[st:en])}</span>"
            )
            cursor = max(cursor, en)
        if cursor < len(txt):
            parts.append(_esc(txt[cursor:]))
        trunc = (
            "<div class='muted' style='margin-top:4px'>"
            "Teks dipangkas pada 60.000 karakter untuk laporan.</div>"
            if len(input_text) > cap
            else ""
        )
        doc_html = (
            "<h2>Teks Dianalisis &amp; Sorotan Segmen</h2>"
            f"{legend}<div class='doc'>{''.join(parts)}</div>{trunc}"
        )

    seg_rows = []
    for s in segments[:150]:
        label = str(s.get("label") or "human")
        ap = s.get("ai_probability")
        apx = f"{float(ap):.1f}%" if ap is not None else "—"
        prev = _esc(str(s.get("preview") or s.get("text") or "")[:160])
        seg_rows.append(
            "<tr>"
            f"<td style='width:5%'>{_esc(s.get('index'))}</td>"
            f"<td style='width:14%'><span class='pill' style='{_seg_tone(label)};color:{_INK}'>"
            f"{_esc(_SEG_NAME.get(label, label))}</span></td>"
            f"<td style='width:9%;text-align:right'>{_esc(s.get('words') or '—')}</td>"
            f"<td style='width:9%;text-align:right;font-weight:700'>{apx}</td>"
            f"<td class='muted'>{prev}{'…' if prev else ''}</td>"
            "</tr>"
        )
    seg_tbl = (
        "<h2>Rincian Segmen Dokumen</h2>"
        "<table><tr><th>#</th><th>Label</th><th>Kata</th><th>AI%</th><th>Cuplikan</th></tr>"
        + "".join(seg_rows)
        + "</table>"
    )
    hint = (
        ""
        if doc_html
        else "<div class='muted' style='margin-top:4px'>Sorotan teks penuh "
        "tersedia untuk analisis baru (teks asli riwayat lama tidak tersimpan). "
        "Jalankan ulang analisis untuk laporan dengan sorotan lengkap.</div>"
    )
    return doc_html + seg_tbl + hint


def ai_detector_report_html(result: dict, meta: dict | None = None) -> str:
    meta = meta or {}
    prob = float(result.get("ai_probability") or 0)
    verdict = str(result.get("verdict") or "—")
    sig = result.get("signals") or {}
    lang = str(result.get("language") or "-").upper()
    words = sig.get("word_count") or meta.get("words") or "—"

    comp_rows = []
    for key, label in (
        ("stat_probability", "Statistik gaya"),
        ("model_probability", "Model n-gram"),
        ("emb_model_probability", "Model embedding"),
        ("llm_probability", "Pemeriksaan LLM"),
    ):
        v = result.get(key)
        if v is None:
            continue
        pct = max(0.0, min(100.0, float(v)))
        comp_rows.append(
            f"<tr><td style='width:38%'>{_esc(label)}</td>"
            f"<td style='width:46%'><div class='bar'><span style='width:{pct:.0f}%'></span></div></td>"
            f"<td style='text-align:right;font-weight:700'>{pct:.1f}</td></tr>"
        )
    comp = (
        "<table>" + "".join(comp_rows) + "</table>"
        if comp_rows
        else "<div class='muted'>Rincian sinyal tidak tersedia.</div>"
    )

    sig_rows = []
    for key, label in (
        ("burstiness", "Burstiness"),
        ("type_token_ratio", "Rasio tipe-token"),
        ("avg_sentence_length", "Rata-rata panjang kalimat"),
        ("bigram_repetition", "Pengulangan bigram"),
        ("cliche_density", "Kepadatan klise"),
        ("personal_ratio", "Rasio ungkapan personal"),
    ):
        if key in sig and sig[key] is not None:
            sig_rows.append(
                f"<tr><td>{_esc(label)}</td>"
                f"<td style='text-align:right'>{_esc(round(float(sig[key]), 3))}</td></tr>"
            )
    sig_tbl = (
        "<table>" + "".join(sig_rows) + "</table>"
        if sig_rows
        else "<div class='muted'>—</div>"
    )

    flagged = result.get("flagged_sentences") or []
    flag_html = ""
    if flagged:
        items = "".join(
            f"<li style='margin-bottom:6px'>{_esc(str(s)[:300])}</li>"
            for s in flagged[:12]
        )
        flag_html = f"<h2>Kalimat yang Ditandai</h2><ul style='padding-left:16px'>{items}</ul>"

    bd = result.get("breakdown") or {}
    bd_html = ""
    if isinstance(bd, dict) and bd.get("ai") is not None:
        ai_p = max(0.0, min(100.0, float(bd.get("ai") or 0)))
        unc_p = max(0.0, min(100.0, float(bd.get("uncertain") or 0)))
        hum_p = max(0.0, min(100.0, float(bd.get("human") or 0)))
        heading = "Komposisi Teks" if bd.get("basis") == "segmen" else "Tingkat Keyakinan"
        seg = "".join(
            f"<span style='display:inline-block;height:14px;width:{p:.1f}%;background:{c}'></span>"
            for p, c in ((ai_p, "#ef4444"), (unc_p, "#f59e0b"), (hum_p, "#10b981"))
            if p > 0
        )
        note = _esc(bd.get("note") or "")
        bd_html = (
            f"<h2>{heading}</h2>"
            f"<div style='display:flex;width:100%;border-radius:6px;overflow:hidden;margin-bottom:6px'>{seg}</div>"
            f"<div class='muted' style='margin-bottom:6px'>"
            f"<span style='color:#ef4444'>&#9679;</span> AI {ai_p:.1f}% &nbsp; "
            f"<span style='color:#f59e0b'>&#9679;</span> tidak pasti {unc_p:.1f}% &nbsp; "
            f"<span style='color:#10b981'>&#9679;</span> manusia {hum_p:.1f}%</div>"
            f"<div class='muted'>{note}</div>"
        )

    warn_items = [str(w) for w in (result.get("warnings") or []) if w]
    reason = (result.get("report") or {}).get("llm_skipped_reason")
    warn_html = ""
    if warn_items:
        lis = "".join(f"<li style='margin-bottom:4px'>{_esc(w)}</li>" for w in warn_items)
        warn_html += (
            "<div class='note' style='border-left:3px solid #f59e0b'>"
            "<strong>Peringatan</strong>"
            f"<ul style='margin:6px 0 0 16px;padding:0'>{lis}</ul></div>"
        )
    if reason:
        warn_html += f"<div class='note'>{_esc(reason)}</div>"

    body = f"""
  <div class="cards">
    <div class="card"><div class="k">Probabilitas AI</div>
      <div class="v" style="color:{BRAND}">{prob:.1f}%</div></div>
    <div class="card"><div class="k">Kesimpulan</div>
      <div style="margin-top:8px"><span class="pill" style="{_verdict_tone(prob)}">{_esc(verdict)}</span></div></div>
    <div class="card"><div class="k">Bahasa / Kata</div>
      <div class="v" style="font-size:16px">{_esc(lang)} · {_esc(words)}</div></div>
  </div>

  {f'<div class="note" style="border-left:3px solid {BRAND}">{_esc(result.get("verdict_explanation"))}</div>' if result.get("verdict_explanation") else ""}

  {warn_html}

  {bd_html}

  {_ai_highlight_html(result)}

  <h2>Rincian Sinyal Deteksi</h2>
  {comp}

  <h2>Metrik Linguistik</h2>
  {sig_tbl}

  {flag_html}

  <div class="note">{_esc(result.get("note") or "Skor adalah estimasi statistik pola teks, bukan bukti kepengarangan. Gunakan sebagai sinyal awal yang ditinjau bersama konteks.")}</div>
"""
    subtitle = meta.get("title") or "Laporan Deteksi Teks AI"
    return _shell("Laporan AI Detector", str(subtitle), body)


def _sev_tone(sev: str) -> str:
    return "background:#fee2e2;color:#b91c1c;" if sev == "critical" else "background:#e0e7ff;color:#4338ca;"


def grammar_report_html(result: dict, meta: dict | None = None) -> str:
    meta = meta or {}
    score = result.get("score")
    summary = result.get("issue_summary") or {}
    metrics = result.get("metrics") or {}
    issues = result.get("issues") or []

    rows = []
    for it in issues[:60]:
        sev = str(it.get("severity") or "advanced")
        rows.append(
            "<tr>"
            f"<td><span class='pill' style='{_sev_tone(sev)}'>{_esc(sev)}</span></td>"
            f"<td>{_esc(it.get('category') or '-')}</td>"
            f"<td><span class='muted' style='text-decoration:line-through'>{_esc(it.get('original') or '')}</span><br>"
            f"<b>{_esc(it.get('suggestion') or '')}</b></td>"
            f"<td class='muted'>{_esc(it.get('explanation') or '')}</td>"
            "</tr>"
        )
    issues_tbl = (
        "<table><tr><th>Tingkat</th><th>Kategori</th><th>Perbaikan</th><th>Alasan</th></tr>"
        + "".join(rows)
        + "</table>"
        if rows
        else "<div class='muted'>Tidak ada masalah yang terdeteksi. Teks sudah rapi.</div>"
    )

    corrected = str(result.get("corrected") or "").strip()
    corrected_html = ""
    if corrected:
        corrected_html = (
            "<h2>Teks Hasil Perbaikan</h2>"
            f"<div style='white-space:pre-wrap;border:1px solid {_LINE};"
            "border-radius:8px;padding:12px'>"
            f"{_esc(corrected[:8000])}</div>"
        )

    body = f"""
  <div class="cards">
    <div class="card"><div class="k">Skor Bahasa</div>
      <div class="v" style="color:{BRAND}">{_esc(score if score is not None else '—')}</div></div>
    <div class="card"><div class="k">Total Masalah</div>
      <div class="v">{_esc(summary.get('total', len(issues)))}</div></div>
    <div class="card"><div class="k">Kritis / Lanjutan</div>
      <div class="v" style="font-size:16px">{_esc(summary.get('critical', 0))} / {_esc(summary.get('advanced', 0))}</div></div>
    <div class="card"><div class="k">Jumlah Kata</div>
      <div class="v">{_esc(metrics.get('words', '—'))}</div></div>
  </div>

  <h2>Daftar Masalah</h2>
  {issues_tbl}

  {corrected_html}

  <div class="note">Saran bersifat bantuan editorial otomatis. Tinjau setiap perubahan
    agar makna dan gaya tetap sesuai maksud penulis.</div>
"""
    subtitle = meta.get("title") or "Laporan Pemeriksaan Tata Bahasa"
    return _shell("Laporan Grammar Checker", str(subtitle), body)
