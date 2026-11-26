"""Kebijakan token: saldo awal 0 (admin yang memberi), demo & admin tanpa potongan."""

import pytest
from fastapi.testclient import TestClient

from app.api import tools
from app.main import app
from app.services import admin as admin_svc

client = TestClient(app)


@pytest.fixture
def ledger(monkeypatch):
    """Simulasi saldo token tanpa DB; kembalikan dict {user_id: saldo}."""
    balances = {1: 0, 2: 5, 3: 1_000_000, 4: 1_000_000}
    monkeypatch.setattr(admin_svc, "token_enforcement_enabled", lambda: True)
    monkeypatch.setattr(admin_svc, "tool_cost", lambda slug: 1)
    monkeypatch.setattr(admin_svc, "rate_limit_enabled", lambda: False)
    monkeypatch.setattr(admin_svc, "is_maintenance", lambda: False)
    monkeypatch.setattr(admin_svc, "feature_enabled", lambda slug: True)

    def charge(uid, amount):
        if balances[uid] < amount:
            return False
        balances[uid] -= amount
        return True

    def refund(uid, amount):
        balances[uid] += amount

    monkeypatch.setattr(admin_svc, "charge_tokens", charge)
    monkeypatch.setattr(admin_svc, "refund_tokens", refund)
    monkeypatch.setattr(tools.billing_svc, "subscription_active", lambda uid: False)
    return balances


def _as(monkeypatch, **user):
    base = {"id": 1, "is_active": True, "is_demo": False, "is_admin": False}
    monkeypatch.setattr(tools, "optional_user_from_request", lambda request: {**base, **user})


def _call():
    return client.post("/tools/word-count", json={"text": "satu dua tiga"})


def test_new_user_with_zero_tokens_is_rejected_with_402(monkeypatch, ledger):
    _as(monkeypatch, id=1)
    r = _call()
    assert r.status_code == 402
    assert "isi saldo" in r.json()["detail"].lower()
    assert ledger[1] == 0


def test_user_with_balance_is_charged(monkeypatch, ledger):
    _as(monkeypatch, id=2)
    assert _call().status_code == 200
    assert ledger[2] == 4


def test_demo_account_is_never_charged(monkeypatch, ledger):
    _as(monkeypatch, id=3, is_demo=True)
    for _ in range(3):
        assert _call().status_code == 200
    assert ledger[3] == 1_000_000


def test_demo_with_zero_balance_still_works(monkeypatch, ledger):
    ledger[3] = 0
    _as(monkeypatch, id=3, is_demo=True)
    assert _call().status_code == 200


def test_admin_is_never_charged(monkeypatch, ledger):
    _as(monkeypatch, id=4, is_admin=True)
    assert _call().status_code == 200
    assert ledger[4] == 1_000_000


def test_default_grant_for_new_users_is_zero():
    assert admin_svc._DEFAULTS["default_token_grant"] == 0


def test_failed_request_is_refunded(monkeypatch, ledger):
    """Permintaan yang gagal (exception di endpoint) tidak boleh memakan saldo."""
    _as(monkeypatch, id=2)

    def boom(*_a, **_k):
        raise RuntimeError("model mati")

    monkeypatch.setattr(tools, "analyze_text", boom)
    no_raise = TestClient(app, raise_server_exceptions=False)
    r = no_raise.post("/tools/word-count", json={"text": "satu dua tiga"})
    assert r.status_code == 500
    assert ledger[2] == 5


def test_invalid_body_is_refunded(monkeypatch, ledger):
    _as(monkeypatch, id=2)
    r = client.post("/tools/word-count", json={"salah": 1})
    assert r.status_code == 422
    assert ledger[2] == 5


def test_http_error_from_endpoint_is_refunded(monkeypatch, ledger):
    _as(monkeypatch, id=2)
    r = client.post("/tools/grammar-check", json={"text": ""})
    assert r.status_code in (400, 422)
    assert ledger[2] == 5


def test_active_subscription_is_not_charged(monkeypatch, ledger):
    monkeypatch.setattr(tools.billing_svc, "subscription_active", lambda uid: True)
    _as(monkeypatch, id=1)
    assert _call().status_code == 200
    assert ledger[1] == 0
