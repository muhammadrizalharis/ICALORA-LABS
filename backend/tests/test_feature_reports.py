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
