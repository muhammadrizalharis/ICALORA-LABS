import json

import app.services.llm.tasks as tasks
from app.services.llm.tasks import _normalize_issue, _text_metrics, grammar_check


class _FakeLLM:
    def __init__(self, reply: str):
        self._reply = reply

    def chat(self, messages, temperature=0.0):
        return self._reply


def _patch_llm(monkeypatch, reply: str):
    monkeypatch.setattr(tasks, "get_llm", lambda: _FakeLLM(reply))


def test_text_metrics_basic():
    m = _text_metrics("Halo dunia. Ini uji coba!")
    assert m["words"] == 5
    assert m["sentences"] == 2
    assert m["characters"] > 0
    assert m["reading_time_min"] >= 0


def test_text_metrics_no_terminator_counts_one_sentence():
    assert _text_metrics("tanpa titik akhir")["sentences"] == 1
    assert _text_metrics("")["sentences"] == 0


def test_normalize_issue_defaults_and_clamps():
    out = _normalize_issue(
        {"original": "teks salah", "suggestion": "teks benar", "category": "ngaco", "severity": "x"}
    )
    assert out is not None
    assert out["category"] == "Ketepatan"
    assert out["severity"] == "advanced"
    assert _normalize_issue({"original": "", "suggestion": ""}) is None


def test_grammar_check_parses_issues_and_scores(monkeypatch):
    reply = json.dumps(
        {
            "corrected": "Saya pergi ke sekolah.",
            "issues": [
                {
                    "category": "Ketepatan",
                    "severity": "critical",
                    "original": "saya pergi ke sekola",
                    "suggestion": "Saya pergi ke sekolah.",
                    "explanation": "Ejaan dan huruf kapital.",
                }
            ],
        }
    )
    _patch_llm(monkeypatch, reply)
    res = grammar_check("saya pergi ke sekola")
    assert res["corrected"] == "Saya pergi ke sekolah."
    assert res["issue_summary"] == {"total": 1, "critical": 1, "advanced": 0}
    assert 0 <= res["score"] <= 100
    assert res["metrics"]["words"] == 4
    assert res["issues"][0]["severity"] == "critical"


def test_grammar_check_clean_text_scores_100(monkeypatch):
    _patch_llm(monkeypatch, json.dumps({"corrected": "Teks ini sudah rapi.", "issues": []}))
    res = grammar_check("Teks ini sudah rapi.")
    assert res["issue_summary"]["total"] == 0
    assert res["score"] == 100


def test_grammar_check_non_json_fallback(monkeypatch):
    _patch_llm(monkeypatch, "Teks hasil perbaikan tanpa format JSON.")
    res = grammar_check("teks asli")
    assert res["corrected"] == "Teks hasil perbaikan tanpa format JSON."
    assert res["issues"] == []
    assert res["score"] == 100
