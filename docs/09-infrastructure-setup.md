# 09 — Infrastruktur & Keamanan (Server Development)

Dokumen ini mencatat infrastruktur data yang berjalan di server untuk ICALORA-LABS
(by MRH INNOVEX) beserta tooling keamanan. Semua self-contained, hanya memakai
port khusus ICALORA-LABS, dan **tidak pernah** menyentuh port/proses milik proyek lain.

## 1. Layanan infrastruktur (Docker Compose)

Definisi: [`infra/docker-compose.infra.yml`](../infra/docker-compose.infra.yml)
Project name Compose: `icalora-infra` (terisolasi dari stack lain).

| Layanan | Image (di-pin) | Fungsi | Port host (127.0.0.1 saja) |
|---------|----------------|--------|----------------------------|
| PostgreSQL + pgvector | `pgvector/pgvector:pg16` | Database utama + vektor embedding | `54432` → 5432 |
| Redis | `redis:7.4-alpine` | Cache, queue, rate-limit | `54379` → 6379 |
| SeaweedFS | `chrislusf/seaweedfs` (by digest SHA256) | Object storage S3-compatible (dokumen & korpus) | `54333` → 8333 (S3), `54888` → 8888 (filer) |

> Catatan: MinIO sebelumnya dipertimbangkan, namun image-nya kini di-gate login
> (pull access denied di Docker Hub & quay.io). Diganti **SeaweedFS** yang
> sepenuhnya open-source dan S3-compatible.

### Pengerasan (hardening) yang diterapkan
- **Bind hanya ke `127.0.0.1`** — tidak ada port yang terbuka ke jaringan luar.
- **`security_opt: no-new-privileges:true`** pada semua layanan.
- **Image di-pin** — Postgres/Redis by tag versi, SeaweedFS by digest SHA256 (reproducible & anti-supply-chain).
- **Healthcheck** pada tiap layanan (Postgres `pg_isready`, Redis `redis-cli ping`, SeaweedFS `GET /cluster/healthz`).
- **Batas resource** (`mem_limit`, `cpus`) untuk cegah noisy-neighbor.
- **`restart: unless-stopped`** agar otomatis pulih.
- **Secret tidak di-commit** — lihat bagian 3.

## 2. Cara menjalankan

```bash
cd infra
cp .env.example .env                       # isi password/secret kuat Anda sendiri
cp seaweedfs/s3.json.example seaweedfs/s3.json   # samakan secretKey dgn S3_SECRET_KEY di .env
chmod 600 .env
# s3.json harus 644 (dibaca proses S3 di container), tapi folder induk dikunci 700:
chmod 644 seaweedfs/s3.json
chmod 700 seaweedfs

docker compose -f docker-compose.infra.yml up -d
docker compose -f docker-compose.infra.yml ps     # semua harus (healthy)
```

> **Kenapa `s3.json` 644 bukan 600?** Proses S3 SeaweedFS menolak membaca file
> mode 600 di dalam container (walau root) karena pembatasan privilege/AppArmor.
> Solusi aman: file `644` (hanya bisa dibaca di dalam container), namun **folder
> induk `seaweedfs/` dikunci `700`** sehingga user lain di host tetap tidak bisa
> membaca isinya. Untuk produksi, gunakan Docker/Kubernetes secrets.

## 3. Manajemen secret (repo PUBLIK — wajib hati-hati)

File rahasia **tidak pernah** masuk git (diblokir [`.gitignore`](../.gitignore)):
- `infra/.env` (password DB/Redis, secret S3) — mode `600`
- `infra/seaweedfs/s3.json` (kredensial S3) — mode `644`, folder induk `700`

Yang **di-track** (template aman, tanpa nilai asli):
- `infra/.env.example`
- `infra/seaweedfs/s3.json.example`

> Pola `.gitignore` memakai `**/seaweedfs/s3.json` (bukan `seaweedfs/s3.json`)
> karena pola dengan `/` di tengah ter-anchor ke root repo dan takkan cocok dengan
> path `infra/seaweedfs/s3.json`.

## 4. Tooling keamanan (di `~/.icalora-tools/`, bukan di repo)

| Alat | Versi | Fungsi |
|------|-------|--------|
| gitleaks | 8.30.1 | Deteksi secret di git/filesystem |
| trivy | 0.76.1 | Scan kerentanan image & dependency |
| detect-secrets | 1.5.0 | Scan secret (venv) |
| bandit | 1.9.4 | Analisis statis keamanan Python |
| pip-audit | 2.10.1 | Audit kerentanan paket Python |

Semua binary diverifikasi checksum saat diunduh. Jalankan scan secret sebelum commit:

```bash
~/.icalora-tools/bin/gitleaks detect --source . --no-banner
~/.icalora-tools/secvenv/bin/detect-secrets scan
```

## 5. Prinsip tetap

- **Hanya port khusus ICALORA-LABS** (54432/54379/54333/54888); tidak pernah menyentuh port/proses user atau proyek lain.
- **Self-contained** — tidak mengambil sumber daya dari proyek lain di server.
- **Legal** — korpus hanya dari sumber open-access berlisensi (lihat [docs/03](03-data-strategy.md) & [docs/06](06-legal-compliance.md)).
- **Setiap perubahan langsung di-commit & push** ke repo publik.
