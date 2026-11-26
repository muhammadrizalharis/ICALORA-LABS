"""Paket berbayar: langganan bulanan, diskon cek ulang revisi, dan referral.

Saldo pengguna (`users.token_balance`) bersatuan Rupiah. Pembayaran manual
(transfer DANA + konfirmasi WhatsApp) dikonfirmasi admin lewat panel, yang
memanggil `on_topup` / `activate_subscription` di sini.
"""

from __future__ import annotations

import hashlib
import re
import secrets
import unicodedata
from typing import Any

from sqlalchemy import text

from app.core.clients import engine

_schema_ready = False

_FP_K = 256  # ukuran sketsa bottom-k untuk sidik jari dokumen
_SHINGLE = 3  # jumlah kata per shingle
_CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"

PACKAGE_DEFAULTS: dict[str, Any] = {
    "subscription_price": 200_000,
    "subscription_days": 30,
    "revision_discount_pct": 37,
    "revision_window_hours": 24,
    "revision_max": 1,
    "revision_min_similarity": 0.4,
    "revision_tools": ["plagiarism-checker", "ai-detector"],
    "referral_bonus": 2_000,
    "referral_min_topup": 8_000,
}


def ensure_billing_schema() -> None:
    global _schema_ready
    if _schema_ready:
        return
    with engine.begin() as c:
        for ddl in (
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS sub_until timestamptz",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS referral_code text",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS referred_by bigint",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS referral_rewarded_at timestamptz",
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_users_referral_code "
            "ON users(referral_code) WHERE referral_code IS NOT NULL",
            """
            CREATE TABLE IF NOT EXISTS charge_log (
                id          bigserial PRIMARY KEY,
                user_id     bigint NOT NULL,
                tool        text NOT NULL,
                amount      bigint NOT NULL DEFAULT 0,
                discount    bigint NOT NULL DEFAULT 0,
                parent_id   bigint,
                job_id      text,
                fingerprint jsonb NOT NULL DEFAULT '[]'::jsonb,
                voided      boolean NOT NULL DEFAULT FALSE,
                created_at  timestamptz NOT NULL DEFAULT now()
            )
            """,
            "CREATE INDEX IF NOT EXISTS idx_charge_log_user_tool "
            "ON charge_log(user_id, tool, created_at DESC)",
            "CREATE INDEX IF NOT EXISTS idx_charge_log_job ON charge_log(job_id)",
        ):
            c.execute(text(ddl))
    _schema_ready = True


def packages() -> dict[str, Any]:
    from app.services import admin as admin_svc

    raw = admin_svc.get_setting("packages", None)
    return clean_packages({**PACKAGE_DEFAULTS, **(raw if isinstance(raw, dict) else {})})


def clean_packages(raw: dict[str, Any]) -> dict[str, Any]:
    def _int(key: str, lo: int, hi: int) -> int:
        try:
            v = int(raw.get(key, PACKAGE_DEFAULTS[key]))
        except (TypeError, ValueError):
            v = int(PACKAGE_DEFAULTS[key])
        return max(lo, min(hi, v))

    try:
        sim = float(raw.get("revision_min_similarity", 0.4))
    except (TypeError, ValueError):
        sim = 0.4
    tools = raw.get("revision_tools", PACKAGE_DEFAULTS["revision_tools"])
    if not isinstance(tools, list):
        tools = list(PACKAGE_DEFAULTS["revision_tools"])
    return {
        "subscription_price": _int("subscription_price", 0, 100_000_000),
        "subscription_days": _int("subscription_days", 1, 366),
        "revision_discount_pct": _int("revision_discount_pct", 0, 100),
        "revision_window_hours": _int("revision_window_hours", 1, 24 * 90),
        "revision_max": _int("revision_max", 0, 100),
        "revision_min_similarity": max(0.1, min(1.0, sim)),
        "revision_tools": [str(t) for t in tools][:20],
        "referral_bonus": _int("referral_bonus", 0, 10_000_000),
        "referral_min_topup": _int("referral_min_topup", 0, 100_000_000),
    }


# ---------------------------------------------------------------- langganan


def subscription_active(user_id: int | None) -> bool:
    if not user_id:
        return False
    ensure_billing_schema()
    with engine.connect() as c:
        r = c.execute(
            text("SELECT sub_until > now() FROM users WHERE id = :id"), {"id": user_id}
        ).first()
    return bool(r and r[0])


def activate_subscription(user_id: int, days: int) -> str | None:
    """Perpanjang langganan `days` hari (ditumpuk bila masih aktif). Kembalikan ISO akhir."""
    ensure_billing_schema()
    with engine.begin() as c:
        r = c.execute(
            text(
                "UPDATE users SET sub_until = GREATEST(COALESCE(sub_until, now()), now()) "
                "+ make_interval(days => :d) WHERE id = :id RETURNING sub_until"
            ),
            {"d": int(days), "id": user_id},
        ).first()
    return r[0].isoformat() if r and r[0] else None


def cancel_subscription(user_id: int) -> None:
    ensure_billing_schema()
    with engine.begin() as c:
        c.execute(text("UPDATE users SET sub_until = NULL WHERE id = :id"), {"id": user_id})


# ---------------------------------------------------------------- referral


def referral_code(user_id: int) -> str:
    """Kode referral milik pengguna (dibuat sekali, lalu tetap)."""
    ensure_billing_schema()
    with engine.begin() as c:
        r = c.execute(
            text("SELECT referral_code FROM users WHERE id = :id"), {"id": user_id}
        ).first()
        if r and r[0]:
            return str(r[0])
        for _ in range(10):
            code = "".join(secrets.choice(_CODE_ALPHABET) for _ in range(7))
            done = c.execute(
                text(
                    "UPDATE users SET referral_code = :code WHERE id = :id "
                    "AND referral_code IS NULL AND NOT EXISTS "
                    "(SELECT 1 FROM users WHERE referral_code = :code) RETURNING referral_code"
                ),
                {"code": code, "id": user_id},
            ).first()
            if done:
                return str(done[0])
        r = c.execute(
            text("SELECT referral_code FROM users WHERE id = :id"), {"id": user_id}
        ).first()
    return str(r[0]) if r and r[0] else ""


def attach_referral(user_id: int, code: str | None) -> bool:
    """Tautkan pengguna BARU (< 1 jam) ke pengajaknya. Abaikan kode diri sendiri/tak valid."""
    code = (code or "").strip().upper()
    if not code or len(code) > 20:
        return False
    ensure_billing_schema()
    with engine.begin() as c:
        r = c.execute(
            text(
                "UPDATE users u SET referred_by = ref.id "
                "FROM users ref "
                "WHERE u.id = :uid AND ref.referral_code = :code AND ref.id <> u.id "
                "AND u.referred_by IS NULL AND u.created_at > now() - interval '1 hour' "
                "AND COALESCE(u.is_demo, FALSE) = FALSE "
                "RETURNING u.id"
            ),
            {"uid": user_id, "code": code},
        ).first()
    return r is not None


def on_topup(user_id: int, amount: int) -> dict | None:
    """Dipanggil saat admin mengonfirmasi pembayaran. Cairkan bonus referral sekali."""
    cfg = packages()
    bonus = cfg["referral_bonus"]
    if bonus <= 0 or amount < cfg["referral_min_topup"]:
        return None
    ensure_billing_schema()
    from app.services.admin import MAX_TOKEN_BALANCE

    with engine.begin() as c:
        r = c.execute(
            text(
                "UPDATE users SET referral_rewarded_at = now(), "
                "token_balance = LEAST(token_balance + :b, :mx) "
                "WHERE id = :id AND referred_by IS NOT NULL AND referral_rewarded_at IS NULL "
                "RETURNING referred_by"
            ),
            {"id": user_id, "b": bonus, "mx": MAX_TOKEN_BALANCE},
        ).first()
        if not r:
            return None
        c.execute(
            text(
                "UPDATE users SET token_balance = LEAST(token_balance + :b, :mx) WHERE id = :id"
            ),
            {"id": int(r[0]), "b": bonus, "mx": MAX_TOKEN_BALANCE},
        )
    return {"referrer_id": int(r[0]), "bonus": bonus}


def referral_stats(user_id: int) -> dict[str, int]:
    ensure_billing_schema()
    with engine.connect() as c:
        r = c.execute(
            text(
                "SELECT count(*), count(referral_rewarded_at) FROM users WHERE referred_by = :id"
            ),
            {"id": user_id},
        ).first()
    return {"joined": int(r[0]) if r else 0, "rewarded": int(r[1]) if r else 0}


def user_billing(user_id: int) -> dict[str, Any]:
    ensure_billing_schema()
    with engine.connect() as c:
        r = c.execute(
            text("SELECT sub_until, sub_until > now() FROM users WHERE id = :id"),
            {"id": user_id},
        ).first()
    return {
        "sub_until": r[0].isoformat() if r and r[0] else None,
        "sub_active": bool(r and r[1]),
        "referral_code": referral_code(user_id),
        "referral": referral_stats(user_id),
    }


# ---------------------------------------------------------------- cek ulang revisi


def fingerprint(doc: str) -> list[int]:
    """Sketsa bottom-k dari shingle 3-kata (stabil antar-proses, tahan revisi kecil)."""
    norm = unicodedata.normalize("NFKC", doc or "").lower()
    words = re.findall(r"\w+", norm)
    if not words:
        return []
    if len(words) < _SHINGLE:
        grams = [" ".join(words)]
    else:
        grams = [" ".join(words[i : i + _SHINGLE]) for i in range(len(words) - _SHINGLE + 1)]
    hashes = {
        int.from_bytes(hashlib.blake2b(g.encode(), digest_size=6).digest(), "big")
        for g in grams
    }
    return sorted(hashes)[:_FP_K]


def similarity(a: list[int], b: list[int]) -> float:
    """Estimasi Jaccard dari dua sketsa bottom-k."""
    if not a or not b:
        return 0.0
    sa, sb = set(a), set(b)
    k = min(_FP_K, len(sa | sb))
    union_k = sorted(sa | sb)[:k]
    both = sum(1 for h in union_k if h in sa and h in sb)
    return both / k if k else 0.0


def revision_price(full: int) -> int:
    """Harga cek ulang revisi untuk harga penuh `full`."""
    return full - full * packages()["revision_discount_pct"] // 100


def has_revision_candidate(user_id: int, tool: str) -> bool:
    """Ada pemeriksaan sebelumnya yang masih berhak diskon revisi (tanpa cek dokumen)."""
    cfg = packages()
    if (
        tool not in cfg["revision_tools"]
        or cfg["revision_max"] <= 0
        or cfg["revision_discount_pct"] <= 0
    ):
        return False
    ensure_billing_schema()
    with engine.connect() as c:
        row = c.execute(
            text(
                "SELECT 1 FROM charge_log p "
                "WHERE p.user_id = :uid AND p.tool = :tool AND p.parent_id IS NULL "
                "AND NOT p.voided AND p.discount = 0 "
                "AND p.created_at > now() - make_interval(hours => :h) "
                "AND (SELECT count(*) FROM charge_log ch "
                "     WHERE ch.parent_id = p.id AND NOT ch.voided) < :mx LIMIT 1"
            ),
            {
                "uid": user_id,
                "tool": tool,
                "h": cfg["revision_window_hours"],
                "mx": cfg["revision_max"],
            },
        ).first()
    return row is not None


def revision_quote(user_id: int, tool: str, doc: str, charged: int) -> dict[str, Any]:
    """Hitung diskon cek ulang. Kembalikan {discount, parent_id, fingerprint}."""
    fp = fingerprint(doc)
    out: dict[str, Any] = {"discount": 0, "parent_id": None, "fingerprint": fp}
    cfg = packages()
    if charged <= 0 or not fp or tool not in cfg["revision_tools"] or cfg["revision_max"] <= 0:
        return out
    ensure_billing_schema()
    with engine.connect() as c:
        rows = c.execute(
            text(
                "SELECT p.id, p.fingerprint FROM charge_log p "
                "WHERE p.user_id = :uid AND p.tool = :tool AND p.parent_id IS NULL "
                "AND NOT p.voided AND p.discount = 0 "
                "AND p.created_at > now() - make_interval(hours => :h) "
                "AND (SELECT count(*) FROM charge_log ch "
                "     WHERE ch.parent_id = p.id AND NOT ch.voided) < :mx "
                "ORDER BY p.created_at DESC LIMIT 30"
            ),
            {
                "uid": user_id,
                "tool": tool,
                "h": cfg["revision_window_hours"],
                "mx": cfg["revision_max"],
            },
        ).all()
    best_id, best_sim = None, 0.0
    for pid, pfp in rows:
        sim = similarity(fp, list(pfp or []))
        if sim > best_sim:
            best_id, best_sim = pid, sim
    if best_id is not None and best_sim >= cfg["revision_min_similarity"]:
        out["discount"] = charged * cfg["revision_discount_pct"] // 100
        out["parent_id"] = int(best_id)
    return out


def log_charge(
    user_id: int,
    tool: str,
    amount: int,
    quote: dict[str, Any],
    job_id: str | None,
) -> None:
    import json

    ensure_billing_schema()
    with engine.begin() as c:
        c.execute(
            text(
                "INSERT INTO charge_log (user_id, tool, amount, discount, parent_id, job_id, "
                "fingerprint) VALUES (:uid, :tool, :amt, :disc, :pid, :job, CAST(:fp AS jsonb))"
            ),
            {
                "uid": user_id,
                "tool": tool,
                "amt": int(amount),
                "disc": int(quote.get("discount") or 0),
                "pid": quote.get("parent_id"),
                "job": job_id,
                "fp": json.dumps(quote.get("fingerprint") or []),
            },
        )
