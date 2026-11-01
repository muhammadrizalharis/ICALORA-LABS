# Deploy ICALORA-LABS (layanan 24/7)

Backend dan frontend berjalan sebagai **systemd user services** dengan
`Restart=always` dan **lingering aktif**, sehingga tetap hidup 24/7 dan otomatis
pulih bila crash atau server reboot. Semua port terikat ke `127.0.0.1`.

| Layanan | Port | Unit |
|--------|------|------|
| Backend (FastAPI) | `127.0.0.1:58010` | `icalora-backend.service` |
| Frontend (Next.js) | `127.0.0.1:58030` | `icalora-frontend.service` |
| Bot Telegram (privat) | — (long-polling) | `icalora-bot.service` |
| Ingest OpenAlex | — | `icalora-ingest-openalex.service` |
| Ingest PMC | — | `icalora-ingest-pmc.service` |
| Embedder GPU | — | `icalora-ingest-embed.service` |

Pekerja ingest bersifat **resumable** (menyimpan cursor di `ingest_jobs`), aman
di-`restart`/`stop`; akan melanjutkan dari posisi terakhir. Semua dikontrol juga
lewat bot Telegram (`/ingest <secret> <sumber> <aksi>`).

## Pasang / perbarui

```bash
cp deploy/systemd/*.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now icalora-backend.service icalora-frontend.service \
  icalora-bot.service icalora-ingest-openalex.service \
  icalora-ingest-pmc.service icalora-ingest-embed.service
loginctl enable-linger "$USER"   # agar tetap jalan walau tidak login
```

## Operasional

```bash
systemctl --user status  icalora-backend icalora-frontend
systemctl --user restart icalora-frontend          # setelah `npm run build`
journalctl --user -u icalora-backend -f            # atau lihat backend/.logs/service_*.log
```

Setelah mengubah frontend: `cd frontend && npm run build && systemctl --user restart icalora-frontend`.

## Catatan port

Port di-forward otomatis oleh VS Code (listening di `127.0.0.1`). Label panel
PORTS diatur via `remote.portsAttributes` di settings VS Code
(ICALORA API = 58010, ICALORA WEB = 58030).
