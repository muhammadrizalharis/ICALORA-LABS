"""Layanan Super Admin: pengaturan aplikasi global + manajemen pengguna.

Pengaturan disimpan di tabel ``app_settings`` (key-value JSON) sehingga Super
Admin bisa mengubahnya dari UI tanpa redeploy. Mencakup:

- ``maintenance_mode``   : bila ON, seluruh fitur ditutup untuk non-admin.
- ``registration_open``  : bila OFF, pengguna Google baru ditolak (yang lama tetap bisa).
- ``default_token_grant``: saldo token awal untuk pengguna baru.
- ``feature_flags``      : peta ``slug -> bool``; fitur yang OFF diblokir.

Semua fungsi idempoten terhadap skema (membuat tabel/kolom bila belum ada).
"""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy import text

from app.core.clients import engine
from app.services import auth as auth_svc

# Daftar slug fitur yang bisa di-toggle. Sumber kebenaran untuk flag fitur.
# Dipetakan dari endpoint /tools/* (lihat app/api/tools.py::_FEATURE_BY_PATH).
FEATURE_SLUGS: list[str] = [
    "word-count",
    "extract-text",
    "grammar-checker",
    "paraphraser",
    "humanizer",
    "ai-rewriter",
    "plagiarism-checker",
    "ai-chat",
    "ai-grader",
    "reader-reactions",
    "resume-builder",
    "citation-finder",
    "ai-detector",
    "authorship",
    "toc-generator",
    "document-improver",
    "hidden-text",
    "doc-chat",
    "publikasi",
    "transcribe",
    "report-pdf",
]

_DEFAULTS: dict[str, Any] = {
    "maintenance_mode": False,
    "registration_open": True,
    "default_token_grant": 0,
    "feature_flags": {},  # slug -> bool; absen = aktif
}

_schema_ready = False


def ensure_settings_schema() -> None:
    """Buat tabel app_settings + kolom users.is_active (idempoten)."""
    global _schema_ready
    if _schema_ready:
        return
    auth_svc.ensure_user_schema()
    with engine.begin() as c:
        c.execute(
            text(
                "CREATE TABLE IF NOT EXISTS app_settings ("
                "key text PRIMARY KEY, "
                "value jsonb NOT NULL, "
                "updated_at timestamptz NOT NULL DEFAULT now())"
            )
        )
        c.execute(
            text(
                "ALTER TABLE users ADD COLUMN IF NOT EXISTS "
                "is_active boolean NOT NULL DEFAULT TRUE"
            )
        )
    _schema_ready = True


def get_setting(key: str, default: Any = None) -> Any:
    ensure_settings_schema()
    with engine.connect() as c:
        r = c.execute(
            text("SELECT value FROM app_settings WHERE key = :k"), {"k": key}
        ).first()
    if r is None:
        return _DEFAULTS.get(key, default)
    val = r[0]
    # psycopg mengembalikan jsonb sebagai objek Python; antisipasi string.
    if isinstance(val, str):
        try:
            val = json.loads(val)
        except Exception:  # noqa: BLE001
            pass
    return val


def set_setting(key: str, value: Any) -> None:
    ensure_settings_schema()
    with engine.begin() as c:
        c.execute(
            text(
                "INSERT INTO app_settings (key, value, updated_at) "
                "VALUES (:k, CAST(:v AS jsonb), now()) "
                "ON CONFLICT (key) DO UPDATE "
                "SET value = EXCLUDED.value, updated_at = now()"
            ),
            {"k": key, "v": json.dumps(value)},
        )


def get_all_settings() -> dict[str, Any]:
    """Seluruh pengaturan (default + override DB) untuk panel admin."""
    ensure_settings_schema()
    out = dict(_DEFAULTS)
    with engine.connect() as c:
        rows = c.execute(text("SELECT key, value FROM app_settings")).fetchall()
    for key, val in rows:
        if isinstance(val, str):
            try:
                val = json.loads(val)
            except Exception:  # noqa: BLE001
                pass
        out[key] = val
    out["feature_slugs"] = FEATURE_SLUGS
    return out


def update_settings(patch: dict[str, Any]) -> dict[str, Any]:
    """Perbarui sebagian pengaturan; hanya kunci yang dikenal diterima."""
    allowed = set(_DEFAULTS.keys())
    for key, value in patch.items():
        if key not in allowed:
            continue
        if key == "maintenance_mode" or key == "registration_open":
            value = bool(value)
        elif key == "default_token_grant":
            value = max(0, int(value))
        elif key == "feature_flags":
            if not isinstance(value, dict):
                continue
            value = {str(k): bool(v) for k, v in value.items()}
        set_setting(key, value)
    return get_all_settings()


# ---- helper enforcement (dipakai endpoint fitur) ----

def is_maintenance() -> bool:
    return bool(get_setting("maintenance_mode", False))


def is_registration_open() -> bool:
    return bool(get_setting("registration_open", True))


def default_token_grant() -> int:
    try:
        return max(0, int(get_setting("default_token_grant", 0)))
    except Exception:  # noqa: BLE001
        return 0


def feature_enabled(slug: str) -> bool:
    """True bila fitur aktif (default aktif kecuali di-set False)."""
    flags = get_setting("feature_flags", {}) or {}
    if isinstance(flags, dict):
        return bool(flags.get(slug, True))
    return True


# ---- manajemen pengguna ----

_USER_COLS = (
    "id, email, name, picture, token_balance, is_demo, is_admin, "
    "COALESCE(is_active, TRUE) AS is_active, created_at, last_login_at"
)


def _row_to_admin_user(r) -> dict:
    return {
        "id": r.id,
        "email": r.email,
        "name": r.name,
        "picture": r.picture,
        "token_balance": r.token_balance,
        "is_demo": bool(r.is_demo),
        "is_admin": bool(r.is_admin),
        "is_active": bool(getattr(r, "is_active", True)),
        "created_at": r.created_at.isoformat() if r.created_at else None,
        "last_login_at": r.last_login_at.isoformat() if r.last_login_at else None,
    }


def list_users(query: str | None = None, limit: int = 200) -> list[dict]:
    ensure_settings_schema()
    sql = f"SELECT {_USER_COLS} FROM users"
    params: dict[str, Any] = {"lim": min(max(limit, 1), 500)}
    if query:
        sql += " WHERE email ILIKE :q OR name ILIKE :q"
        params["q"] = f"%{query}%"
    sql += " ORDER BY created_at DESC NULLS LAST, id DESC LIMIT :lim"
    with engine.connect() as c:
        rows = c.execute(text(sql), params).fetchall()
    return [_row_to_admin_user(r) for r in rows]


def get_admin_user(user_id: int) -> dict | None:
    ensure_settings_schema()
    with engine.connect() as c:
        r = c.execute(
            text(f"SELECT {_USER_COLS} FROM users WHERE id = :id"), {"id": user_id}
        ).first()
    return _row_to_admin_user(r) if r else None


def update_user(user_id: int, fields: dict[str, Any]) -> dict | None:
    """Perbarui token_balance / is_admin / is_active / name untuk satu user."""
    ensure_settings_schema()
    sets: list[str] = []
    params: dict[str, Any] = {"id": user_id}
    if "token_balance" in fields and fields["token_balance"] is not None:
        sets.append("token_balance = :tb")
        params["tb"] = max(0, int(fields["token_balance"]))
    if "is_admin" in fields and fields["is_admin"] is not None:
        sets.append("is_admin = :ia")
        params["ia"] = bool(fields["is_admin"])
    if "is_active" in fields and fields["is_active"] is not None:
        sets.append("is_active = :ac")
        params["ac"] = bool(fields["is_active"])
    if "name" in fields and fields["name"] is not None:
        sets.append("name = :nm")
        params["nm"] = str(fields["name"])[:200]
    if not sets:
        return get_admin_user(user_id)
    with engine.begin() as c:
        c.execute(
            text(f"UPDATE users SET {', '.join(sets)} WHERE id = :id"), params
        )
    return get_admin_user(user_id)


def delete_user(user_id: int) -> bool:
    """Hapus user beserta riwayat & berkasnya."""
    ensure_settings_schema()
    with engine.begin() as c:
        c.execute(text("DELETE FROM tool_file WHERE user_id = :id"), {"id": user_id})
        c.execute(text("DELETE FROM tool_history WHERE user_id = :id"), {"id": user_id})
        res = c.execute(text("DELETE FROM users WHERE id = :id"), {"id": user_id})
    return bool(res.rowcount)


def count_users() -> dict[str, int]:
    ensure_settings_schema()
    with engine.connect() as c:
        total = c.execute(text("SELECT count(*) FROM users")).scalar() or 0
        admins = c.execute(
            text("SELECT count(*) FROM users WHERE is_admin")
        ).scalar() or 0
        inactive = c.execute(
            text("SELECT count(*) FROM users WHERE NOT COALESCE(is_active, TRUE)")
        ).scalar() or 0
    return {"total": int(total), "admins": int(admins), "inactive": int(inactive)}
