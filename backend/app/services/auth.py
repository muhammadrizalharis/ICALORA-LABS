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
    return {
        "id": r.id,
        "tool": r.tool,
        "title": r.title,
        "input_preview": r.input_preview,
        "result": r.result,
        "created_at": r.created_at.isoformat() if r.created_at else None,
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
