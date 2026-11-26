"""Uji pagar anti-abuse (rate limit + potong token) di tools._access_guard.

Semua default OFF; uji perilaku saat admin mengaktifkannya, dengan
memonkeypatch helper admin_svc agar tidak menyentuh DB.
"""

from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.api import tools


class _FakeClient:
    host = "203.0.113.9"


class _FakeRequest:
    def __init__(self, headers=None):
        self.headers = headers or {}
        self.client = _FakeClient()
        self.state = SimpleNamespace()


def _reset_hits():
    tools._RL_HITS.clear()


def test_client_identity_prefers_user_id():
    req = _FakeRequest()
    assert tools._client_identity(req, {"id": 7}) == "u:7"


def test_client_identity_uses_forwarded_ip_for_anon():
    req = _FakeRequest(headers={"x-forwarded-for": "198.51.100.4, 10.0.0.1"})
    assert tools._client_identity(req, None) == "ip:198.51.100.4"


def test_rate_limit_disabled_is_noop(monkeypatch):
    _reset_hits()
    monkeypatch.setattr(tools.admin_svc, "rate_limit_enabled", lambda: False)
    req = _FakeRequest()
    for _ in range(100):
        tools._enforce_rate_limit(req, {"id": 1})  # tidak melempar


def test_rate_limit_blocks_after_threshold(monkeypatch):
    _reset_hits()
    monkeypatch.setattr(tools.admin_svc, "rate_limit_enabled", lambda: True)
    monkeypatch.setattr(tools.admin_svc, "rate_limit_per_min", lambda: 3)
    req = _FakeRequest()
    user = {"id": 42}
    for _ in range(3):
        tools._enforce_rate_limit(req, user)
    with pytest.raises(HTTPException) as exc:
        tools._enforce_rate_limit(req, user)
    assert exc.value.status_code == 429


def test_rate_limit_isolated_per_identity(monkeypatch):
    _reset_hits()
    monkeypatch.setattr(tools.admin_svc, "rate_limit_enabled", lambda: True)
    monkeypatch.setattr(tools.admin_svc, "rate_limit_per_min", lambda: 1)
    req = _FakeRequest()
    tools._enforce_rate_limit(req, {"id": 1})
    # Identitas lain tidak terpengaruh oleh kuota identitas pertama.
    tools._enforce_rate_limit(req, {"id": 2})
    with pytest.raises(HTTPException):
        tools._enforce_rate_limit(req, {"id": 1})


def test_token_cost_disabled_is_noop(monkeypatch):
    monkeypatch.setattr(tools.admin_svc, "token_enforcement_enabled", lambda: False)
    tools._enforce_token_cost(_FakeRequest(), {"id": 1}, "ai-detector")


def test_token_cost_anonymous_skipped(monkeypatch):
    monkeypatch.setattr(tools.admin_svc, "token_enforcement_enabled", lambda: True)
    # Tanpa user → tidak melempar (dijaga rate-limit, bukan token).
    tools._enforce_token_cost(_FakeRequest(), None, "ai-detector")


def test_token_cost_rejects_when_insufficient(monkeypatch):
    monkeypatch.setattr(tools.admin_svc, "token_enforcement_enabled", lambda: True)
    monkeypatch.setattr(tools.billing_svc, "subscription_active", lambda uid: False)
    monkeypatch.setattr(tools.admin_svc, "tool_cost", lambda slug: 5)
    monkeypatch.setattr(tools.admin_svc, "charge_tokens", lambda uid, amt: False)
    with pytest.raises(HTTPException) as exc:
        tools._enforce_token_cost(_FakeRequest(), {"id": 3}, "ai-detector")
    assert exc.value.status_code == 402


def test_token_cost_passes_when_charged(monkeypatch):
    monkeypatch.setattr(tools.admin_svc, "token_enforcement_enabled", lambda: True)
    monkeypatch.setattr(tools.billing_svc, "subscription_active", lambda uid: False)
    monkeypatch.setattr(tools.admin_svc, "tool_cost", lambda slug: 2)
    charged = {}
    monkeypatch.setattr(
        tools.admin_svc,
        "charge_tokens",
        lambda uid, amt: charged.update(uid=uid, amt=amt) or True,
    )
    tools._enforce_token_cost(_FakeRequest(), {"id": 9}, "ai-detector")
    assert charged == {"uid": 9, "amt": 2}
