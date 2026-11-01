# 02 — Arsitektur Teknis

Arsitektur ICALORA-LABS dirancang **self-contained**: semua layanan & data milik sendiri, tidak bergantung pada proyek lain.

---

## Diagram Tingkat Tinggi

```
┌───────────────────────────────────────────────────────────┐
│  FRONTEND — Next.js (web app + dashboard + report viewer)  │
│  • Sidebar 13 fitur   • Upload dokumen (PDF/DOCX)          │
│  • Report viewer (highlight warna, daftar sumber)          │
│  • Auth UI, billing/langganan                              │
└───────────────┬───────────────────────────────────────────┘
                │ REST / tRPC (HTTPS)
┌───────────────▼───────────────────────────────────────────┐
│  API GATEWAY — Python FastAPI                              │
│  • Auth & rate limit   • Orkestrasi fitur                  │
│  • Enqueue job berat ke worker                             │
└───┬───────────────┬───────────────┬───────────────────────┘
    │               │               │
┌───▼─────┐  ┌──────▼───────┐  ┌────▼──────────────┐
│ LLM     │  │ ML SERVICES  │  │  DATA LAYER        │
│ SERVICE │  │ • Detector   │  │ • PostgreSQL       │
│ (fitur  │  │ • Plagiarism │  │ • pgvector (embed) │
│  ringan)│  │ • Authorship │  │ • Object storage   │
└─────────┘  └──────┬───────┘  │   (dokumen, teks)  │
                    │          │ • Redis (cache/que)│
                    │          └────────┬───────────┘
            ┌───────▼──────────┐        │
            │ SEARCH / INDEX   │◄───────┘
            │ • MinHash index  │
            │ • Vector search  │
            │   (Qdrant/pgvec) │
            └───────┬──────────┘
                    │
        ┌───────────▼─────────────────┐
        │ CORPUS PIPELINE (batch job)  │
        │ Ingest: OpenAlex / PMC OA /  │
        │ DOAJ / CORE / arXiv          │
        │ → bersihkan → segmentasi     │
        │ → fingerprint + embedding    │
        │ → simpan ke index            │
        └─────────────────────────────┘
```

---

## Komponen

### 1. Frontend (Next.js + TypeScript + Tailwind)
- Halaman utama + dashboard pengguna.
- **Report Viewer**: komponen inti untuk menampilkan hasil plagiarism & AI detection (teks dengan highlight warna, panel sumber, angka persentase) — meniru format laporan Turnitin.
- Upload & antrian status proses dokumen (real-time via WebSocket/polling).

### 2. API Gateway (FastAPI)
- Autentikasi (JWT), otorisasi, rate limiting, kuota langganan.
- Orkestrasi: fitur ringan → langsung; fitur berat → masuk antrian worker.

### 3. LLM Service
- Melayani fitur Kelompok A (chat, grammar, paraphrase, rewrite, humanize, grade, reactions, resume).
- Abstraksi provider (bisa LLM API komersial atau model open-source self-hosted — keputusan di [05-tech-stack.md](./05-tech-stack.md)).

### 4. ML Services
- **Plagiarism engine**: segmentasi → cari kandidat (MinHash) → verifikasi (embedding similarity) → susun report.
- **AI detector**: pipeline fitur statistik + model classifier.
- **Authorship**: ekstraksi fitur stylometry + pembanding.

### 5. Data Layer
- **PostgreSQL** — data pengguna, dokumen, metadata, hasil.
- **pgvector / Qdrant** — index embedding untuk semantic search.
- **Object storage** (S3-compatible / MinIO) — simpan dokumen asli & full-text korpus.
- **Redis** — cache + broker antrian job.

### 6. Corpus Pipeline (batch)
- Worker terpisah untuk mengunduh, membersihkan, dan mengindeks korpus (lihat [03-data-strategy.md](./03-data-strategy.md)).
- Berjalan terjadwal (incremental update).

---

## Alur Proses Dokumen (Plagiarism)

```
User upload → ekstrak teks → segmentasi kalimat/paragraf
   → untuk tiap segmen:
        MinHash lookup (kandidat exact/near-dup)
        + vector search (kandidat parafrase)
   → scoring & agregasi
   → susun Similarity Report (highlight + sumber + %)
   → simpan hasil → tampilkan di Report Viewer
```

---

## Prinsip Non-Fungsional
- **Skalabilitas:** worker terpisah agar proses berat tidak memblok API.
- **Privasi:** dokumen pengguna dienkripsi at-rest; opsi hapus otomatis.
- **Observability:** logging, metrics, tracing untuk job berat.
