# Deploy ICALORA-LABS dengan Docker (stack aplikasi)

Stack **aplikasi** (backend FastAPI, bot Telegram, frontend Next.js) kini bisa
dijalankan dalam container, jadi maintenance cukup satu perintah.

> Infra (Redis, SeaweedFS) tetap di `infra/docker-compose.infra.yml`.
> Postgres korpus berada di VM storage terpisah (lihat catatan di `infra/`).

## Prasyarat
- Docker + Docker Compose plugin
- Berkas rahasia `backend/.env` sudah terisi (tidak di-commit)
- Infra sudah jalan (Redis/SeaweedFS) dan Ollama aktif di host

## Menjalankan

```bash
cd deploy/docker

# Hentikan service systemd lama agar port 58010/58030 tidak bentrok
systemctl --user stop icalora-backend icalora-bot icalora-frontend

# Build + jalankan
docker compose -f docker-compose.app.yml up -d --build
```

Cek status & kesehatan:

```bash
docker compose -f docker-compose.app.yml ps
curl -fsS http://127.0.0.1:58010/health
curl -fsS http://127.0.0.1:58030/
```

## Kenapa `network_mode: host`?
Backend terhubung ke banyak layanan via `127.0.0.1` (Postgres remote via IP-nya,
Redis, SeaweedFS/S3, Ollama). Dengan host network, seluruh referensi di
`backend/.env` bekerja apa adanya tanpa perubahan konfigurasi.

## Perintah umum
```bash
docker compose -f docker-compose.app.yml logs -f backend   # ikuti log
docker compose -f docker-compose.app.yml restart frontend  # restart satu service
docker compose -f docker-compose.app.yml down              # hentikan semua
docker compose -f docker-compose.app.yml up -d --build      # rebuild setelah update kode
```

## Kembali ke systemd (rollback)
```bash
docker compose -f docker-compose.app.yml down
systemctl --user start icalora-backend icalora-bot icalora-frontend
```

## Hemat disk (opsional)
Setelah yakin Docker stabil, salinan native lama bisa dibuang:
- `backend/.venv/` (~950 MB) dan `frontend/node_modules/` (~690 MB)
Bersihkan cache build Docker: `docker image prune` / `docker builder prune`.
