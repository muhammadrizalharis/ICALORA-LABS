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
    # --- Proteksi penyalahgunaan (default OFF agar tidak memutus situs) ---
    "rate_limit_enabled": False,
    "rate_limit_per_min": 20,  # maks permintaan tool / menit / identitas
    "token_enforcement": False,  # bila ON, saldo token dipotong tiap pemakaian
    "default_tool_cost": 1,  # biaya token default per analisis
    "tool_costs": {},  # slug -> int; absen = default_tool_cost
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
        elif key in ("rate_limit_enabled", "token_enforcement"):
            value = bool(value)
        elif key == "rate_limit_per_min":
            value = max(1, min(10_000, int(value)))
        elif key == "default_tool_cost":
            value = max(0, int(value))
        elif key == "tool_costs":
            if not isinstance(value, dict):
                continue
            clean: dict[str, int] = {}
            for k, v in value.items():
                try:
                    clean[str(k)] = max(0, int(v))
                except (TypeError, ValueError):
                    continue
            value = clean
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


def rate_limit_enabled() -> bool:
    return bool(get_setting("rate_limit_enabled", False))


def rate_limit_per_min() -> int:
    try:
        return max(1, int(get_setting("rate_limit_per_min", 20)))
    except Exception:  # noqa: BLE001
        return 20


def token_enforcement_enabled() -> bool:
    return bool(get_setting("token_enforcement", False))


def tool_cost(slug: str) -> int:
    """Biaya token untuk suatu fitur (override per-slug, jika ada)."""
    costs = get_setting("tool_costs", {}) or {}
    if isinstance(costs, dict) and slug in costs:
        try:
            return max(0, int(costs[slug]))
        except (TypeError, ValueError):
            pass
    try:
        return max(0, int(get_setting("default_tool_cost", 1)))
    except Exception:  # noqa: BLE001
        return 1


def charge_tokens(user_id: int, amount: int) -> bool:
    """Potong `amount` token secara atomik. True bila berhasil.

    False bila saldo tidak cukup (tanpa mengubah saldo). Tidak memotong
    jika amount <= 0.
    """
    if amount <= 0:
        return True
    ensure_settings_schema()
    with engine.begin() as c:
        row = c.execute(
            text(
                "UPDATE users SET token_balance = token_balance - :amt "
                "WHERE id = :uid AND token_balance >= :amt "
                "RETURNING token_balance"
            ),
            {"amt": amount, "uid": user_id},
        ).first()
    return row is not None



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


# ---------------------------------------------------------------------------
# Analitik Super Admin: agregasi pemakaian dari tool_history / tool_job / users
# ---------------------------------------------------------------------------

def analytics_overview(days: int = 14) -> dict[str, Any]:
    """Ringkasan aktivitas untuk dashboard super-admin.

    Mengagregasi tanpa menyentuh isi `result` (hanya metadata) agar murah &
    privasi terjaga. Semua angka dihitung di SQL (cepat, lintas seluruh data).
    """
    ensure_settings_schema()
    days = max(1, min(90, int(days)))
    out: dict[str, Any] = {"days": days}
    with engine.connect() as c:
        # --- Kartu ringkasan ---
        out["totals"] = {
            "runs": int(c.execute(text("SELECT count(*) FROM tool_history")).scalar() or 0),
            "runs_window": int(
                c.execute(
                    text(
                        "SELECT count(*) FROM tool_history "
                        "WHERE created_at >= now() - make_interval(days => :d)"
                    ),
                    {"d": days},
                ).scalar()
                or 0
            ),
            "users": int(c.execute(text("SELECT count(*) FROM users")).scalar() or 0),
            "active_users_window": int(
                c.execute(
                    text(
                        "SELECT count(DISTINCT user_id) FROM tool_history "
                        "WHERE created_at >= now() - make_interval(days => :d)"
                    ),
                    {"d": days},
                ).scalar()
                or 0
            ),
            "new_users_window": int(
                c.execute(
                    text(
                        "SELECT count(*) FROM users "
                        "WHERE created_at >= now() - make_interval(days => :d)"
                    ),
                    {"d": days},
                ).scalar()
                or 0
            ),
            "tokens_outstanding": int(
                c.execute(text("SELECT COALESCE(sum(token_balance),0) FROM users")).scalar() or 0
            ),
        }

        # --- Pemakaian per tool (sepanjang masa) ---
        out["per_tool"] = [
            {"tool": r[0], "count": int(r[1])}
            for r in c.execute(
                text(
                    "SELECT tool, count(*) c FROM tool_history "
                    "GROUP BY tool ORDER BY c DESC"
                )
            )
        ]

        # --- Tren harian (window) ---
        out["daily"] = [
            {"day": str(r[0]), "runs": int(r[1]), "users": int(r[2])}
            for r in c.execute(
                text(
                    "SELECT date_trunc('day', created_at)::date AS d, "
                    "       count(*) AS runs, count(DISTINCT user_id) AS users "
                    "FROM tool_history "
                    "WHERE created_at >= now() - make_interval(days => :d) "
                    "GROUP BY d ORDER BY d"
                ),
                {"d": days},
            )
        ]

        # --- Pengguna teraktif (window) ---
        out["top_users"] = [
            {
                "user_id": int(r[0]) if r[0] is not None else None,
                "email": r[1],
                "name": r[2],
                "runs": int(r[3]),
            }
            for r in c.execute(
                text(
                    "SELECT h.user_id, u.email, u.name, count(*) AS runs "
                    "FROM tool_history h LEFT JOIN users u ON u.id = h.user_id "
                    "WHERE h.created_at >= now() - make_interval(days => :d) "
                    "GROUP BY h.user_id, u.email, u.name "
                    "ORDER BY runs DESC LIMIT 10"
                ),
                {"d": days},
            )
        ]

        # --- Kesehatan job async (error rate) ---
        try:
            job_rows = list(
                c.execute(
                    text(
                        "SELECT status, count(*) FROM tool_job "
                        "WHERE created_at >= now() - make_interval(days => :d) "
                        "GROUP BY status"
                    ),
                    {"d": days},
                )
            )
            by_status = {str(r[0]): int(r[1]) for r in job_rows}
            total_jobs = sum(by_status.values())
            out["jobs"] = {
                "by_status": by_status,
                "total": total_jobs,
                "error_rate": round(by_status.get("error", 0) / total_jobs, 4)
                if total_jobs
                else 0.0,
            }
        except Exception:  # noqa: BLE001 — tabel job opsional
            out["jobs"] = {"by_status": {}, "total": 0, "error_rate": 0.0}

    return out


def recent_activity(limit: int = 50, tool: str | None = None) -> list[dict[str, Any]]:
    """Feed aktivitas terbaru lintas SEMUA pengguna (metadata saja, tanpa isi).

    Berguna bagi super-admin untuk memantau penyalahgunaan / pola pemakaian.
    """
    ensure_settings_schema()
    limit = max(1, min(200, int(limit)))
    clause = ""
    params: dict[str, Any] = {"lim": limit}
    if tool:
        clause = "WHERE h.tool = :tool"
        params["tool"] = tool
    with engine.connect() as c:
        rows = c.execute(
            text(
                "SELECT h.id, h.user_id, u.email, u.name, h.tool, h.title, "
                "       h.input_preview, h.created_at "
                "FROM tool_history h LEFT JOIN users u ON u.id = h.user_id "
                f"{clause} "
                "ORDER BY h.created_at DESC LIMIT :lim"
            ),
            params,
        )
        return [
            {
                "id": int(r[0]),
                "user_id": int(r[1]) if r[1] is not None else None,
                "email": r[2],
                "name": r[3],
                "tool": r[4],
                "title": r[5],
                "input_preview": r[6],
                "created_at": r[7].isoformat() if r[7] else None,
            }
            for r in rows
        ]
