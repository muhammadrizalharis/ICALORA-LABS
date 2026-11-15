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

    body = f"""
  <div class="cards">
    <div class="card"><div class="k">Probabilitas AI</div>
      <div class="v" style="color:{BRAND}">{prob:.1f}%</div></div>
    <div class="card"><div class="k">Kesimpulan</div>
      <div style="margin-top:8px"><span class="pill" style="{_verdict_tone(prob)}">{_esc(verdict)}</span></div></div>
    <div class="card"><div class="k">Bahasa / Kata</div>
      <div class="v" style="font-size:16px">{_esc(lang)} · {_esc(words)}</div></div>
  </div>

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
