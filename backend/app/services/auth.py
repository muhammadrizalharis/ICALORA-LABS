"""Autentikasi & sesi pengguna.

- Sesi disimpan dalam cookie HTTP-only yang ditandatangani HMAC (stdlib, tanpa
  dependency tambahan).
- Login via Google OAuth (butuh GOOGLE_CLIENT_ID/SECRET) atau demo-login lokal
  (untuk pengembangan; semua fitur gratis, token tak terbatas).
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time

from sqlalchemy import text

from app.core.clients import engine
from app.core.config import get_settings

settings = get_settings()


def _sign(payload: dict) -> str:
    raw = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode()
    sig = hmac.new(settings.session_secret.encode(), raw.encode(), hashlib.sha256).hexdigest()
    return f"{raw}.{sig}"


def make_session_token(user_id: int) -> str:
    exp = int(time.time()) + settings.session_ttl_days * 86400
    return _sign({"uid": user_id, "exp": exp})


def verify_session_token(token: str | None) -> int | None:
    if not token or "." not in token:
        return None
    raw, sig = token.rsplit(".", 1)
    expected = hmac.new(settings.session_secret.encode(), raw.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(sig, expected):
        return None
    try:
        payload = json.loads(base64.urlsafe_b64decode(raw.encode()).decode())
    except Exception:  # noqa: BLE001
        return None
    if payload.get("exp", 0) < int(time.time()):
        return None
    return int(payload.get("uid"))


def _row_to_user(r) -> dict:
    return {
        "id": r.id,
        "email": r.email,
        "name": r.name,
        "picture": r.picture,
        "token_balance": r.token_balance,
        "is_demo": r.is_demo,
    }


def get_user(user_id: int) -> dict | None:
    with engine.connect() as c:
        r = c.execute(
            text(
                "SELECT id, email, name, picture, token_balance, is_demo "
                "FROM users WHERE id = :id"
            ),
            {"id": user_id},
        ).first()
    return _row_to_user(r) if r else None


def optional_user_from_request(request) -> dict | None:
    """Ambil user dari cookie sesi jika ada (tanpa memaksa login)."""
    token = request.cookies.get(settings.session_cookie)
    uid = verify_session_token(token)
    return get_user(uid) if uid else None


def upsert_google_user(sub: str, email: str, name: str, picture: str) -> dict:
    with engine.begin() as c:
        r = c.execute(
            text(
                """
                INSERT INTO users (google_sub, email, name, picture, last_login_at)
                VALUES (:sub, :email, :name, :picture, now())
                ON CONFLICT (google_sub) DO UPDATE
                   SET email = EXCLUDED.email, name = EXCLUDED.name,
                       picture = EXCLUDED.picture, last_login_at = now()
                RETURNING id, email, name, picture, token_balance, is_demo
                """
            ),
            {"sub": sub, "email": email, "name": name, "picture": picture},
        ).first()
    return _row_to_user(r)


def create_demo_user() -> dict:
    with engine.begin() as c:
        r = c.execute(
            text(
                """
                INSERT INTO users (email, name, picture, is_demo, last_login_at)
                VALUES (:email, :name, NULL, TRUE, now())
                RETURNING id, email, name, picture, token_balance, is_demo
                """
            ),
            {"email": "demo@icalora.local", "name": "Pengguna Demo"},
        ).first()
    return _row_to_user(r)


def record_history(
    user_id: int, tool: str, title: str, input_preview: str, result: dict
) -> None:
    with engine.begin() as c:
        c.execute(
            text(
                """
                INSERT INTO tool_history (user_id, tool, title, input_preview, result)
                VALUES (:uid, :tool, :title, :prev, CAST(:res AS jsonb))
                """
            ),
            {
                "uid": user_id,
                "tool": tool,
                "title": title[:200] if title else None,
                "prev": input_preview[:500] if input_preview else None,
                "res": json.dumps(result)[:200000],
            },
        )


def list_history(user_id: int, tool: str | None = None, limit: int = 50) -> list[dict]:
    q = (
        "SELECT id, tool, title, input_preview, created_at FROM tool_history "
        "WHERE user_id = :uid"
    )
    params: dict = {"uid": user_id, "limit": limit}
    if tool:
        q += " AND tool = :tool"
        params["tool"] = tool
    q += " ORDER BY created_at DESC LIMIT :limit"
    with engine.connect() as c:
        rows = c.execute(text(q), params).all()
    return [
        {
            "id": r.id,
            "tool": r.tool,
            "title": r.title,
            "input_preview": r.input_preview,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]


def get_history_item(user_id: int, item_id: int) -> dict | None:
    with engine.connect() as c:
        r = c.execute(
            text(
                "SELECT id, tool, title, input_preview, result, created_at "
                "FROM tool_history WHERE user_id = :uid AND id = :id"
            ),
            {"uid": user_id, "id": item_id},
        ).first()
    if not r:
        return None
    return {
        "id": r.id,
        "tool": r.tool,
        "title": r.title,
        "input_preview": r.input_preview,
        "result": r.result,
        "created_at": r.created_at.isoformat() if r.created_at else None,
    }


def delete_history_item(user_id: int, item_id: int) -> bool:
    with engine.begin() as c:
        res = c.execute(
            text("DELETE FROM tool_history WHERE user_id = :uid AND id = :id"),
            {"uid": user_id, "id": item_id},
        )
    return res.rowcount > 0
