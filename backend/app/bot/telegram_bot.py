"""Bot Telegram ICALORA-LABS (long-polling, akses privat).

Menghubungkan Telegram ke backend lokal (:58010). Tidak membuka port publik:
bot menarik update via getUpdates. Akses dibatasi allowlist chat id
(TELEGRAM_ALLOWED_CHAT_IDS). Jika allowlist kosong, bot hanya membalas chat id
pemanggil agar bisa dikunci.

Perintah:
  /cek, /grammar, /parafrase, /humanize, /hitung  — fitur teks
  /status  — status lengkap (API, infra, web-search, korpus)
  /ping    — cek bot & backend hidup
  /services, /restart, /logs, /ingest, /backup  — admin (wajib secret)
  /start, /help, /whoami

Jalankan:
    python -m app.bot.telegram_bot
"""

from __future__ import annotations

import html
import os
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
    "<b>ICALORA-LABS Bot</b>\n\n"
    "<b>Fitur teks:</b>\n"
    "/cek &lt;teks&gt; — cek kemiripan/plagiarisme\n"
    "/grammar &lt;teks&gt; — perbaiki tata bahasa\n"
    "/parafrase &lt;teks&gt; — parafrase\n"
    "/humanize &lt;teks&gt; — humanize teks AI\n"
    "/hitung &lt;teks&gt; — word count\n"
    "/status — status lengkap (API, DB, web-search, korpus)\n"
    "/ping — cek bot &amp; backend hidup\n"
    "/whoami — chat id Anda\n\n"
    "<b>Admin (wajib secret):</b>\n"
    "/backup &lt;secret&gt; — backup DB ke Drive\n"
    "/services &lt;secret&gt; — status semua layanan\n"
    "/restart &lt;secret&gt; &lt;layanan&gt; — restart layanan\n"
    "/ingest &lt;secret&gt; &lt;openalex|pmc|embed&gt; &lt;start|stop|restart|status&gt;\n"
    "/logs &lt;secret&gt; &lt;layanan&gt; — 20 baris log terakhir\n\n"
    "layanan: backend, frontend, bot, redis, storage, all"
)

# Nama ramah -> kontainer Docker (deploy utama). Fallback systemd memakai nama
# unit yang sama (icalora-backend.service, dst.) bila Docker tak tersedia.
_UNITS = {
    "backend": "icalora-backend",
    "frontend": "icalora-frontend",
    "bot": "icalora-bot",
    "redis": "icalora-redis",
    "storage": "icalora-seaweedfs",
}
# Unit ingest (korpus) — berjalan sebagai systemd one-shot di host, bukan kontainer.
_INGEST_UNITS = {
    "openalex": "icalora-ingest-openalex",
    "pmc": "icalora-ingest-pmc",
    "embed": "icalora-ingest-embed",
}
_LOG_FILES = {
    "backend": "service_backend.log",
    "frontend": "service_frontend.log",
    "bot": "service_bot.log",
    "openalex": "ingest_openalex.log",
    "pmc": "ingest_pmc.log",
    "embed": "ingest_embed.log",
}
_LOGDIR = ROOT / "backend" / ".logs"
_DOCKER_SOCK = "/var/run/docker.sock"


def _allowed() -> set[int]:
    raw = settings.telegram_allowed_chat_ids.strip()
    return {int(x) for x in raw.split(",") if x.strip().isdigit()} if raw else set()


def _send(chat_id: int, text: str) -> None:
    try:
        r = httpx.post(
            f"{TG}/sendMessage",
            json={"chat_id": chat_id, "text": text, "parse_mode": "HTML"},
            timeout=30,
        )
        if r.status_code == 400:
            # HTML gagal di-parse → kirim ulang sebagai teks biasa
            httpx.post(
                f"{TG}/sendMessage",
                json={"chat_id": chat_id, "text": text},
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


def _mark(ok: bool) -> str:
    return "✅" if ok else "❌"


def _status() -> str:
    """Status menyeluruh: API, infrastruktur, web-search (kuota), korpus & ingest."""
    try:
        d = _get("/health/status")
    except Exception as exc:  # noqa: BLE001
        return f"❌ <b>Backend tak terjangkau</b>\n<code>{html.escape(str(exc))}</code>"

    overall_ok = d.get("status") == "ok"
    out = [
        f"{_mark(overall_ok)} <b>Status ICALORA-LABS</b> — "
        f"<code>{html.escape(str(d.get('status', '?')))}</code>",
        "",
        "<b>🔌 API &amp; Infrastruktur</b>",
    ]

    infra = d.get("infra", {}).get("services", {})

    pg = infra.get("postgres", {})
    out.append(
        f"{_mark(pg.get('ok'))} PostgreSQL"
        + (f" · pgvector {'aktif' if pg.get('pgvector') else 'nonaktif'}" if pg.get("ok") else "")
        + (f" · <code>{html.escape(str(pg.get('error'))[:60])}</code>" if pg.get("error") else "")
    )

    rd = infra.get("redis", {})
    out.append(
        f"{_mark(rd.get('ok'))} Redis"
        + (f" · <code>{html.escape(str(rd.get('error'))[:60])}</code>" if rd.get("error") else "")
    )

    s3 = infra.get("s3", {})
    buckets = s3.get("buckets") or []
    out.append(
        f"{_mark(s3.get('ok'))} Object storage (S3)"
        + (f" · {len(buckets)} bucket" if s3.get("ok") else "")
        + (f" · <code>{html.escape(str(s3.get('error'))[:60])}</code>" if s3.get("error") else "")
    )

    llm = infra.get("llm", {})
    out.append(
        f"{_mark(llm.get('ok'))} LLM ({html.escape(str(llm.get('provider', '?')))})"
        + (
            f" · model <code>{html.escape(str(llm.get('model', '?')))}</code>"
            f" {'tersedia' if llm.get('model_available') else 'BELUM diunduh'}"
            if llm.get("ok")
            else ""
        )
        + (f" · <code>{html.escape(str(llm.get('error'))[:60])}</code>" if llm.get("error") else "")
    )

    # ---- Web-search (verifikasi daring) ----
    ws = d.get("websearch", {})
    out.append("")
    out.append("<b>🌐 Web-search daring (verifikasi)</b>")
    if not ws.get("enabled"):
        out.append("⚪ Dinonaktifkan (ONLINE_WEBSEARCH_ENABLED=false)")
    elif not ws.get("provider"):
        out.append("⚠️ Tak ada penyedia terpasang (Tavily/Brave key kosong)")
    else:
        used = ws.get("used", -1)
        cap = ws.get("cap", 0)
        remaining = ws.get("remaining")
        prov = str(ws.get("provider", "?")).capitalize()
        if used == -1:
            quota_ok = False
            quota_txt = "kuota tak terbaca (Redis?)"
        else:
            quota_ok = remaining is None or remaining > 0
            pct = f" ({used * 100 // cap}%)" if cap else ""
            rem_txt = f" · sisa {remaining}" if remaining is not None else ""
            quota_txt = f"{used}/{cap}{pct}{rem_txt} — bulan {ws.get('month', '?')}"
        out.append(f"{_mark(bool(ws.get('provider')))} Penyedia aktif: <b>{prov}</b>")
        tav = ws.get("providers_configured", {}).get("tavily")
        brv = ws.get("providers_configured", {}).get("brave")
        out.append(f"   Kunci: Tavily {_mark(tav)} · Brave {_mark(brv)}")
        out.append(f"{_mark(quota_ok)} Kuota: {quota_txt}")
        out.append(
            f"   Tuning: {ws.get('sentences_per_paper', '?')} kalimat/paper · "
            f"{ws.get('results_per_sentence', '?')} hasil/kalimat"
        )

    # ---- Korpus & ingest ----
    corpus = d.get("corpus", {})
    out.append("")
    out.append("<b>📚 Korpus &amp; ingest</b>")
    if corpus.get("error"):
        out.append(f"❌ <code>{html.escape(str(corpus['error'])[:80])}</code>")
    else:
        out.append(f"Total dokumen: <b>{corpus.get('total_documents', '?')}</b>")
        by_source = corpus.get("by_source", {})
        if isinstance(by_source, dict) and by_source:
            for src, cnt in sorted(by_source.items(), key=lambda kv: -int(kv[1] or 0)):
                out.append(f"• {html.escape(str(src))}: {cnt}")
        jobs = corpus.get("jobs", [])
        running = [j for j in jobs if j.get("status") == "running"]
        if running:
            out.append("<b>Job ingest berjalan:</b>")
            for j in running[:6]:
                out.append(
                    f"🔄 {html.escape(str(j.get('source')))} · "
                    f"{j.get('docs_ingested')}/{j.get('docs_target') or '?'}"
                )
        else:
            out.append("Tidak ada job ingest berjalan.")
        errored = [j for j in jobs if j.get("status") == "error" and j.get("last_error")]
        if errored:
            j = errored[0]
            out.append(
                f"⚠️ Error terbaru ({html.escape(str(j.get('source')))}): "
                f"<code>{html.escape(str(j.get('last_error'))[:80])}</code>"
            )

    return "\n".join(out)


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


def _systemctl(*args: str) -> str:
    try:
        res = subprocess.run(
            ["systemctl", "--user", *args],
            capture_output=True,
            text=True,
            timeout=30,
        )
        out = (res.stdout or "") + (res.stderr or "")
        return out.strip() or "(tidak ada output)"
    except Exception as exc:  # noqa: BLE001
        return f"Gagal systemctl: {exc}"


def _docker_available() -> bool:
    return os.path.exists(_DOCKER_SOCK)


def _docker_api(method: str, path: str, *, stream: bool = False):
    """Panggil Docker Engine API lewat unix socket (tanpa perlu CLI docker)."""
    transport = httpx.HTTPTransport(uds=_DOCKER_SOCK)
    with httpx.Client(transport=transport, base_url="http://docker", timeout=30) as client:
        r = client.request(method, path)
        r.raise_for_status()
        return r.content if stream else r


def _docker_list() -> dict[str, dict]:
    """Peta nama kontainer -> {state, status} untuk semua kontainer ICALORA."""
    out: dict[str, dict] = {}
    try:
        r = _docker_api("GET", "/containers/json?all=1")
        for c in r.json():
            for raw in c.get("Names", []):
                name = raw.lstrip("/")
                out[name] = {"state": c.get("State", "?"), "status": c.get("Status", "")}
    except Exception as exc:  # noqa: BLE001
        out["_error"] = {"state": "error", "status": str(exc)}
    return out


def _services_status() -> str:
    lines = ["<b>Status layanan:</b>"]
    if _docker_available():
        info = _docker_list()
        if "_error" in info:
            err = html.escape(info["_error"]["status"][:80])
            lines.append(f"❌ Docker API error: <code>{err}</code>")
            return "\n".join(lines)
        for name, cname in _UNITS.items():
            c = info.get(cname)
            if not c:
                lines.append(f"⚪ {name}: <code>tidak ada</code>")
                continue
            running = c["state"] == "running"
            healthy = "unhealthy" not in c["status"]
            mark = "✅" if (running and healthy) else ("⚠️" if running else "❌")
            lines.append(f"{mark} {name}: <code>{html.escape(c['status'] or c['state'])}</code>")
        return "\n".join(lines)
    # Fallback systemd (deploy host)
    for name, unit in {**_UNITS, **_INGEST_UNITS}.items():
        state = _systemctl("is-active", unit).splitlines()[0] if unit else "?"
        mark = "✅" if state == "active" else "⚠️"
        lines.append(f"{mark} {name}: <code>{state}</code>")
    return "\n".join(lines)


def _restart_service(name: str) -> str:
    name = name.lower().strip()
    if name == "all":
        targets = list(_UNITS.keys())
    elif name in _UNITS:
        targets = [name]
    else:
        return f"Layanan tidak dikenal: {html.escape(name)}"
    # restart bot terakhir supaya balasan sempat terkirim
    targets.sort(key=lambda n: n == "bot")
    if _docker_available():
        done, failed = [], []
        for n in targets:
            try:
                _docker_api("POST", f"/containers/{_UNITS[n]}/restart?t=10")
                done.append(n)
            except Exception as exc:  # noqa: BLE001
                failed.append(f"{n} ({str(exc)[:40]})")
        msg = f"Restart terkirim: {', '.join(done)}" if done else "Tidak ada yang direstart."
        if failed:
            msg += f"\n⚠️ Gagal: {html.escape(', '.join(failed))}"
        return msg
    units = [_UNITS[n] for n in targets]
    _systemctl("restart", *units)
    return f"Restart dikirim: {html.escape(name)}"


def _ingest_control(source: str, action: str) -> str:
    source = source.lower().strip()
    action = action.lower().strip()
    if source not in _INGEST_UNITS:
        return f"Sumber tidak dikenal: {html.escape(source)}"
    if action not in ("start", "stop", "restart", "status"):
        return f"Aksi tidak dikenal: {html.escape(action)}"
    unit = _INGEST_UNITS[source]
    if action == "status":
        return f"{source}: <code>{_systemctl('is-active', unit).splitlines()[0]}</code>"
    out = _systemctl(action, unit)
    if out.startswith("Gagal"):
        return (
            f"ingest {source}: {action} GAGAL (systemd tak tersedia). "
            "Ingest korpus dijalankan sebagai job host, bukan kontainer."
        )
    return f"ingest {source}: {action} dikirim."


def _demux_docker_logs(data: bytes) -> str:
    """Docker non-TTY logs memakai framing 8-byte header. Buang header, ambil payload."""
    out = bytearray()
    i, n = 0, len(data)
    while i + 8 <= n:
        size = int.from_bytes(data[i + 4 : i + 8], "big")
        i += 8
        out += data[i : i + size]
        i += size
    return out.decode("utf-8", "replace") if out else data.decode("utf-8", "replace")


def _tail_log(name: str, lines: int = 20) -> str:
    name = name.lower().strip()
    if _docker_available() and name in _UNITS:
        try:
            raw = _docker_api(
                "GET",
                f"/containers/{_UNITS[name]}/logs?stdout=1&stderr=1&tail={lines}",
                stream=True,
            )
            text = _demux_docker_logs(raw).strip() or "(log kosong)"
            text = text[-3500:]
            return f"<b>{name} (akhir {lines} baris):</b>\n<pre>{html.escape(text)}</pre>"
        except Exception as exc:  # noqa: BLE001
            return f"Gagal baca log docker: {html.escape(str(exc))}"
    # Fallback file log (deploy host)
    fname = _LOG_FILES.get(name)
    if not fname:
        return f"Layanan tidak dikenal: {html.escape(name)}"
    path = _LOGDIR / fname
    if not path.exists():
        return f"Log belum ada: {fname}"
    try:
        with path.open("rb") as fh:
            data = fh.readlines()[-lines:]
        text = b"".join(data).decode("utf-8", "replace")
        return f"<b>{name} (akhir {lines} baris):</b>\n<pre>{html.escape(text)}</pre>"
    except Exception as exc:  # noqa: BLE001
        return f"Gagal baca log: {html.escape(str(exc))}"


def _check_secret(arg: str) -> tuple[bool, str]:
    """Pisahkan secret (token pertama) dari sisa argumen."""
    secret, _, rest = arg.partition(" ")
    expected = settings.telegram_bot_secret or ""
    if not expected:
        return False, "Secret admin belum dikonfigurasi di server."
    if secret != expected:
        return False, "Secret salah atau kosong. Format: /perintah &lt;secret&gt; ..."
    return True, rest.strip()


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
    if cmd == "ping":
        t0 = time.monotonic()
        try:
            _get("/health")
            dt = int((time.monotonic() - t0) * 1000)
            _send(chat_id, f"🏓 Pong! Bot ✅ · Backend ✅ ({dt} ms)")
        except Exception as exc:  # noqa: BLE001
            err = html.escape(str(exc)[:80])
            _send(chat_id, f"🏓 Pong! Bot ✅ · Backend ❌\n<code>{err}</code>")
        return

    # ---- Perintah admin (wajib secret) ----
    admin_cmds = {"backup", "services", "restart", "ingest", "logs"}
    if cmd in admin_cmds:
        ok, rest = _check_secret(arg)
        if not ok:
            _send(chat_id, rest)
            return
        if cmd == "backup":
            _send(chat_id, _run_backup())
        elif cmd == "services":
            _send(chat_id, _services_status())
        elif cmd == "restart":
            if not rest:
                _send(chat_id, "Format: /restart &lt;secret&gt; &lt;layanan&gt;")
            else:
                _send(chat_id, _restart_service(rest.split()[0]))
        elif cmd == "ingest":
            parts = rest.split()
            if len(parts) < 2:
                _send(chat_id, "Format: /ingest &lt;secret&gt; &lt;sumber&gt; &lt;aksi&gt;")
            else:
                _send(chat_id, _ingest_control(parts[0], parts[1]))
        elif cmd == "logs":
            if not rest:
                _send(chat_id, "Format: /logs &lt;secret&gt; &lt;layanan&gt;")
            else:
                _send(chat_id, _tail_log(rest.split()[0]))
        return

    if cmd == "status":
        try:
            _send(chat_id, _status())
        except Exception as exc:  # noqa: BLE001
            _send(chat_id, f"Gagal ambil status: {html.escape(str(exc))}")
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
