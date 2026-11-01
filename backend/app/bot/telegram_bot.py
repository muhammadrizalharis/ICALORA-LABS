"""Bot Telegram ICALORA-LABS (long-polling, akses privat).

Menghubungkan Telegram ke backend lokal (:58010). Tidak membuka port publik:
bot menarik update via getUpdates. Akses dibatasi allowlist chat id
(TELEGRAM_ALLOWED_CHAT_IDS). Jika allowlist kosong, bot hanya membalas chat id
pemanggil agar bisa dikunci.

Perintah:
  /cek, /grammar, /parafrase, /humanize, /hitung  — fitur teks
  /status  — status korpus & ingest (admin)
  /backup  — jalankan backup DB ke Drive (admin)
  /start, /help, /whoami

Jalankan:
    python -m app.bot.telegram_bot
"""

from __future__ import annotations

import html
import subprocess
import time
from pathlib import Path

import httpx

from app.core.config import get_settings

settings = get_settings()
API = settings.backend_base_url.rstrip("/")
TG = f"https://api.telegram.org/bot{settings.telegram_bot_token}"
ROOT = Path(__file__).resolve().parents[3]

_HELP = (
    "<b>ICALORA-LABS Bot</b>\n"
    "Kirim perintah diikuti teks:\n"
    "/cek <teks> — cek kemiripan/plagiarisme\n"
    "/grammar <teks> — perbaiki tata bahasa\n"
    "/parafrase <teks> — parafrase\n"
    "/humanize <teks> — humanize teks AI\n"
    "/hitung <teks> — word count\n"
    "/status — status korpus &amp; ingest\n"
    "/backup — backup DB ke Drive\n"
    "/whoami — tampilkan chat id Anda"
)


def _allowed() -> set[int]:
    raw = settings.telegram_allowed_chat_ids.strip()
    return {int(x) for x in raw.split(",") if x.strip().isdigit()} if raw else set()


def _send(chat_id: int, text: str) -> None:
    try:
        httpx.post(
            f"{TG}/sendMessage",
            json={"chat_id": chat_id, "text": text, "parse_mode": "HTML"},
            timeout=30,
        )
    except Exception as exc:  # noqa: BLE001
        print(f"[bot] gagal kirim: {exc}", flush=True)


def _post(path: str, body: dict) -> dict:
    r = httpx.post(f"{API}{path}", json=body, timeout=180)
    r.raise_for_status()
    return r.json()


def _get(path: str) -> dict:
    r = httpx.get(f"{API}{path}", timeout=60)
    r.raise_for_status()
    return r.json()


def _fmt_plagiarism(d: dict) -> str:
    lines = [
        f"<b>Indeks Kemiripan (salinan):</b> {d['overall_similarity']}%",
        f"<b>Risiko Parafrase (semantik):</b> {d['paraphrase_similarity']}%",
        f"{d['word_count']} kata · {d['char_count']} karakter",
        "",
        "<b>Sumber teratas:</b>",
    ]
    for s in d["sources"][:5]:
        title = html.escape((s.get("title") or "(tanpa judul)")[:70])
        lines.append(f"• {s['similarity']}% — {title} [{s['source']}]")
    return "\n".join(lines)


def _status() -> str:
    d = _get("/ingest/status")
    parts = ["<b>Status korpus ICALORA</b>", f"Total dokumen: {d.get('total_documents', '?')}"]
    by_source = d.get("by_source", {})
    if isinstance(by_source, dict):
        for src, cnt in by_source.items():
            parts.append(f"• {src}: {cnt}")
    jobs = d.get("jobs", [])
    running = [j for j in jobs if j.get("status") == "running"]
    if running:
        parts.append("\n<b>Job ingest berjalan:</b>")
        for j in running[:6]:
            parts.append(f"• {j.get('source')} [{j.get('status')}] {j.get('docs_ingested')}")
    return "\n".join(parts)


def _run_backup() -> str:
    script = ROOT / "scripts" / "backup_to_drive.sh"
    try:
        subprocess.Popen(
            ["bash", str(script)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        return "Backup dijalankan di latar belakang. Cek /status atau log server."
    except Exception as exc:  # noqa: BLE001
        return f"Gagal memulai backup: {exc}"


def _handle(chat_id: int, text: str) -> None:
    text = text.strip()
    cmd, _, arg = text.partition(" ")
    cmd = cmd.lower().lstrip("/").split("@")[0]
    arg = arg.strip()

    if cmd in ("start", "help"):
        _send(chat_id, _HELP)
        return
    if cmd == "whoami":
        _send(chat_id, f"chat_id Anda: <code>{chat_id}</code>")
        return

    text_cmds = {
        "cek": ("/tools/plagiarism", _fmt_plagiarism),
        "grammar": ("/tools/grammar-check", lambda d: html.escape(d.get("corrected", ""))),
        "parafrase": ("/tools/paraphrase", lambda d: html.escape(d.get("result", ""))),
        "humanize": ("/tools/humanize", lambda d: html.escape(d.get("result", ""))),
        "hitung": (
            "/tools/word-count",
            lambda d: (
                f"{d.get('words')} kata · {d.get('characters')} karakter · "
                f"{d.get('sentences')} kalimat"
            ),
        ),
    }
    if cmd == "status":
        try:
            _send(chat_id, _status())
        except Exception as exc:  # noqa: BLE001
            _send(chat_id, f"Gagal ambil status: {html.escape(str(exc))}")
        return
    if cmd == "backup":
        _send(chat_id, _run_backup())
        return
    if cmd in text_cmds:
        if not arg:
            _send(chat_id, f"Format: /{cmd} &lt;teks&gt;")
            return
        path, fmt = text_cmds[cmd]
        try:
            body = {"text": arg}
            d = _post(path, body)
            _send(chat_id, fmt(d) or "(kosong)")
        except Exception as exc:  # noqa: BLE001
            _send(chat_id, f"Gagal memproses: {html.escape(str(exc))}")
        return

    _send(chat_id, "Perintah tidak dikenal. Ketik /help.")


def main() -> None:
    if not settings.telegram_bot_token:
        print("[bot] TELEGRAM_BOT_TOKEN kosong — berhenti.", flush=True)
        return
    allowed = _allowed()
    print(f"[bot] mulai. allowlist={allowed or 'KOSONG (mode kunci)'}", flush=True)
    offset = None
    while True:
        try:
            params = {"timeout": 30}
            if offset is not None:
                params["offset"] = offset
            r = httpx.get(f"{TG}/getUpdates", params=params, timeout=40)
            updates = r.json().get("result", [])
        except Exception as exc:  # noqa: BLE001
            print(f"[bot] getUpdates error: {exc}", flush=True)
            time.sleep(5)
            continue
        for upd in updates:
            offset = upd["update_id"] + 1
            msg = upd.get("message") or upd.get("edited_message")
            if not msg:
                continue
            chat_id = msg["chat"]["id"]
            text = msg.get("text", "")
            if not text:
                continue
            if allowed and chat_id not in allowed:
                _send(chat_id, "Akses ditolak (bot privat).")
                continue
            if not allowed:
                _send(
                    chat_id,
                    "Bot belum dikunci. chat_id Anda: "
                    f"<code>{chat_id}</code>\nTambahkan ke TELEGRAM_ALLOWED_CHAT_IDS.",
                )
                _handle(chat_id, text)
                continue
            _handle(chat_id, text)


if __name__ == "__main__":
    main()
