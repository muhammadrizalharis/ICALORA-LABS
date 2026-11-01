# ICALORA-LABS — AI Academic Integrity Toolkit

> **Web / Produk:** ICALORA-LABS &nbsp;·&nbsp; **Perusahaan:** MRH INNOVEX
> *"ICALORA-LABS — Where scholarship meets truth."*

Platform AI akademik serba-bisa: **plagiarism checker, AI detector, paraphraser, humanizer, grammar checker, citation finder, AI grader**, dan lainnya — alternatif yang lebih terjangkau untuk Turnitin & sejenisnya, dibangun **mandiri** dengan **korpus & sumber daya milik sendiri** dari sumber **open-access yang legal**.

---

## 📁 Struktur Dokumen Rencana

| File | Isi |
|---|---|
| [README.md](./README.md) | Ringkasan proyek (file ini) |
| [docs/01-features.md](./docs/01-features.md) | Peta 13 fitur + tingkat kesulitan |
| [docs/02-architecture.md](./docs/02-architecture.md) | Arsitektur teknis sistem |
| [docs/03-data-strategy.md](./docs/03-data-strategy.md) | Strategi membangun korpus & dataset sendiri |
| [docs/04-roadmap.md](./docs/04-roadmap.md) | Tahapan pembangunan (5 fase) |
| [docs/05-tech-stack.md](./docs/05-tech-stack.md) | Pilihan teknologi & struktur folder |
| [docs/06-legal-compliance.md](./docs/06-legal-compliance.md) | Legalitas, lisensi, & kepatuhan |
| [docs/07-branding.md](./docs/07-branding.md) | Nama, domain, & identitas brand |
| [docs/08-database-security.md](./docs/08-database-security.md) | Database, keamanan, backend, frontend |
| [docs/09-infrastructure-setup.md](./docs/09-infrastructure-setup.md) | Infrastruktur data & tooling keamanan |
| [docs/10-storage-optimization.md](./docs/10-storage-optimization.md) | Strategi penyimpanan korpus hemat |
| [docs/11-report-viewer-spec.md](./docs/11-report-viewer-spec.md) | Spesifikasi report viewer (similarity/writing/AI) |

---

## 🎯 Ringkasan Keputusan

| Aspek | Keputusan |
|---|---|
| **Nama web / produk** | ICALORA-LABS |
| **Nama perusahaan** | MRH INNOVEX |
| **Domain utama** | `icaloralabs.com` / `icaloralabs.ai` (web/produk) + `mrhinnovex.com` (perusahaan) — *semua masih bebas, segera amankan* |
| **Pendekatan data** | Mandiri (self-contained), korpus dari sumber open-access legal |
| **Legalitas** | Hanya sumber berlisensi reuse (OpenAlex, PMC OA, DOAJ, CORE) — **tanpa scraping konten berbayar** |
| **Target** | Mahasiswa, dosen, peneliti, institusi |

---

## ⚡ Status

- [x] Riset nama & branding
- [x] Rencana fitur, arsitektur, data, roadmap, stack, legal
- [x] Infrastruktur data (Postgres+pgvector, Redis, SeaweedFS) + tooling keamanan
- [x] **Fase 0** — scaffold monorepo (backend FastAPI + frontend Next.js), terhubung ke infra
- [ ] Fase 1 — 9 fitur ringan (LLM)
- [ ] Pengumpulan korpus
- [ ] Fitur berat (plagiarism, detector)

---

## ▶️ Menjalankan Secara Lokal (Fase 0)

**Prasyarat:** Docker, Node 20+, Python 3.10+.

1. **Infrastruktur** (Postgres/Redis/SeaweedFS):
   ```bash
   cd infra
   cp .env.example .env && cp seaweedfs/s3.json.example seaweedfs/s3.json
   # isi secret kuat Anda sendiri; samakan S3_SECRET_KEY dengan s3.json
   chmod 600 .env && chmod 644 seaweedfs/s3.json && chmod 700 seaweedfs
   docker compose -f docker-compose.infra.yml up -d
   ```
   Detail & hardening: [docs/09](./docs/09-infrastructure-setup.md).

2. **Backend** (FastAPI, default port 58010):
   ```bash
   cd backend
   python3 -m venv .venv && . .venv/bin/activate
   pip install -e ".[dev]"
   cp .env.example .env   # samakan nilai dengan infra/.env
   uvicorn app.main:app --host 127.0.0.1 --port 58010
   # cek koneksi infra: curl http://127.0.0.1:58010/health/infra
   ```

3. **Frontend** (Next.js, port 3000):
   ```bash
   cd frontend
   cp .env.example .env.local
   npm install && npm run dev
   ```

> Semua port ICALORA-LABS khusus (54432/54379/54333/54888 infra, 58010 API) dan hanya
> mengikat `127.0.0.1`. **Tidak pernah** memakai port/proses proyek lain.

---

## 🚦 Prinsip Utama

1. **Legal-first** — hanya memakai data yang lisensinya mengizinkan reuse.
2. **Self-contained (MUTLAK)** — SEMUA sumber daya (kode, korpus, dataset, model, aset, konfigurasi, dependensi) dibangun khusus untuk ICALORA-LABS. **DILARANG** mengambil, menyalin, atau berbagi sumber daya dari proyek lain mana pun di workspace (mis. Askara, CodeUnical, dll). Tidak ada ketergantungan silang antar-proyek.
3. **Jujur ke pengguna** — AI detector selalu menampilkan disclaimer akurasi; tidak ada klaim berlebihan.
4. **MVP dulu** — fitur ringan jalan cepat, fitur berat (plagiarism, detector) dibangun bertahap.
