"""Uji builder HTML laporan PDF (AI detector & grammar) + render ke PDF."""

from app.services.report import render_pdf
from app.services.report.reports import (
    ai_detector_report_html,
    grammar_report_html,
)


def test_ai_report_html_contains_core_fields():
    result = {
        "ai_probability": 91.2,
        "verdict": "kemungkinan besar AI",
        "language": "id",
        "stat_probability": 35.4,
        "model_probability": 86.9,
        "emb_model_probability": 90.9,
        "signals": {"burstiness": 0.23, "word_count": 112},
        "flagged_sentences": ["Kalimat uji ditandai."],
    }
    html = ai_detector_report_html(result, {"title": "Tes"})
    assert "91.2%" in html
    assert "kemungkinan besar AI" in html
    assert "Kalimat uji ditandai." in html
    assert "ICALORA" in html


def test_ai_report_escapes_html():
    result = {"ai_probability": 10, "verdict": "<script>x</script>", "signals": {}}
    html = ai_detector_report_html(result)
    assert "<script>x</script>" not in html
    assert "&lt;script&gt;" in html


def test_ai_report_highlights_full_text_with_segments():
    result = {
        "ai_probability": 70,
        "verdict": "campuran",
        "signals": {},
        "input_text": "Kalimat manusia biasa. Kalimat buatan AI jelas sekali.",
        "segments": [
            {"index": 0, "label": "human", "start": 0, "end": 22,
             "words": 3, "ai_probability": 8.0, "preview": "Kalimat manusia"},
            {"index": 1, "label": "ai", "start": 22, "end": 54,
             "words": 5, "ai_probability": 92.0, "preview": "Kalimat buatan AI"},
        ],
    }
    html = ai_detector_report_html(result, {"title": "Tes"})
    assert "Teks Dianalisis" in html
    assert "Rincian Segmen Dokumen" in html
    assert "class='doc'" in html
    assert "Sorotan:" in html
    assert "#fee2e2" in html  # sorotan AI (merah)
    assert "#ecfdf5" in html  # sorotan manusia (hijau)


def test_ai_report_segment_table_without_full_text():
    """Riwayat lama tanpa input_text tetap menampilkan tabel segmen + petunjuk."""
    result = {
        "ai_probability": 40,
        "verdict": "campuran",
        "signals": {},
        "segments": [
            {"index": 0, "label": "mixed", "words": 50, "ai_probability": 65.0,
             "preview": "Cuplikan segmen uji"},
        ],
    }
    html = ai_detector_report_html(result)
    assert "Rincian Segmen Dokumen" in html
    assert "Cuplikan segmen uji" in html
    assert "class='doc'" not in html
    assert "riwayat lama tidak tersimpan" in html


def test_grammar_report_lists_issues():
    result = {
        "score": 78,
        "corrected": "Teks perbaikan.",
        "metrics": {"words": 120},
        "issue_summary": {"total": 2, "critical": 1, "advanced": 1},
        "issues": [
            {
                "severity": "critical",
                "category": "Ketepatan",
                "original": "salh",
                "suggestion": "salah",
                "explanation": "ejaan",
            },
        ],
    }
    html = grammar_report_html(result, {"title": "Tes"})
    assert "78" in html
    assert "salah" in html
    assert "Ketepatan" in html


def test_reports_render_to_pdf_bytes():
    ai_pdf = render_pdf(ai_detector_report_html({"ai_probability": 50, "signals": {}}))
    gr_pdf = render_pdf(grammar_report_html({"score": 100, "issues": []}))
    assert ai_pdf[:4] == b"%PDF"
    assert gr_pdf[:4] == b"%PDF"
