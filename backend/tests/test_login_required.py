"""Semua layanan /tools wajib login (Google/email); bot memakai token internal."""

import pytest
from fastapi.testclient import TestClient

from app.api import tools
from app.main import app
from app.services import auth as auth_svc

client = TestClient(app)

# Endpoint yang dulu bisa dipakai tanpa login.
_ANON_CALLS = [
    ("post", "/tools/word-count", {"json": {"text": "satu dua"}}),
    ("post", "/tools/plagiarism", {"json": {"text": "teks uji"}}),
    ("post", "/tools/plagiarism-async", {"json": {"text": "teks uji"}}),
    (
        "post",
        "/tools/plagiarism-file-async",
        {"files": {"file": ("a.pdf", b"%PDF-1.4", "application/pdf")}},
    ),
    ("post", "/tools/paraphrase-async", {"json": {"text": "teks uji"}}),
    ("post", "/tools/grammar-check", {"json": {"text": "teks uji"}}),
    ("post", "/tools/extract-text", {"files": {"file": ("a.txt", b"x", "text/plain")}}),
    ("get", "/tools/job/abc", {}),
]


@pytest.mark.parametrize(("method", "path", "kw"), _ANON_CALLS)
def test_anonymous_requests_are_rejected_with_401(monkeypatch, method, path, kw):
    monkeypatch.setattr(tools, "optional_user_from_request", lambda request: None)
    r = getattr(client, method)(path, **kw)
    assert r.status_code == 401
    assert "masuk" in r.json()["detail"].lower()


def test_logged_in_user_is_allowed(monkeypatch):
    monkeypatch.setattr(
        tools, "optional_user_from_request",
        lambda request: {"id": 7, "is_admin": False, "is_active": True},
    )
    r = client.post("/tools/word-count", json={"text": "satu dua tiga"})
    assert r.status_code == 200


def test_internal_bot_token_is_allowed_without_login(monkeypatch):
    monkeypatch.setattr(tools, "optional_user_from_request", lambda request: None)
    r = client.post(
        "/tools/word-count",
        json={"text": "satu dua tiga"},
        headers={"x-internal-token": auth_svc.internal_service_token()},
    )
    assert r.status_code == 200


def test_wrong_or_empty_internal_token_is_rejected(monkeypatch):
    monkeypatch.setattr(tools, "optional_user_from_request", lambda request: None)
    for bad in ("", "salah", auth_svc.internal_service_token()[:-1] + "0"):
        r = client.post(
            "/tools/word-count", json={"text": "a b"}, headers={"x-internal-token": bad}
        )
        assert r.status_code == 401


def test_internal_token_depends_on_session_secret(monkeypatch):
    before = auth_svc.internal_service_token()
    monkeypatch.setattr(auth_svc.settings, "session_secret", "rahasia-lain")
    assert auth_svc.internal_service_token() != before


def test_session_cookie_signed_with_secret_is_required():
    # Cookie palsu (tanda tangan salah) tidak dianggap login.
    assert auth_svc.verify_session_token("eyJ1aWQiOiAxfQ==.deadbeef") is None
    assert auth_svc.verify_session_token(None) is None


def test_public_endpoints_stay_public():
    # /health dan /auth/me tidak boleh kena kewajiban login.
    assert client.get("/health").status_code == 200
    assert client.get("/auth/me").status_code == 200
