"""Bot Telegram: galat layanan dijawab dengan pesan yang jelas, bukan trace teknis."""

import httpx
import pytest

from app.bot import telegram_bot as bot


@pytest.fixture
def sent(monkeypatch):
    out: list[str] = []
    monkeypatch.setattr(bot, "_send", lambda chat, text: out.append(text))
    return out


def _status_error(code):
    req = httpx.Request("POST", "http://x")
    return httpx.HTTPStatusError("x", request=req, response=httpx.Response(code, request=req))


@pytest.mark.parametrize(("code", "needle"), [
    (402, "Saldo token"), (401, "tidak diizinkan"), (403, "tidak diizinkan"),
    (413, "terlalu panjang"), (429, "Terlalu banyak"), (503, "pemeliharaan"), (500, "500"),
])
def test_http_errors_get_friendly_message(monkeypatch, sent, code, needle):
    def boom(path, body):
        raise _status_error(code)

    monkeypatch.setattr(bot, "_post", boom)
    bot._handle(1, "/cek teks uji")
    assert needle.lower() in sent[-1].lower()
    assert "Traceback" not in sent[-1]


def test_timeout_gets_clear_message(monkeypatch, sent):
    def slow(path, body):
        raise httpx.ReadTimeout("t")

    monkeypatch.setattr(bot, "_post", slow)
    bot._handle(1, "/cek teks uji")
    assert "melebihi batas waktu" in sent[-1]


def test_internal_token_header_is_sent(monkeypatch):
    seen = {}

    class R:
        status_code = 200

        def raise_for_status(self):
            pass

        def json(self):
            return {"ok": True}

    def fake_post(url, json=None, headers=None, timeout=None):
        seen.update(headers or {})
        return R()

    monkeypatch.setattr(bot.httpx, "post", fake_post)
    bot._post("/tools/word-count", {"text": "a"})
    assert "x-internal-token" in seen and len(seen["x-internal-token"]) == 64


def test_cek_runs_in_background_and_other_commands_stay_responsive(monkeypatch, sent):
    import threading

    gate = threading.Event()
    done = threading.Event()

    def slow_post(path, body):
        if path != "/tools/plagiarism":
            return {"words": 3, "characters": 14, "sentences": 1}
        gate.wait(5)
        return {"similarity_index": 12.0, "sources": []}

    monkeypatch.setattr(bot, "_post", slow_post)
    monkeypatch.setattr(bot, "_fmt_plagiarism", lambda d: "HASIL-CEK")

    def record(chat, text):
        sent.append(text)
        if text == "HASIL-CEK":
            done.set()

    monkeypatch.setattr(bot, "_send", record)

    bot._handle(1, "/cek teks panjang", background=True)
    assert any("Memeriksa" in m for m in sent)  # ack segera, handler tidak memblokir
    bot._handle(1, "/hitung satu dua tiga", background=True)  # tetap dijawab saat /cek berjalan
    assert any("kata" in m for m in sent)
    assert "HASIL-CEK" not in sent
    gate.set()
    assert done.wait(5) and "HASIL-CEK" in sent


def test_plagiarism_path_gets_long_timeout_others_default(monkeypatch):
    seen = {}

    def fake_post(url, json=None, headers=None, timeout=None):
        seen[url] = timeout
        return type("R", (), {"raise_for_status": lambda s: None, "json": lambda s: {}})()

    monkeypatch.setattr(bot.httpx, "post", fake_post)
    monkeypatch.setattr(bot, "_internal_headers", lambda: {})
    bot._post("/tools/plagiarism", {})
    bot._post("/tools/word-count", {})
    assert seen[f"{bot.API}/tools/plagiarism"] >= 900
    assert seen[f"{bot.API}/tools/word-count"] == 180
