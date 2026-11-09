<!-- ╔══════════════════════════════════════════════════════════════════╗ -->
<!--                        ICALORA-LABS README                          -->
<!-- ╚══════════════════════════════════════════════════════════════════╝ -->

<div align="center">

<img src="https://capsule-render.vercel.app/api?type=waving&color=0:4F46E5,100:06B6D4&height=200&section=header&text=ICALORA-LABS&fontSize=60&fontColor=ffffff&animation=fadeIn&fontAlignY=38&desc=AI%20Academic%20Integrity%20Toolkit%20by%20MRH%20INNOVEX&descSize=18&descAlignY=60" alt="ICALORA-LABS" />

<a href="https://github.com/muhammadrizalharis/ICALORA-LABS">
  <img src="https://readme-typing-svg.demolab.com?font=Fira+Code&weight=600&size=22&pause=1000&color=06B6D4&center=true&vCenter=true&width=600&lines=Where+scholarship+meets+truth.;Plagiarism+Checker+%E2%80%A2+AI+Detector+%E2%80%A2+Paraphraser;Legal-first+%E2%80%A2+Self-contained+%E2%80%A2+Transparent" alt="Typing SVG" />
</a>

<br/>

<!-- ─────────────────────────────  Badges  ───────────────────────────── -->
<p>
  <img src="https://img.shields.io/badge/license-Proprietary-red?style=for-the-badge" alt="License" />
  <img src="https://img.shields.io/badge/status-Live-brightgreen?style=for-the-badge" alt="Status" />
  <img src="https://img.shields.io/badge/data-Open--Access%20Legal-blueviolet?style=for-the-badge" alt="Data" />
</p>

<p>
  <img src="https://img.shields.io/badge/FastAPI-009688?style=flat-square&logo=fastapi&logoColor=white" alt="FastAPI" />
  <img src="https://img.shields.io/badge/Next.js-000000?style=flat-square&logo=next.js&logoColor=white" alt="Next.js" />
  <img src="https://img.shields.io/badge/PostgreSQL-4169E1?style=flat-square&logo=postgresql&logoColor=white" alt="PostgreSQL" />
  <img src="https://img.shields.io/badge/pgvector-4169E1?style=flat-square&logo=postgresql&logoColor=white" alt="pgvector" />
  <img src="https://img.shields.io/badge/Redis-DC382D?style=flat-square&logo=redis&logoColor=white" alt="Redis" />
  <img src="https://img.shields.io/badge/SeaweedFS-33A1C9?style=flat-square&logo=files&logoColor=white" alt="SeaweedFS" />
  <img src="https://img.shields.io/badge/Ollama-000000?style=flat-square&logo=ollama&logoColor=white" alt="Ollama" />
  <img src="https://img.shields.io/badge/Python-3776AB?style=flat-square&logo=python&logoColor=white" alt="Python" />
  <img src="https://img.shields.io/badge/TypeScript-3178C6?style=flat-square&logo=typescript&logoColor=white" alt="TypeScript" />
</p>

</div>

---

<div align="center">

> **🌐 Web / Produk:** `ICALORA-LABS` &nbsp;·&nbsp; **🏢 Perusahaan:** `MRH INNOVEX`
>
> *"ICALORA-LABS — Where scholarship meets truth."*

</div>

Platform AI akademik serba-bisa: **plagiarism checker, AI detector, paraphraser,
humanizer, grammar checker, citation finder, AI grader**, dan lainnya — solusi
deteksi plagiarisme & AI yang **sah, transparan, dan terpercaya**, dibangun
**mandiri** dengan **korpus & sumber daya milik sendiri** dari sumber
**open-access yang legal**.

---

## 📑 Daftar Isi

- [✨ Sorotan](#-sorotan)
- [🧰 Fitur Unggulan](#-fitur-unggulan)
- [🧱 Arsitektur Singkat](#-arsitektur-singkat)
- [📁 Struktur Dokumen Rencana](#-struktur-dokumen-rencana)
- [🎯 Ringkasan Keputusan](#-ringkasan-keputusan)
- [⚡ Status](#-status)
- [▶️ Menjalankan Secara Lokal](#️-menjalankan-secara-lokal-fase-0)
- [🚦 Prinsip Utama](#-prinsip-utama)
- [📜 Lisensi](#-lisensi)

---

## ✨ Sorotan

| | |
|---|---|
| ⚖️ **Legal-first** | Hanya sumber open-access legal (OpenAlex, PMC OA, DOAJ, CORE) — tanpa scraping konten berbayar. |
| 🔒 **Self-contained** | Semua kode, korpus, dataset, model, dan aset dibangun khusus untuk ICALORA-LABS. |
| 🧠 **AI yang jujur** | AI detector sentence-level dengan highlight & disclaimer akurasi — tanpa klaim berlebihan. |
| 📄 **Laporan terverifikasi** | Setiap fitur menghasilkan laporan PDF yang bisa diunduh. |
| 🛡️ **Privasi & keamanan** | Semua layanan mengikat `127.0.0.1`, self-hosted, anti-malware. |

---

## 🧰 Fitur Unggulan

| Fitur | Deskripsi |
|---|---|
| 🔍 **Plagiarism Checker** | Bandingkan dokumen ke korpus besar dengan label kemiripan yang jujur. |
| 🤖 **AI Detector** | Deteksi teks AI level kalimat + highlight inline + skor terkalibrasi. |
| ✍️ **Paraphraser** | Tulis ulang teks mempertahankan makna. |
| 🪄 **Humanizer** | Haluskan gaya tulisan agar lebih natural. |
| 📝 **Grammar / Writing Report** | Daftar isu tata bahasa + teks terkoreksi. |
| 📚 **Citation Finder** | Temukan & format rujukan yang relevan. |
| 🎓 **AI Grader** | Penilaian otomatis dengan rubrik. |
| 🧬 **Authorship / Stylometry** | Skor kemiripan gaya + fitur stilometrik. |
| 🕵️ **Hidden-Text Scanner** | Temukan karakter tersembunyi / teks putih / sisipan. |
| 📰 **Rekomendasi Jurnal** | Tata letak rekomendasi jurnal + skor kesiapan. |

> Peta lengkap 13 fitur: **[docs/01-features.md](./docs/01-features.md)**.

---

## 🧱 Arsitektur Singkat

```text
                ┌────────────────────┐
   Pengguna ──▶ │  Frontend (Next.js) │ ──┐  same-origin proxy
                └────────────────────┘   │
                                         ▼
                ┌────────────────────┐   API
                │  Backend (FastAPI)  │ ◀─┘
                └─────────┬──────────┘
          ┌───────────────┼───────────────┐
          ▼               ▼               ▼
   ┌────────────┐  ┌────────────┐  ┌────────────┐
   │ PostgreSQL │  │   Redis    │  │ SeaweedFS  │
   │ + pgvector │  │  (cache)   │  │  (objek)   │
   └────────────┘  └────────────┘  └────────────┘
          ▲
          │   embeddings & LLM
     ┌────────────┐
     │   Ollama   │  (GPU, self-hosted)
     └────────────┘
```

Detail: **[docs/02-architecture.md](./docs/02-architecture.md)**.

---

## 📁 Struktur Dokumen Rencana

| 📄 File | Isi |
|---|---|
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
| [docs/11-report-viewer-spec.md](./docs/11-report-viewer-spec.md) | Spesifikasi report viewer |
| [docs/12-dataset-ingestion.md](./docs/12-dataset-ingestion.md) | Pipeline ingest & embedding korpus |

---

## 🎯 Ringkasan Keputusan

| Aspek | Keputusan |
|---|---|
| 🏷️ **Nama web / produk** | ICALORA-LABS |
| 🏢 **Nama perusahaan** | MRH INNOVEX |
| 🗄️ **Pendekatan data** | Mandiri (self-contained), korpus dari sumber open-access legal |
| ⚖️ **Legalitas** | Hanya sumber berlisensi reuse (OpenAlex, PMC OA, DOAJ, CORE) — **tanpa scraping konten berbayar** |
| 🎓 **Target** | Mahasiswa, dosen, peneliti, institusi |

---

## ⚡ Status

- [x] 🧭 Riset nama & branding
- [x] 🗺️ Rencana fitur, arsitektur, data, roadmap, stack, legal
- [x] 🧱 Infrastruktur data (Postgres+pgvector, Redis, SeaweedFS) + tooling keamanan
- [x] 🚀 **Fase 0** — scaffold monorepo (backend FastAPI + frontend Next.js), terhubung ke infra
- [x] 🧰 Fitur ringan (LLM) + laporan PDF terverifikasi
- [x] 🤖 AI Detector sentence-level + highlight inline
- [x] 🔍 Plagiarism checker bandingkan ke korpus
- [~] 📥 Ingest/embedding korpus berjalan
- [ ] 🧪 Finalisasi fitur berat + QA laporan

---

## ▶️ Menjalankan Secara Lokal (Fase 0)

> **Prasyarat:** 🐳 Docker · 🟢 Node 20+ · 🐍 Python 3.10+

**1. Infrastruktur** (Postgres / Redis / SeaweedFS)

```bash
cd infra
cp .env.example .env && cp seaweedfs/s3.json.example seaweedfs/s3.json
# isi secret kuat Anda sendiri; samakan S3_SECRET_KEY dengan s3.json
chmod 600 .env && chmod 644 seaweedfs/s3.json && chmod 700 seaweedfs
docker compose -f docker-compose.infra.yml up -d
```

Detail & hardening: **[docs/09](./docs/09-infrastructure-setup.md)**.

**2. Backend** (FastAPI, default port 58010)

```bash
cd backend
python3 -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env   # samakan nilai dengan infra/.env
uvicorn app.main:app --host 127.0.0.1 --port 58010
# cek koneksi infra: curl http://127.0.0.1:58010/health/infra
```

**3. Frontend** (Next.js, port 3000)

```bash
cd frontend
cp .env.example .env.local
npm install && npm run dev
```

> 🔐 Semua port ICALORA-LABS khusus (54432/54379/54333/54888 infra, 58010 API) dan
> hanya mengikat `127.0.0.1`. **Tidak pernah** memakai port/proses proyek lain.

---

## 🚦 Prinsip Utama

1. ⚖️ **Legal-first** — hanya memakai data yang lisensinya mengizinkan reuse.
2. 🔒 **Self-contained (MUTLAK)** — SEMUA sumber daya (kode, korpus, dataset, model,
   aset, konfigurasi, dependensi) dibangun khusus untuk ICALORA-LABS. **DILARANG**
   mengambil, menyalin, atau berbagi sumber daya dari proyek lain mana pun.
3. 🙏 **Jujur ke pengguna** — AI detector selalu menampilkan disclaimer akurasi;
   tidak ada klaim berlebihan.
4. 🧩 **MVP dulu** — fitur ringan jalan cepat, fitur berat (plagiarism, detector)
   dibangun bertahap.

---

## 📜 Lisensi

**Proprietary — © 2026 MRH INNOVEX. All Rights Reserved.**

Kode ini **dapat dilihat publik untuk transparansi**, namun **tidak memberikan izin**
untuk digunakan, disalin, dimodifikasi, atau didistribusikan tanpa izin tertulis dari
pemilik. Lihat berkas **[LICENSE](./LICENSE)** untuk ketentuan lengkap.

<div align="center">

<br/>

<img src="https://capsule-render.vercel.app/api?type=waving&color=0:06B6D4,100:4F46E5&height=120&section=footer" alt="footer" />

<sub>© 2026 <b>MRH INNOVEX</b> · ICALORA-LABS — All Rights Reserved</sub>

</div>
