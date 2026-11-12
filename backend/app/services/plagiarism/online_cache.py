"""Cache teks-penuh OA yang berhasil diunduh.

Menyimpan TEKS (bukan berkas PDF) di PostgreSQL agar pemeriksaan bersifat
DETERMINISTIK: sekali teks penuh sebuah sumber terambil, cek berikutnya
memakai ulang teks itu alih-alih mengunduh ulang. Ini mencegah skor berayun
liar (mis. 94%→7%) ketika server penerbit kebetulan lambat/putus saat satu
pemeriksaan. Gagal-aman: galat apa pun pada cache tak boleh membatalkan cek.
"""

from __future__ import annotations

import hashlib

from sqlalchemy import text

from app.core.clients import engine
from app.core.config import get_settings

settings = get_settings()

_SCHEMA_READY = False


def _ensure_schema() -> None:
    global _SCHEMA_READY
    if _SCHEMA_READY:
        return
    try:
        with engine.begin() as conn:
            conn.execute(
                text(
                    "CREATE TABLE IF NOT EXISTS online_fulltext_cache ("
                    "cache_key TEXT PRIMARY KEY, "
                    "full_text TEXT NOT NULL, "
                    "char_len INTEGER NOT NULL, "
                    "fetched_at TIMESTAMPTZ NOT NULL DEFAULT now())"
                )
            )
        _SCHEMA_READY = True
    except Exception:  # noqa: BLE001, S110
        pass


def cache_key(doi: str | None, url: str | None) -> str | None:
    """Kunci stabil per-sumber: utamakan DOI (ternormalisasi), lalu hash URL."""
    d = (doi or "").strip().lower()
    if d:
        return f"doi:{d}"
    u = (url or "").strip()
    if u:
        return "url:" + hashlib.sha256(u.encode("utf-8")).hexdigest()
    return None


def get(key: str | None) -> str | None:
    """Ambil teks penuh tersimpan bila ada & belum kedaluwarsa."""
    if not key or not settings.online_fulltext_cache_enabled:
        return None
    _ensure_schema()
    try:
        ttl = max(1, int(settings.online_fulltext_cache_ttl_days))
        with engine.connect() as conn:
            row = conn.execute(
                text(
                    "SELECT full_text FROM online_fulltext_cache "
                    "WHERE cache_key = :k "
                    "AND fetched_at > now() - make_interval(days => :ttl)"
                ),
                {"k": key, "ttl": ttl},
            ).first()
        if row and row[0]:
            return str(row[0])
    except Exception:  # noqa: BLE001, S110
        pass
    return None


def put(key: str | None, full_text: str) -> None:
    """Simpan/segarkan teks penuh yang berhasil diunduh (upsert)."""
    if not key or not settings.online_fulltext_cache_enabled:
        return
    if not full_text or len(full_text) < 500:
        return
    _ensure_schema()
    try:
        with engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO online_fulltext_cache "
                    "(cache_key, full_text, char_len, fetched_at) "
                    "VALUES (:k, :t, :n, now()) "
                    "ON CONFLICT (cache_key) DO UPDATE SET "
                    "full_text = EXCLUDED.full_text, "
                    "char_len = EXCLUDED.char_len, "
                    "fetched_at = now() "
                    "WHERE EXCLUDED.char_len >= online_fulltext_cache.char_len"
                ),
                {"k": key, "t": full_text, "n": len(full_text)},
            )
    except Exception:  # noqa: BLE001, S110
        pass
