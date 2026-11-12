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


def test_sentence_count_ignores_abbreviations():
    # Singkatan, desimal, inisial, dan sitasi tidak boleh dihitung akhir kalimat.
    assert analyze_text("Dr. Budi pergi ke kampus. Ia mengajar.")["sentences"] == 2
    assert analyze_text("Nilai rata-rata 3.14 dan 2.71 cukup tinggi.")["sentences"] == 1
    assert analyze_text("Metode ini dkk. digunakan oleh Smith et al. pada 2020.")["sentences"] == 1
    assert (
        analyze_text("Penelitian ini memakai data a.l. survei dll. secara daring.")["sentences"]
        == 1
    )
    assert analyze_text("Tunggu... apakah benar? Ya!")["sentences"] == 2
    assert analyze_text("A. B. Cahyono menulis buku. Buku itu terkenal.")["sentences"] == 2


def test_word_count_endpoint():
    r = client.post("/tools/word-count", json={"text": "satu dua tiga"})
    assert r.status_code == 200
    assert r.json()["words"] == 3


def test_word_count_rejects_empty():
    r = client.post("/tools/word-count", json={"text": ""})
    assert r.status_code == 422
