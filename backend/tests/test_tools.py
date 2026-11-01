from fastapi.testclient import TestClient

from app.main import app
from app.services.text_tools import analyze_text

client = TestClient(app)


def test_analyze_text_counts():
    result = analyze_text("Halo dunia. Ini uji coba!")
    assert result["words"] == 5
    assert result["sentences"] == 2
    assert result["characters"] > 0


def test_analyze_empty():
    result = analyze_text("")
    assert result["words"] == 0
    assert result["sentences"] == 0
    assert result["reading_time_seconds"] == 0


def test_word_count_endpoint():
    r = client.post("/tools/word-count", json={"text": "satu dua tiga"})
    assert r.status_code == 200
    assert r.json()["words"] == 3


def test_word_count_rejects_empty():
    r = client.post("/tools/word-count", json={"text": ""})
    assert r.status_code == 422
