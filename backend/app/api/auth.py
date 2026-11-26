"""Endpoint autentikasi, sesi, profil, dan riwayat (history) pengguna."""

from __future__ import annotations

import secrets
import urllib.parse
from typing import Any

import httpx
from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field

from app.core.config import get_settings
from app.services import admin as admin_svc
from app.services import auth as svc
from app.services import billing as billing_svc
from app.services import email as email_svc

settings = get_settings()
router = APIRouter(prefix="/auth", tags=["auth"])


class AdminLoginIn(BaseModel):
    password: str


class AdminPasswordIn(BaseModel):
    current_password: str
    new_password: str


class PasswordLoginIn(BaseModel):
    email: str
    password: str


class AdminUserPatchIn(BaseModel):
    token_balance: int | None = None
    is_staff: bool | None = None  # peran "Admin" (admin biasa); hanya Super Admin yang bisa
    is_active: bool | None = None
    name: str | None = None


class AdminTokenIn(BaseModel):
    add: int | None = Field(default=None, ge=1)  # tambah saldo (admin biasa & super)
    set: int | None = Field(default=None, ge=0)  # tetapkan saldo (hanya super)


class AdminSettingsIn(BaseModel):
    maintenance_mode: bool | None = None
    registration_open: bool | None = None
    default_token_grant: int | None = None
    feature_flags: dict[str, bool] | None = None
    rate_limit_enabled: bool | None = None
    rate_limit_per_min: int | None = None
    token_enforcement: bool | None = None
    default_tool_cost: int | None = None
    tool_costs: dict[str, int] | None = None
    payment_info: dict[str, Any] | None = None
    packages: dict[str, Any] | None = None


class AdminSubscriptionIn(BaseModel):
    days: int | None = Field(default=None, ge=1, le=366)  # kosong = durasi paket
    cancel: bool = False

GOOGLE_AUTH = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN = "https://oauth2.googleapis.com/token"  # noqa: S105
GOOGLE_USERINFO = "https://openidconnect.googleapis.com/v1/userinfo"


def _set_session(resp: Response, user_id: int) -> None:
    resp.set_cookie(
        key=settings.session_cookie,
        value=svc.make_session_token(user_id),
        max_age=settings.session_ttl_days * 86400,
        httponly=True,
        samesite="lax",
        path="/",
    )


def current_user(request: Request) -> dict:
    token = request.cookies.get(settings.session_cookie)
    uid = svc.verify_session_token(token)
    if not uid:
        raise HTTPException(status_code=401, detail="Belum login.")
    user = svc.get_user(uid)
    if not user:
        raise HTTPException(status_code=401, detail="Sesi tidak valid.")
    if not user.get("is_active", True) and not user.get("is_admin"):
        raise HTTPException(status_code=403, detail="Akun Anda dinonaktifkan.")
    return user


def optional_user(request: Request) -> dict | None:
    token = request.cookies.get(settings.session_cookie)
    uid = svc.verify_session_token(token)
    user = svc.get_user(uid) if uid else None
    if user and not user.get("is_active", True) and not user.get("is_admin"):
        return None
    return user


def require_admin(request: Request) -> dict:
    user = current_user(request)
    if not user.get("is_admin"):
        raise HTTPException(status_code=403, detail="Hanya Super Admin.")
    return user


def require_staff(request: Request) -> dict:
    """Super Admin ATAU admin biasa (is_staff, akun aktif)."""
    user = current_user(request)
    if user.get("is_admin"):
        return user
    if user.get("is_staff") and user.get("is_active", True):
        return user
    raise HTTPException(status_code=403, detail="Hanya admin.")


@router.get("/me")
def me(request: Request) -> dict:
    user = optional_user(request)
    return {
        "authenticated": user is not None,
        "user": user,
        "google_enabled": bool(settings.google_client_id and settings.google_client_secret),
        "admin_enabled": svc.admin_configured(),
        "password_login_enabled": True,
        "email_enabled": email_svc.smtp_configured(),
        "history_retention_days": settings.history_retention_days,
        "maintenance_mode": admin_svc.is_maintenance(),
        "registration_open": admin_svc.is_registration_open(),
        "token_enforcement": admin_svc.token_enforcement_enabled(),
        "default_tool_cost": admin_svc.tool_cost(""),
        "tool_costs": admin_svc.public_tool_costs(),
        "payment_info": admin_svc.payment_info(),
        "packages": billing_svc.packages(),
        "billing": billing_svc.user_billing(int(user["id"])) if user else None,
    }


@router.post("/login")
def password_login(body: PasswordLoginIn, response: Response) -> dict:
    """Login dengan email + kata sandi (alternatif Google)."""
    user = svc.verify_user_login(body.email.strip(), body.password)
    if not user:
        raise HTTPException(status_code=401, detail="Email atau kata sandi salah.")
    _set_session(response, user["id"])
    return {"ok": True, "user": user}


@router.post("/reset-password")
async def reset_password(request: Request) -> dict:
    """Buat kata sandi baru untuk pengguna aktif: tampil sekali + kirim email."""
    user = current_user(request)
    new_pw = svc.generate_password(12)
    svc.set_user_password(user["id"], new_pw)
    emailed = False
    email_error: str | None = None
    to = user.get("email")
    if to and email_svc.smtp_configured():
        try:
            await run_in_threadpool(email_svc.send_new_password, to, user.get("name"), new_pw)
            emailed = True
        except Exception as exc:  # noqa: BLE001
            email_error = str(exc)
    elif not email_svc.smtp_configured():
        email_error = "Email server belum dikonfigurasi."
    elif not to:
        email_error = "Akun tidak memiliki alamat email."
    return {
        "ok": True,
        "password": new_pw,
        "email": to,
        "emailed": emailed,
        "email_error": email_error,
    }


@router.post("/admin-login")
def admin_login(body: AdminLoginIn, response: Response) -> dict:
    """Login super admin melalui kata sandi privat (tanpa Google)."""
    if not svc.admin_configured():
        raise HTTPException(status_code=503, detail="Super admin belum dikonfigurasi.")
    if not svc.verify_admin_password(body.password):
        raise HTTPException(status_code=401, detail="Kata sandi admin salah.")
    user = svc.upsert_admin_user()
    _set_session(response, user["id"])
    return {"ok": True, "user": user}


@router.post("/admin-password")
def admin_password(body: AdminPasswordIn, request: Request) -> dict:
    """Ubah kata sandi super admin (butuh sesi admin + kata sandi lama)."""
    user = current_user(request)
    if not user.get("is_admin"):
        raise HTTPException(status_code=403, detail="Hanya super admin.")
    if not svc.verify_admin_password(body.current_password):
        raise HTTPException(status_code=401, detail="Kata sandi lama salah.")
    new_pw = (body.new_password or "").strip()
    if len(new_pw) < 8:
        raise HTTPException(status_code=422, detail="Kata sandi baru minimal 8 karakter.")
    svc.set_admin_password(new_pw)
    return {"ok": True}


@router.post("/logout")
def logout(response: Response) -> dict:
    response.delete_cookie(settings.session_cookie, path="/")
    return {"ok": True}


@router.get("/google/login")
def google_login() -> RedirectResponse:
    if not settings.google_client_id:
        raise HTTPException(status_code=503, detail="Google OAuth belum dikonfigurasi.")
    state = secrets.token_urlsafe(16)
    params = {
        "client_id": settings.google_client_id,
        "redirect_uri": settings.google_redirect_uri,
        "response_type": "code",
        "scope": "openid email profile",
        "state": state,
        "access_type": "online",
        "prompt": "select_account",
    }
    url = f"{GOOGLE_AUTH}?{urllib.parse.urlencode(params)}"
    resp = RedirectResponse(url)
    resp.set_cookie("oauth_state", state, max_age=600, httponly=True, samesite="lax", path="/")
    return resp


@router.get("/google/callback")
def google_callback(
    code: str | None = None,
    state: str | None = None,
    oauth_state: str | None = Cookie(default=None),
    icalora_ref: str | None = Cookie(default=None),
) -> RedirectResponse:
    if not code:
        raise HTTPException(status_code=400, detail="Kode otorisasi tidak ada.")
    if not oauth_state or state != oauth_state:
        raise HTTPException(status_code=400, detail="State OAuth tidak cocok.")
    try:
        with httpx.Client(timeout=20) as client:
            tok = client.post(
                GOOGLE_TOKEN,
                data={
                    "code": code,
                    "client_id": settings.google_client_id,
                    "client_secret": settings.google_client_secret,
                    "redirect_uri": settings.google_redirect_uri,
                    "grant_type": "authorization_code",
                },
            )
            tok.raise_for_status()
            access_token = tok.json()["access_token"]
            info = client.get(
                GOOGLE_USERINFO, headers={"Authorization": f"Bearer {access_token}"}
            )
            info.raise_for_status()
            data = info.json()
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"Gagal login Google: {exc}") from exc

    try:
        user = svc.upsert_google_user(
            sub=data["sub"],
            email=data.get("email", ""),
            name=data.get("name", ""),
            picture=data.get("picture", ""),
        )
    except svc.RegistrationClosed:
        resp = RedirectResponse(f"{settings.frontend_base_url}/login?error=registration_closed")
        resp.delete_cookie("oauth_state", path="/")
        return resp
    if icalora_ref:
        try:
            billing_svc.attach_referral(int(user["id"]), icalora_ref)
        except Exception:  # noqa: BLE001 - referral tak boleh menggagalkan login
            pass
    resp = RedirectResponse(f"{settings.frontend_base_url}/dashboard")
    _set_session(resp, user["id"])
    resp.delete_cookie("oauth_state", path="/")
    resp.delete_cookie("icalora_ref", path="/")
    return resp


@router.get("/history")
def history(request: Request, tool: str | None = None, limit: int = 50) -> dict:
    user = current_user(request)
    return {"items": svc.list_history(user["id"], tool, min(limit, 100))}


@router.get("/history/{item_id}")
def history_item(item_id: int, user: dict = Depends(current_user)) -> dict:  # noqa: B008
    item = svc.get_history_item(user["id"], item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Riwayat tidak ditemukan.")
    return item


@router.delete("/history/{item_id}")
def history_delete(item_id: int, user: dict = Depends(current_user)) -> dict:  # noqa: B008
    ok = svc.delete_history_item(user["id"], item_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Riwayat tidak ditemukan.")
    return {"ok": True}


# ====================== SUPER ADMIN: KELOLA PENGGUNA & PENGATURAN ======================


@router.get("/admin/users")
def admin_list_users(
    request: Request, q: str | None = None, limit: int = 200
) -> dict:
    require_staff(request)
    return {
        "users": admin_svc.list_users(q, limit),
        "stats": admin_svc.count_users(),
    }


@router.patch("/admin/users/{user_id}")
def admin_patch_user(user_id: int, body: AdminUserPatchIn, request: Request) -> dict:
    admin = require_admin(request)
    target = admin_svc.get_admin_user(user_id)
    if not target:
        raise HTTPException(status_code=404, detail="Pengguna tidak ditemukan.")
    # Jangan biarkan admin menonaktifkan dirinya sendiri.
    if user_id == admin["id"] and body.is_active is False:
        raise HTTPException(status_code=400, detail="Tidak bisa menonaktifkan diri sendiri.")
    if body.is_staff is not None and (target["is_admin"] or target["is_demo"]):
        raise HTTPException(
            status_code=400, detail="Peran Admin tidak berlaku untuk Super Admin/akun demo."
        )
    fields = body.model_dump(exclude_none=True)
    before = {k: target.get(k) for k in fields}  # ambil SEBELUM diubah (untuk audit)
    updated = admin_svc.update_user(user_id, fields)
    for key, label in (
        ("is_staff", "role"), ("is_active", "active"), ("token_balance", "tokens_set"),
        ("name", "rename"),
    ):
        if key in fields:
            admin_svc.record_audit(
                admin, f"user.{label}", target, {"from": before[key], "to": fields[key]}
            )
    return {"ok": True, "user": updated}


@router.post("/admin/users/{user_id}/tokens")
def admin_give_tokens(user_id: int, body: AdminTokenIn, request: Request) -> dict:
    """Beri token. Admin biasa: hanya `add` pada pengguna biasa, dibatasi per pemberian.

    Super Admin: `add` tanpa batas atau `set` (tetapkan saldo).
    """
    actor = require_staff(request)
    is_super = bool(actor.get("is_admin"))
    if (body.add is None) == (body.set is None):
        raise HTTPException(status_code=400, detail="Isi salah satu: add atau set.")
    if body.set is not None and not is_super:
        raise HTTPException(status_code=403, detail="Hanya Super Admin yang bisa menetapkan saldo.")
    target = admin_svc.get_admin_user(user_id)
    if not target:
        raise HTTPException(status_code=404, detail="Pengguna tidak ditemukan.")
    if not is_super:
        if user_id == actor["id"]:
            raise HTTPException(status_code=403, detail="Tidak bisa memberi token ke diri sendiri.")
        if target["is_admin"] or target["is_staff"]:
            raise HTTPException(
                status_code=403, detail="Admin biasa hanya bisa memberi token ke pengguna biasa."
            )
        if body.add and body.add > settings.staff_max_token_grant:
            cap = f"Rp{settings.staff_max_token_grant:,}".replace(",", ".")
            raise HTTPException(
                status_code=403,
                detail=f"Maksimal {cap} per pengisian saldo.",
            )
    if target["is_demo"]:
        raise HTTPException(status_code=400, detail="Akun demo sudah tak terbatas.")
    if body.add is not None:
        new_balance = admin_svc.add_tokens(user_id, body.add)
        detail = {"add": body.add, "balance_before": target["token_balance"]}
        action = "tokens.add"
        reward = billing_svc.on_topup(user_id, body.add)
        if reward:
            detail["referral_bonus"] = reward
            new_balance = (admin_svc.get_admin_user(user_id) or {}).get(
                "token_balance", new_balance
            )
    else:
        updated = admin_svc.update_user(user_id, {"token_balance": body.set})
        new_balance = updated["token_balance"] if updated else None
        detail = {"set": body.set, "balance_before": target["token_balance"]}
        action = "tokens.set"
    admin_svc.record_audit(actor, action, target, {**detail, "balance_after": new_balance})
    return {"ok": True, "user_id": user_id, "token_balance": new_balance}


@router.post("/admin/users/{user_id}/subscription")
def admin_subscription(user_id: int, body: AdminSubscriptionIn, request: Request) -> dict:
    """Aktifkan/perpanjang langganan setelah pembayaran dikonfirmasi (admin & super)."""
    actor = require_staff(request)
    target = admin_svc.get_admin_user(user_id)
    if not target:
        raise HTTPException(status_code=404, detail="Pengguna tidak ditemukan.")
    if target["is_demo"]:
        raise HTTPException(status_code=400, detail="Akun demo sudah tak terbatas.")
    if body.cancel:
        if not actor.get("is_admin"):
            raise HTTPException(status_code=403, detail="Hanya Super Admin yang bisa membatalkan.")
        billing_svc.cancel_subscription(user_id)
        admin_svc.record_audit(actor, "subscription.cancel", target)
        return {"ok": True, "user_id": user_id, "sub_until": None}
    days = body.days or billing_svc.packages()["subscription_days"]
    until = billing_svc.activate_subscription(user_id, days)
    detail: dict[str, Any] = {"days": days, "sub_until": until}
    reward = billing_svc.on_topup(user_id, billing_svc.packages()["subscription_price"])
    if reward:
        detail["referral_bonus"] = reward
    admin_svc.record_audit(actor, "subscription.activate", target, detail)
    return {"ok": True, "user_id": user_id, "sub_until": until}


@router.delete("/admin/users/{user_id}")
def admin_delete_user(user_id: int, request: Request) -> dict:
    admin = require_admin(request)
    if user_id == admin["id"]:
        raise HTTPException(status_code=400, detail="Tidak bisa menghapus diri sendiri.")
    target = admin_svc.get_admin_user(user_id)
    if not admin_svc.delete_user(user_id):
        raise HTTPException(status_code=404, detail="Pengguna tidak ditemukan.")
    admin_svc.record_audit(admin, "user.delete", target)
    return {"ok": True}


@router.get("/admin/users/{user_id}/history")
def admin_user_history(
    user_id: int, request: Request, tool: str | None = None, limit: int = 50
) -> dict:
    require_admin(request)
    if not admin_svc.get_admin_user(user_id):
        raise HTTPException(status_code=404, detail="Pengguna tidak ditemukan.")
    return {"items": svc.list_history(user_id, tool, min(limit, 100))}


@router.post("/admin/users/{user_id}/reset-password")
def admin_reset_user_password(user_id: int, request: Request) -> dict:
    admin = require_admin(request)
    target = admin_svc.get_admin_user(user_id)
    if not target:
        raise HTTPException(status_code=404, detail="Pengguna tidak ditemukan.")
    new_pw = svc.generate_password(12)
    svc.set_user_password(user_id, new_pw)
    admin_svc.record_audit(admin, "user.reset_password", target)
    return {"ok": True, "password": new_pw, "email": target.get("email")}


@router.get("/admin/audit")
def admin_audit(request: Request, limit: int = 100) -> dict:
    """Log tindakan admin (pemberian token, perubahan peran, dll). Hanya Super Admin."""
    require_admin(request)
    return {"items": admin_svc.list_audit(limit)}


@router.get("/admin/analytics")
def admin_analytics(request: Request, days: int = 14) -> dict:
    require_admin(request)
    return admin_svc.analytics_overview(days)


@router.get("/admin/activity")
def admin_activity(request: Request, limit: int = 50, tool: str | None = None) -> dict:
    require_admin(request)
    return {"items": admin_svc.recent_activity(limit, tool)}


@router.get("/admin/settings")
def admin_get_settings(request: Request) -> dict:
    require_admin(request)
    return admin_svc.get_all_settings()


@router.put("/admin/settings")
def admin_put_settings(body: AdminSettingsIn, request: Request) -> dict:
    require_admin(request)
    patch = body.model_dump(exclude_none=True)
    return {"ok": True, "settings": admin_svc.update_settings(patch)}
