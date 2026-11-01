# 08 — Database, Keamanan, Backend & Frontend

Dokumen ini merinci pondasi teknis ICALORA-LABS: pilihan database, lapisan keamanan, serta ringkasan backend & frontend. Melengkapi [05-tech-stack.md](./05-tech-stack.md) dan [02-architecture.md](./02-architecture.md).

> **Prinsip:** semua dibangun sendiri (self-contained), tanpa mengambil sumber daya dari proyek lain.

---

## 1. Database

### Pilihan utama: PostgreSQL

| Komponen | Teknologi | Fungsi |
|---|---|---|
| Database utama | **PostgreSQL 16** | User, dokumen, hasil analisis, langganan, metadata korpus |
| Vector search | **pgvector** (extension) | Embedding untuk deteksi parafrase / semantic similarity |
| Cache & antrian | **Redis** | Cache hasil, session, broker job berat |
| Object storage | **MinIO / S3-compatible** | Dokumen asli & full-text korpus (TIDAK disimpan di DB) |

**Alasan:** gratis, matang, andal; pgvector memungkinkan satu DB untuk data relasional + vector (sederhana di awal). Bisa migrasi ke **Qdrant** saat korpus membesar.

### Skema inti (gambaran awal)

```
users            (id, email, password_hash, role, created_at)
subscriptions    (id, user_id, plan, quota, status, period)
documents        (id, user_id, filename, storage_key, status, created_at)
analyses         (id, document_id, type, result_json, score, created_at)
corpus_docs      (id, source, license, doi, title, storage_key, indexed_at)
corpus_segments  (id, corpus_doc_id, text_hash, embedding, position)
```

- Dokumen & full-text **tidak** disimpan di kolom DB besar → pakai object storage, DB simpan `storage_key`.
- `corpus_docs.license` wajib diisi (audit lisensi — lihat [06-legal-compliance.md](./06-legal-compliance.md)).

### Migrasi & ORM
- **SQLAlchemy** (ORM) + **Alembic** (migrasi versi skema).

---

## 2. Keamanan

> ⚠️ Repo ini **PUBLIK**. Kode boleh publik, **rahasia tidak pernah**. Semua konfigurasi sensitif lewat environment variable.

### Secrets & konfigurasi
- Semua kredensial di `.env` → sudah diblokir `.gitignore`.
- Gunakan secret manager di produksi (mis. Docker secrets / vault).
- **Tidak ada** API key, password, token, atau connection string di dalam kode.

### Autentikasi & otorisasi
| Aspek | Implementasi |
|---|---|
| Login | JWT (access + refresh token) |
| Password | Hash **argon2** atau **bcrypt** (tidak pernah plaintext) |
| Role | Role-based access control (user / admin) |
| Isolasi data | Tiap user hanya bisa akses dokumen miliknya |

### Perlindungan aplikasi
- **HTTPS/TLS wajib** + HSTS.
- **Validasi input** ketat (Pydantic) → cegah SQL injection & XSS.
- **ORM parameterized query** → tanpa string SQL manual.
- **Rate limiting** per user/IP → cegah abuse & brute force.
- **CORS** dibatasi ke domain yang diizinkan.
- **Security headers** (CSP, X-Frame-Options, dll).
- **Upload**: validasi tipe & ukuran file, batasi, scan sebelum proses.

### Privasi data pengguna
- Enkripsi at-rest untuk dokumen pengguna.
- Opsi **auto-delete** dokumen setelah analisis selesai.
- Dokumen pengguna **tidak** dimasukkan ke korpus publik tanpa izin eksplisit.
- Patuhi UU PDP (Indonesia) & GDPR bila relevan.

### Operasional
- **Dependabot** / scan dependensi untuk celah library.
- Logging & audit (tanpa menyimpan data sensitif di log).
- Backup database terenkripsi & terjadwal.

---

## 3. Backend

**Python 3.12 + FastAPI** (ideal untuk beban ML/AI).

| Komponen | Teknologi | Fungsi |
|---|---|---|
| Web framework | FastAPI | API async + auto-docs (Swagger/OpenAPI) |
| Validasi | Pydantic | Skema & keamanan input |
| Antrian job | Celery / RQ + Redis | Proses berat (plagiarism, AI detector) tanpa blok API |
| ORM & migrasi | SQLAlchemy + Alembic | Akses DB & versioning skema |
| Server | Uvicorn / Gunicorn | Runtime produksi |

**Struktur modular** — tiap fitur service terpisah: `llm/`, `plagiarism/`, `ai_detector/`, `authorship/`, `citation/` (lihat struktur folder di [05-tech-stack.md](./05-tech-stack.md)).

**Alur job berat:** request → API validasi → enqueue → worker proses → simpan hasil → frontend ambil via polling/WebSocket.

---

## 4. Frontend

**Next.js (App Router) + TypeScript**.

| Komponen | Teknologi | Fungsi |
|---|---|---|
| Framework | Next.js | SSR/SSG, SEO, routing modern |
| Styling | Tailwind CSS + shadcn/ui | UI bersih, cepat dibangun |
| Data fetching | React Query / tRPC | Aman & efisien, typed |
| Realtime | WebSocket / polling | Status proses dokumen |
| Komponen inti | **Report Viewer** | Laporan plagiarism/AI: highlight warna + daftar sumber + persentase (ala Turnitin) |

**Fokus UX:**
- Sidebar 13 fitur (sesuai referensi toolkit).
- Upload dokumen (PDF/DOCX) dengan indikator progres.
- Report viewer interaktif (klik highlight → lihat sumber).
- Autentikasi, dashboard, halaman langganan.

---

## Ringkasan Keputusan

```
Database  : PostgreSQL + pgvector + Redis + MinIO/S3
Keamanan  : JWT, argon2/bcrypt, HTTPS, validasi Pydantic, rate limit,
            secrets via .env (repo publik aman), enkripsi data pengguna
Backend   : Python 3.12 + FastAPI + Celery + SQLAlchemy/Alembic
Frontend  : Next.js + TypeScript + Tailwind + shadcn/ui
```

> Detail provider LLM, hosting, dan vector DB final ditetapkan saat mulai Fase 0.
