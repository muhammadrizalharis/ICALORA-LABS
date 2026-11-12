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
from datetime import timedelta

import zstandard
from sqlalchemy import text

from app.core.clients import engine
from app.core.config import get_settings

settings = get_settings()

_ZSTD_C = zstandard.ZstdCompressor(level=19)
_ZSTD_D = zstandard.ZstdDecompressor()


def _optimize_pdf(data: bytes) -> bytes:
    """Rapikan PDF (buang objek tak terpakai + deflate stream) tanpa mengubah
    tampilan. Mengembalikan versi terkecil; aman gagal ke data asli."""
    try:
        import pymupdf

        doc = pymupdf.open(stream=data, filetype="pdf")
        opt = doc.tobytes(garbage=4, deflate=True, clean=True)
        doc.close()
        return opt if 0 < len(opt) < len(data) else data
    except Exception:  # noqa: BLE001
        return data


def _pack_file_bytes(data: bytes, mime: str | None, filename: str | None) -> tuple[bytes, str]:
    """Kompres berkas untuk disimpan: optimasi PDF (bila PDF) lalu zstd."""
    body = data
    is_pdf = (mime or "").lower() == "application/pdf" or (filename or "").lower().endswith(".pdf")
    if is_pdf:
        body = _optimize_pdf(data)
    return _ZSTD_C.compress(body), "zstd"


def _unpack_file_bytes(data: bytes, compression: str | None) -> bytes:
    if compression == "zstd" and data:
        try:
            return _ZSTD_D.decompress(data)
        except Exception:  # noqa: BLE001
            return data
    return data


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
        "is_admin": bool(getattr(r, "is_admin", False)),
        "is_active": bool(getattr(r, "is_active", True)),
    }


_user_schema_ready = False


def ensure_user_schema() -> None:
    """Pastikan kolom is_admin, admin_password_hash & password_hash ada (idempoten)."""
    global _user_schema_ready
    if _user_schema_ready:
        return
    with engine.begin() as c:
        c.execute(
            text(
                "ALTER TABLE users ADD COLUMN IF NOT EXISTS "
                "is_admin BOOLEAN NOT NULL DEFAULT FALSE"
            )
        )
        c.execute(
            text("ALTER TABLE users ADD COLUMN IF NOT EXISTS admin_password_hash TEXT")
        )
        c.execute(
            text("ALTER TABLE users ADD COLUMN IF NOT EXISTS password_hash TEXT")
        )
        c.execute(
            text(
                "ALTER TABLE users ADD COLUMN IF NOT EXISTS "
                "is_active BOOLEAN NOT NULL DEFAULT TRUE"
            )
        )
    _user_schema_ready = True


def generate_password(length: int = 12) -> str:
    """Buat kata sandi acak mudah-dibaca (tanpa karakter ambigu)."""
    import secrets

    alphabet = "abcdefghijkmnpqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    return "".join(secrets.choice(alphabet) for _ in range(length))


def set_user_password(user_id: int, password: str) -> None:
    """Simpan hash kata sandi login untuk pengguna mana pun."""
    ensure_user_schema()
    h = _hash_password(password)
    with engine.begin() as c:
        c.execute(
            text("UPDATE users SET password_hash = :h WHERE id = :id"),
            {"h": h, "id": user_id},
        )


def verify_user_login(email: str, password: str) -> dict | None:
    """Verifikasi login email+kata sandi; kembalikan user bila cocok."""
    if not email or not password:
        return None
    ensure_user_schema()
    with engine.connect() as c:
        r = c.execute(
            text(
                "SELECT id, email, name, picture, token_balance, is_demo, is_admin, "
                "COALESCE(is_active, TRUE) AS is_active, "
                "password_hash FROM users WHERE lower(email) = lower(:email) "
                "ORDER BY id LIMIT 1"
            ),
            {"email": email},
        ).first()
    if r is None or not r.password_hash:
        return None
    if not bool(getattr(r, "is_active", True)):
        return None
    if not _verify_password_hash(password, r.password_hash):
        return None
    with engine.begin() as c:
        c.execute(text("UPDATE users SET last_login_at = now() WHERE id = :id"), {"id": r.id})
    return _row_to_user(r)


def _hash_password(password: str) -> str:
    """Hash kata sandi dengan PBKDF2-HMAC-SHA256 (stdlib, bergaram)."""
    salt = __import__("os").urandom(16)
    iterations = 200_000
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return f"pbkdf2_sha256${iterations}${salt.hex()}${dk.hex()}"


def _verify_password_hash(password: str, stored: str) -> bool:
    try:
        algo, iter_s, salt_hex, hash_hex = stored.split("$", 3)
        if algo != "pbkdf2_sha256":
            return False
        dk = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), bytes.fromhex(salt_hex), int(iter_s)
        )
        return hmac.compare_digest(dk.hex(), hash_hex)
    except Exception:  # noqa: BLE001
        return False


def _admin_password_hash() -> str | None:
    """Ambil hash kata sandi admin tersimpan (bila sudah pernah diganti)."""
    ensure_user_schema()
    with engine.connect() as c:
        r = c.execute(
            text("SELECT admin_password_hash FROM users WHERE email = :email"),
            {"email": settings.admin_email},
        ).first()
    return r[0] if r and r[0] else None


def admin_configured() -> bool:
    """Super admin aktif bila kata sandi di-env ATAU sudah diset di DB."""
    return bool(settings.admin_password) or _admin_password_hash() is not None


def verify_admin_password(password: str) -> bool:
    """Verifikasi kata sandi admin: utamakan hash DB, fallback ke env."""
    if not password:
        return False
    stored = _admin_password_hash()
    if stored is not None:
        return _verify_password_hash(password, stored)
    if settings.admin_password:
        return hmac.compare_digest(password, settings.admin_password)
    return False


def set_admin_password(new_password: str) -> None:
    """Simpan kata sandi admin baru (hash) di DB, menimpa nilai env."""
    upsert_admin_user()
    h = _hash_password(new_password)
    with engine.begin() as c:
        c.execute(
            text("UPDATE users SET admin_password_hash = :h WHERE email = :email"),
            {"h": h, "email": settings.admin_email},
        )


def get_user(user_id: int) -> dict | None:
    ensure_user_schema()
    with engine.connect() as c:
        r = c.execute(
            text(
                "SELECT id, email, name, picture, token_balance, is_demo, is_admin, "
                "COALESCE(is_active, TRUE) AS is_active "
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


class RegistrationClosed(Exception):
    """Pendaftaran pengguna baru sedang ditutup oleh Super Admin."""


def upsert_google_user(sub: str, email: str, name: str, picture: str) -> dict:
    ensure_user_schema()
    # Lazy import untuk menghindari circular import (admin -> auth).
    from app.services import admin as admin_svc

    with engine.connect() as c:
        existing = c.execute(
            text("SELECT id FROM users WHERE google_sub = :sub"), {"sub": sub}
        ).first()

    if existing is None and not admin_svc.is_registration_open():
        raise RegistrationClosed()

    grant = admin_svc.default_token_grant() if existing is None else None
    with engine.begin() as c:
        r = c.execute(
            text(
                """
                INSERT INTO users (google_sub, email, name, picture,
                                   token_balance, last_login_at)
                VALUES (:sub, :email, :name, :picture,
                        COALESCE(:grant, 0), now())
                ON CONFLICT (google_sub) DO UPDATE
                   SET email = EXCLUDED.email, name = EXCLUDED.name,
                       picture = EXCLUDED.picture, last_login_at = now()
                RETURNING id, email, name, picture, token_balance, is_demo, is_admin
                """
            ),
            {"sub": sub, "email": email, "name": name, "picture": picture, "grant": grant},
        ).first()
    return _row_to_user(r)


def upsert_admin_user() -> dict:
    """Buat/ambil akun super admin tunggal (berdasarkan email admin)."""
    ensure_user_schema()
    with engine.begin() as c:
        r = c.execute(
            text(
                "UPDATE users SET is_admin = TRUE, name = :name, last_login_at = now() "
                "WHERE email = :email "
                "RETURNING id, email, name, picture, token_balance, is_demo, is_admin"
            ),
            {"email": settings.admin_email, "name": settings.admin_name},
        ).first()
        if r is None:
            r = c.execute(
                text(
                    "INSERT INTO users (email, name, is_admin, last_login_at) "
                    "VALUES (:email, :name, TRUE, now()) "
                    "RETURNING id, email, name, picture, token_balance, is_demo, is_admin"
                ),
                {"email": settings.admin_email, "name": settings.admin_name},
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


def purge_expired_history() -> int:
    """Hapus riwayat yang lebih tua dari batas retensi (default 3 hari).

    Dipanggil secara oportunistik setiap kali riwayat dicatat/dibaca sehingga
    berkas hasil tidak disimpan melampaui masa simpan — sesuai kebijakan
    retensi: lebih dari N hari, berkas dihapus permanen.
    """
    days = max(1, int(settings.history_retention_days))
    ensure_file_schema()
    with engine.begin() as c:
        c.execute(
            text(
                "DELETE FROM tool_file "
                "WHERE created_at < now() - make_interval(days => :days)"
            ),
            {"days": days},
        )
        res = c.execute(
            text(
                "DELETE FROM tool_history "
                "WHERE created_at < now() - make_interval(days => :days)"
            ),
            {"days": days},
        )
    return res.rowcount or 0


_FILE_SCHEMA_READY = False


def ensure_file_schema() -> None:
    """Buat tabel penyimpanan berkas asli (di VM Postgres) bila belum ada.

    Berkas asli (mis. PDF) disimpan sebagai bytea DI VM yang sama dengan
    riwayat — tidak menyentuh disk HPC — dan ikut kebijakan hapus 3 hari.
    """
    global _FILE_SCHEMA_READY
    if _FILE_SCHEMA_READY:
        return
    with engine.begin() as c:
        c.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS tool_file (
                    id          bigserial PRIMARY KEY,
                    user_id     bigint NOT NULL,
                    history_id  bigint,
                    filename    text,
                    mime        text,
                    byte_size   bigint,
                    sha256      text,
                    data        bytea NOT NULL,
                    created_at  timestamptz NOT NULL DEFAULT now()
                )
                """
            )
        )
        c.execute(
            text("CREATE INDEX IF NOT EXISTS idx_tool_file_history ON tool_file(history_id)")
        )
        c.execute(
            text("CREATE INDEX IF NOT EXISTS idx_tool_file_user ON tool_file(user_id)")
        )
        c.execute(
            text("ALTER TABLE tool_file ADD COLUMN IF NOT EXISTS compression text")
        )
        c.execute(
            text("ALTER TABLE tool_file ADD COLUMN IF NOT EXISTS stored_size bigint")
        )
    _FILE_SCHEMA_READY = True


def record_history(
    user_id: int, tool: str, title: str, input_preview: str, result: dict
) -> int | None:
    with engine.begin() as c:
        row = c.execute(
            text(
                """
                INSERT INTO tool_history (user_id, tool, title, input_preview, result)
                VALUES (:uid, :tool, :title, :prev, CAST(:res AS jsonb))
                RETURNING id
                """
            ),
            {
                "uid": user_id,
                "tool": tool,
                "title": title[:200] if title else None,
                "prev": input_preview[:500] if input_preview else None,
                "res": json.dumps(result)[:200000],
            },
        ).first()
    try:
        purge_expired_history()
    except Exception:  # noqa: BLE001, S110
        pass
    return int(row.id) if row else None


def save_tool_file(
    user_id: int,
    history_id: int | None,
    filename: str | None,
    mime: str | None,
    data: bytes,
    sha256: str | None = None,
) -> int | None:
    """Simpan berkas asli di VM (terkompresi). Kembalikan id baris."""
    ensure_file_schema()
    stored, comp = _pack_file_bytes(data, mime, filename)
    with engine.begin() as c:
        row = c.execute(
            text(
                """
                INSERT INTO tool_file
                    (user_id, history_id, filename, mime, byte_size, stored_size,
                     sha256, data, compression)
                VALUES (:uid, :hid, :fn, :mime, :sz, :ssz, :sha, :data, :comp)
                RETURNING id
                """
            ),
            {
                "uid": user_id,
                "hid": history_id,
                "fn": (filename or "")[:300] or None,
                "mime": (mime or "")[:120] or None,
                "sz": len(data),
                "ssz": len(stored),
                "sha": sha256,
                "data": stored,
                "comp": comp,
            },
        ).first()
    return int(row.id) if row else None


def get_tool_file_by_history(user_id: int, history_id: int) -> dict | None:
    """Ambil berkas asli untuk sebuah riwayat (hanya dalam masa retensi)."""
    ensure_file_schema()
    days = max(1, int(settings.history_retention_days))
    with engine.connect() as c:
        r = c.execute(
            text(
                "SELECT filename, mime, byte_size, data, compression FROM tool_file "
                "WHERE user_id = :uid AND history_id = :hid "
                "AND created_at >= now() - make_interval(days => :days) "
                "ORDER BY id DESC LIMIT 1"
            ),
            {"uid": user_id, "hid": history_id, "days": days},
        ).first()
    if not r:
        return None
    raw = bytes(r.data) if r.data is not None else b""
    return {
        "filename": r.filename,
        "mime": r.mime,
        "byte_size": r.byte_size,
        "data": _unpack_file_bytes(raw, r.compression),
    }


def list_history(user_id: int, tool: str | None = None, limit: int = 50) -> list[dict]:
    try:
        purge_expired_history()
    except Exception:  # noqa: BLE001, S110
        pass
    days = max(1, int(settings.history_retention_days))
    q = (
        "SELECT id, tool, title, input_preview, created_at FROM tool_history "
        "WHERE user_id = :uid AND created_at >= now() - make_interval(days => :days)"
    )
    params: dict = {"uid": user_id, "limit": limit, "days": days}
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
    days = max(1, int(settings.history_retention_days))
    with engine.connect() as c:
        r = c.execute(
            text(
                "SELECT id, tool, title, input_preview, result, created_at "
                "FROM tool_history WHERE user_id = :uid AND id = :id "
                "AND created_at >= now() - make_interval(days => :days)"
            ),
            {"uid": user_id, "id": item_id, "days": days},
        ).first()
    if not r:
        return None
    created = r.created_at
    expires = (created + timedelta(days=days)) if created else None
    return {
        "id": r.id,
        "tool": r.tool,
        "title": r.title,
        "input_preview": r.input_preview,
        "result": r.result,
        "created_at": created.isoformat() if created else None,
        "expires_at": expires.isoformat() if expires else None,
        "retention_days": days,
        "file": get_file_meta_by_history(user_id, item_id),
    }


def get_file_meta_by_history(user_id: int, history_id: int) -> dict | None:
    """Metadata berkas asli (tanpa blob data) untuk panel Informasi File."""
    ensure_file_schema()
    days = max(1, int(settings.history_retention_days))
    with engine.connect() as c:
        r = c.execute(
            text(
                "SELECT filename, mime, byte_size, sha256 FROM tool_file "
                "WHERE user_id = :uid AND history_id = :hid "
                "AND created_at >= now() - make_interval(days => :days) "
                "ORDER BY id DESC LIMIT 1"
            ),
            {"uid": user_id, "hid": history_id, "days": days},
        ).first()
    if not r:
        return None
    return {
        "filename": r.filename,
        "mime": r.mime,
        "byte_size": r.byte_size,
        "sha256": r.sha256,
    }


def delete_history_item(user_id: int, item_id: int) -> bool:
    ensure_file_schema()
    with engine.begin() as c:
        c.execute(
            text("DELETE FROM tool_file WHERE user_id = :uid AND history_id = :id"),
            {"uid": user_id, "id": item_id},
        )
        res = c.execute(
            text("DELETE FROM tool_history WHERE user_id = :uid AND id = :id"),
            {"uid": user_id, "id": item_id},
        )
    return res.rowcount > 0
