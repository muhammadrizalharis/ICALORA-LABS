# 00 — Ringkasan Room Chat ICALORA-LABS

> **Tujuan dokumen:** menjadi *handoff* / titik sambung agar pembahasan ICALORA-LABS
> bisa dilanjutkan di room/chat baru tanpa kehilangan konteks.
> Dirangkum dari room asli dan backup chat.

---

## 📍 Sumber Room

| Item | Nilai |
|---|---|
| **Room utama** | `db9014f0-22e7-4514-84ba-dc33919b4a13` |
| **Periode** | 2026-11-01 → 2026-11-05 |
| **Jumlah event** | 15.468 |
| **Backup chat** | [copilot-chat-backup-ssh](https://github.com/muhammadrizalharis/copilot-chat-backup-ssh) → `sessions/db9014f0-.../transcript.md` |
| **Repo proyek** | [ICALORA-LABS](https://github.com/muhammadrizalharis/ICALORA-LABS) (publik) |
| **Lokasi lokal** | `/home/muhammadrizalharis/ICALORA-LABS` |

> Catatan: sesi lain (`03ae7f80`, `21f0ca34`, `23687904`, dll.) hanya menyebut folder
> ICALORA-LABS secara insidental (laporan penyimpanan, dsb.), **bukan** diskusi khusus.

---

## 🎯 Inti Keputusan (yang sudah final)

| Aspek | Keputusan |
|---|---|
| **Produk / web** | **ICALORA-LABS** |
| **Perusahaan** | **MRH INNOVEX** |
| **Domain** | `icaloralabs.com` / `icaloralabs.ai` + `mrhinnovex.com` (amankan) |
| **Konsep** | Toolkit akademik AI serba-bisa (alternatif Turnitin) — 13 fitur |
| **Data** | Mandiri, hanya sumber **open-access legal** (OpenAlex, PMC OA, DOAJ, CORE) — **tanpa scraping konten berbayar** |
| **Prinsip** | Legal-first · Self-contained (mutlak, tidak ambil sumber proyek lain) · Jujur ke pengguna · MVP dulu |
| **Branding kata "Turnitin"** | **Dihapus** dari produk; pakai istilah "plagiarism / similarity" yang sah & terpercaya |
| **Telegram bot** | **Dibatalkan** (tidak diperlukan) |
| **Hosting** | Sementara localhost; hosting menyusul |
| **Aturan repo** | Setiap perubahan sekecil apa pun **wajib commit & push** ke repo publik |
| **Port** | Khusus ICALORA-LABS (infra 54432/54379/54333/54888, API 58010), hanya `127.0.0.1`, **tidak pernah** pakai port user/proyek lain |

---

## 🧭 Kronologi Pembahasan (ringkas)

1. **Ide awal** — bisakah bikin web mirip Turnitin + deteksi AI karena biaya Turnitin mahal.
   → Jawaban: fitur AI realistis; plagiarism ala Turnitin mahal karena **data berlisensi**, bukan algoritma. Scraping publisher berbayar = risiko hukum. Pakai open-access legal.
2. **Riset nama** — eksplorasi banyak kandidat → final **ICALORA-LABS by MRH INNOVEX**.
3. **Rencana lengkap** — dibuat di `/home/muhammadrizalharis/ICALORA-LABS` (docs 01–12).
4. **Database/keamanan/stack** — Postgres+pgvector, Redis, SeaweedFS; backend FastAPI, frontend Next.js; fokus optimal & anti-malware; semua tool di-host sendiri.
5. **Strategi penyimpanan korpus** — hemat disk (kompresi, konversi gambar→teks), opsi simpan ke drive 1000TB.
6. **Scaffold monorepo (Fase 0)** — backend + frontend terhubung ke infra.
7. **Pengumpulan korpus otomatis** — ingest di background, **prioritas GPU** daripada CPU, multi-sumber (OpenAlex, PMC OA, DOAJ, CORE; cek open-access ScienceDirect/MDPI).
8. **UI/branding** — logo transparan dipasang; UI dibuat lebih proper ala tools akademik modern; skema warna soft 1-warna.
9. **Fitur & laporan** — tiap fitur hasilkan **laporan PDF terverifikasi** yang bisa diunduh; AI Detector sentence-level + highlight; plagiarism bandingkan ke **seluruh korpus (±1,3 juta dok)** dengan label jujur.
10. **Operasional** — runtime 24/7 jangan padam; Ollama dibahas soal resident vs on-demand (VRAM); batas input 50.000 karakter (`MAX_CHARS` di `backend/app/api/tools.py`).

---

## ✅ Status Saat Ini

- [x] Riset nama, branding, rencana (fitur/arsitektur/data/roadmap/stack/legal)
- [x] Infrastruktur data (Postgres+pgvector, Redis, SeaweedFS) + tooling keamanan
- [x] **Fase 0** — scaffold monorepo (FastAPI + Next.js) terhubung ke infra
- [x] 9 fitur ringan (LLM) + laporan PDF terverifikasi
- [x] AI Detector sentence-level + highlight inline
- [x] Plagiarism checker bandingkan ke korpus ±1,3 juta dokumen
- [~] Ingest/embedding korpus berjalan (worker `icalora-ingest-embed`) — isu VRAM GPU dibahas
- [ ] Finalisasi fitur berat (AI Detector dataset latih, Authorship)
- [ ] Pengumpulan korpus menuju target penuh
- [ ] Hosting produksi

---

## 📂 Peta Dokumen Rencana

`README.md` · `docs/01-features.md` … `docs/12-dataset-ingestion.md`
(lihat tabel lengkap di [README.md](../README.md)).

---

## ⏭️ Titik Sambung (pembahasan terakhir)

Pertanyaan terakhir di room asli: **"batas 50.000 karakter — bisa lebih?"**
→ **Sudah diselesaikan:** batas dinaikkan menjadi `MAX_CHARS = 2_000_000`
(`backend/app/api/tools.py`) — hanya pagar keamanan memori (server 24/7, ±340rb kata).
Analisis semantik memakai embedding per-jendela, jadi seluruh isi dokumen tetap diperiksa.

**Untuk dilanjutkan di room ini** — kandidat topik berikutnya:
- Menaikkan / membuat batas karakter adaptif per fitur.
- Menstabilkan resident model Ollama vs on-demand (manajemen VRAM).
- Melanjutkan ingest korpus ke target & verifikasi kualitas similarity.
- Finalisasi fitur berat + QA laporan PDF.
