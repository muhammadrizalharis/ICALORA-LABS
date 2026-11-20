"""Peran: Super Admin (tunggal) vs admin biasa (is_staff) vs pengguna biasa."""

import pytest
from fastapi.testclient import TestClient

from app.api import auth as auth_api
from app.main import app
from app.services import admin as admin_svc

client = TestClient(app)

SUPER = {"id": 1, "email": "admin@icalora-labs.local", "is_admin": True, "is_staff": False,
         "is_active": True, "is_demo": False, "role": "super"}
STAFF = {"id": 2, "email": "staf@x.id", "is_admin": False, "is_staff": True,
         "is_active": True, "is_demo": False, "role": "admin"}
USER = {"id": 3, "email": "mhs@x.id", "is_admin": False, "is_staff": False,
        "is_active": True, "is_demo": False, "role": "user"}


def _row(u, balance=0):
    return {**u, "token_balance": balance, "name": "N"}


@pytest.fixture
def world(monkeypatch):
    """Dunia kecil di memori: pengguna, saldo, dan log audit."""
    db = {u["id"]: _row(u) for u in (SUPER, STAFF, USER)}
    db[4] = _row({**USER, "id": 4, "email": "demo@x", "is_demo": True, "role": "demo"})
    db[5] = _row({**STAFF, "id": 5, "email": "staf2@x.id"})
    audit: list = []
    monkeypatch.setattr(admin_svc, "get_admin_user", lambda i: db.get(i))

    def add(uid, n):
        db[uid]["token_balance"] += n
        return db[uid]["token_balance"]

    def update(uid, fields):
        db[uid].update(fields)
        return db[uid]

    monkeypatch.setattr(admin_svc, "add_tokens", add)
    monkeypatch.setattr(admin_svc, "update_user", update)
    monkeypatch.setattr(
        admin_svc, "record_audit", lambda a, act, t=None, d=None: audit.append((a["email"], act, d))
    )
    monkeypatch.setattr(admin_svc, "list_users", lambda q, lim: list(db.values()))
    monkeypatch.setattr(admin_svc, "count_users", lambda: {"total": 5, "admins": 3, "inactive": 0})
    monkeypatch.setattr(admin_svc, "list_audit", lambda lim: [{"action": "x"}])
    return db, audit


def _login(monkeypatch, user):
    monkeypatch.setattr(auth_api, "current_user", lambda request: user)


def test_staff_can_list_users_but_user_cannot(monkeypatch, world):
    _login(monkeypatch, STAFF)
    assert client.get("/auth/admin/users").status_code == 200
    _login(monkeypatch, USER)
    assert client.get("/auth/admin/users").status_code == 403


def test_staff_can_add_tokens_to_regular_user_and_it_is_audited(monkeypatch, world):
    db, audit = world
    _login(monkeypatch, STAFF)
    r = client.post("/auth/admin/users/3/tokens", json={"add": 500})
    assert r.status_code == 200 and r.json()["token_balance"] == 500
    assert audit and audit[0][:2] == ("staf@x.id", "tokens.add")


def test_staff_cannot_exceed_grant_cap(monkeypatch, world):
    _login(monkeypatch, STAFF)
    cap = auth_api.settings.staff_max_token_grant
    assert client.post("/auth/admin/users/3/tokens", json={"add": cap + 1}).status_code == 403
    assert client.post("/auth/admin/users/3/tokens", json={"add": cap}).status_code == 200


def test_staff_cannot_set_balance_or_touch_admins_or_self(monkeypatch, world):
    _login(monkeypatch, STAFF)
    assert client.post("/auth/admin/users/3/tokens", json={"set": 5}).status_code == 403
    url = "/auth/admin/users/{}/tokens"
    assert client.post(url.format(1), json={"add": 5}).status_code == 403  # Super Admin
    assert client.post(url.format(5), json={"add": 5}).status_code == 403  # admin lain
    assert client.post(url.format(2), json={"add": 5}).status_code == 403  # diri sendiri


def test_staff_cannot_use_super_admin_endpoints(monkeypatch, world):
    _login(monkeypatch, STAFF)
    assert client.patch("/auth/admin/users/3", json={"token_balance": 99}).status_code == 403
    assert client.patch("/auth/admin/users/3", json={"is_staff": True}).status_code == 403
    assert client.delete("/auth/admin/users/3").status_code == 403
    assert client.post("/auth/admin/users/3/reset-password").status_code == 403
    assert client.get("/auth/admin/users/3/history").status_code == 403
    assert client.get("/auth/admin/settings").status_code == 403
    assert client.put("/auth/admin/settings", json={"maintenance_mode": True}).status_code == 403
    assert client.get("/auth/admin/audit").status_code == 403
    assert client.get("/auth/admin/activity").status_code == 403
    assert client.get("/auth/admin/analytics").status_code == 403


def test_regular_user_cannot_give_tokens(monkeypatch, world):
    _login(monkeypatch, USER)
    assert client.post("/auth/admin/users/3/tokens", json={"add": 5}).status_code == 403


def test_inactive_staff_loses_access(monkeypatch, world):
    _login(monkeypatch, {**STAFF, "is_active": False})
    assert client.get("/auth/admin/users").status_code == 403


def test_super_admin_can_add_set_and_has_no_cap(monkeypatch, world):
    db, audit = world
    _login(monkeypatch, SUPER)
    big = auth_api.settings.staff_max_token_grant * 10
    assert client.post("/auth/admin/users/3/tokens", json={"add": big}).status_code == 200
    r = client.post("/auth/admin/users/3/tokens", json={"set": 7})
    assert r.status_code == 200 and db[3]["token_balance"] == 7
    assert [a[1] for a in audit] == ["tokens.add", "tokens.set"]


def test_token_body_validation(monkeypatch, world):
    _login(monkeypatch, SUPER)
    assert client.post("/auth/admin/users/3/tokens", json={}).status_code == 400
    assert client.post("/auth/admin/users/3/tokens", json={"add": 1, "set": 1}).status_code == 400
    assert client.post("/auth/admin/users/3/tokens", json={"add": 0}).status_code == 422
    assert client.post("/auth/admin/users/3/tokens", json={"add": -5}).status_code == 422
    assert client.post("/auth/admin/users/99/tokens", json={"add": 5}).status_code == 404


def test_demo_account_tokens_rejected(monkeypatch, world):
    _login(monkeypatch, SUPER)
    assert client.post("/auth/admin/users/4/tokens", json={"add": 5}).status_code == 400


def test_only_super_admin_assigns_admin_role_and_it_is_audited(monkeypatch, world):
    db, audit = world
    _login(monkeypatch, SUPER)
    r = client.patch("/auth/admin/users/3", json={"is_staff": True})
    assert r.status_code == 200 and db[3]["is_staff"] is True
    assert ("admin@icalora-labs.local", "user.role", {"from": False, "to": True}) in audit
    # tidak berlaku untuk Super Admin / akun demo
    assert client.patch("/auth/admin/users/1", json={"is_staff": True}).status_code == 400
    assert client.patch("/auth/admin/users/4", json={"is_staff": True}).status_code == 400


def test_super_admin_flag_cannot_be_granted_through_api(monkeypatch, world):
    _login(monkeypatch, SUPER)
    r = client.patch("/auth/admin/users/3", json={"is_admin": True})
    assert r.status_code in (200, 422)
    assert world[0][3].get("is_admin") is False  # field diabaikan; tak pernah jadi Super Admin


def test_super_admin_can_read_audit(monkeypatch, world):
    _login(monkeypatch, SUPER)
    assert client.get("/auth/admin/audit").json()["items"] == [{"action": "x"}]


def test_roles_computed():
    from app.services.auth import user_role

    class R:  # noqa: D106
        def __init__(self, **k):
            self.is_admin = k.get("is_admin", False)
            self.is_staff = k.get("is_staff", False)
            self.is_demo = k.get("is_demo", False)

    assert user_role(R(is_admin=True, is_staff=True)) == "super"
    assert user_role(R(is_staff=True)) == "admin"
    assert user_role(R(is_demo=True)) == "demo"
    assert user_role(R()) == "user"
