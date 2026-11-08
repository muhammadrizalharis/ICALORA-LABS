"""Endpoint autentikasi, sesi, profil, dan riwayat (history) pengguna."""

from __future__ import annotations

import secrets
import urllib.parse

import httpx
from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response
from fastapi.responses import RedirectResponse

from app.core.config import get_settings
from app.services import auth as svc

settings = get_settings()
router = APIRouter(prefix="/auth", tags=["auth"])

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
    return user


def optional_user(request: Request) -> dict | None:
    token = request.cookies.get(settings.session_cookie)
    uid = svc.verify_session_token(token)
    return svc.get_user(uid) if uid else None


@router.get("/me")
def me(request: Request) -> dict:
    user = optional_user(request)
    return {
        "authenticated": user is not None,
        "user": user,
        "google_enabled": bool(settings.google_client_id and settings.google_client_secret),
        "demo_enabled": settings.allow_demo_login,
        "history_retention_days": settings.history_retention_days,
    }


@router.post("/demo-login")
def demo_login(response: Response) -> dict:
    if not settings.allow_demo_login:
        raise HTTPException(status_code=403, detail="Demo login dinonaktifkan.")
    user = svc.create_demo_user()
    _set_session(response, user["id"])
    return {"ok": True, "user": user}


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

    user = svc.upsert_google_user(
        sub=data["sub"],
        email=data.get("email", ""),
        name=data.get("name", ""),
        picture=data.get("picture", ""),
    )
    resp = RedirectResponse(f"{settings.frontend_base_url}/dashboard")
    _set_session(resp, user["id"])
    resp.delete_cookie("oauth_state", path="/")
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
