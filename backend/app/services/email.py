"""Pengiriman email via SMTP (stdlib). Dipakai untuk mengirim kata sandi baru
ke pengguna. Aman gagal: pemanggil menangani bila SMTP belum dikonfigurasi."""

from __future__ import annotations

import smtplib
import ssl
from email.message import EmailMessage
from email.utils import formataddr

from app.core.config import get_settings

settings = get_settings()


def smtp_configured() -> bool:
    return bool(settings.smtp_host and settings.smtp_user and settings.smtp_password)


def _from_header() -> str:
    if settings.smtp_from:
        return settings.smtp_from
    return formataddr(("ICALORA-LABS", settings.smtp_user))


def send_email(to: str, subject: str, text_body: str, html_body: str | None = None) -> None:
    """Kirim email. Melempar exception bila gagal (pemanggil menangani)."""
    if not smtp_configured():
        raise RuntimeError("SMTP belum dikonfigurasi.")
    msg = EmailMessage()
    msg["From"] = _from_header()
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(text_body)
    if html_body:
        msg.add_alternative(html_body, subtype="html")

    ctx = ssl.create_default_context()
    if settings.smtp_port == 465:
        with smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port, context=ctx, timeout=20) as s:
            s.login(settings.smtp_user, settings.smtp_password)
            s.send_message(msg)
    else:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=20) as s:
            s.ehlo()
            s.starttls(context=ctx)
            s.ehlo()
            s.login(settings.smtp_user, settings.smtp_password)
            s.send_message(msg)


def send_new_password(to: str, name: str | None, password: str) -> None:
    """Kirim kata sandi baru ke pengguna dengan isi ramah."""
    greet = name or "Pengguna"
    text_body = (
        f"Halo {greet},\n\n"
        "Kata sandi baru untuk akun ICALORA-LABS Anda telah dibuat:\n\n"
        f"    {password}\n\n"
        "Gunakan email dan kata sandi ini untuk masuk. Demi keamanan, jangan "
        "bagikan kata sandi ini kepada siapa pun. Anda dapat membuat kata sandi "
        "baru kapan saja dari halaman Akun.\n\n"
        "— Tim ICALORA-LABS"
    )
    html_body = (
        f"<p>Halo {greet},</p>"
        "<p>Kata sandi baru untuk akun <b>ICALORA-LABS</b> Anda telah dibuat:</p>"
        f'<p style="font-size:18px;font-weight:700;letter-spacing:1px;'
        f'background:#f4f4f5;padding:12px 16px;border-radius:8px;display:inline-block">'
        f"{password}</p>"
        "<p>Gunakan email dan kata sandi ini untuk masuk. Demi keamanan, jangan "
        "bagikan kata sandi ini kepada siapa pun. Anda dapat membuat kata sandi "
        "baru kapan saja dari halaman Akun.</p>"
        "<p>— Tim ICALORA-LABS</p>"
    )
    send_email(to, "Kata Sandi Baru ICALORA-LABS", text_body, html_body)
