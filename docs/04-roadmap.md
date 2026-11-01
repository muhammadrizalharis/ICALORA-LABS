# 04 — Roadmap Pembangunan (5 Fase)

Pendekatan: **MVP dulu**, fitur ringan jalan cepat untuk validasi pasar, fitur berat dibangun bertahap.

---

## Fase 0 — Fondasi
**Tujuan:** kerangka siap pakai.
- Scaffold monorepo (frontend Next.js + backend FastAPI).
- Setup auth, database (PostgreSQL + pgvector), object storage, Redis.
- CI/CD dasar, environment, linting/testing.
- UI shell: sidebar 13 fitur + routing + report viewer kosong.

**Keluaran:** aplikasi bisa jalan lokal, login, navigasi antar fitur.

---

## Fase 1 — Fitur Ringan (LLM) ⚡
**Tujuan:** 9 fitur aktif cepat → produk sudah berguna.
- Word Count, Grammar Checker, Paraphraser, AI Rewriter, Humanizer,
  AI Chat, AI Grader, Reader Reactions, Resume Builder.
- Integrasi LLM service + abstraksi provider.
- Kuota/langganan dasar.

**Keluaran:** MVP yang bisa dipakai & (opsional) mulai monetisasi.

---

## Fase 2 — Citation Finder 🔖
**Tujuan:** fitur akademik pembeda.
- Integrasi Crossref + OpenAlex + DataCite.
- Pencarian referensi + format sitasi (APA, IEEE, MLA, Harvard, Vancouver).
- Ekspor BibTeX / RIS.

**Keluaran:** alat sitasi lengkap.

---

## Fase 3 — Plagiarism Checker 🔴 (inti)
**Tujuan:** fitur unggulan utama.
- Bangun corpus pipeline (ingest → clean → segment → fingerprint → embed → index).
- Mulai korpus terfokus (1 bidang) lalu skalakan.
- Engine similarity (MinHash + vector search).
- **Similarity Report viewer**: persentase + highlight + daftar sumber.

**Keluaran:** plagiarism checker fungsional dengan laporan ala Turnitin.

---

## Fase 4 — AI Detector & Authorship 🔴
**Tujuan:** melengkapi fitur deteksi.
- Bangun dataset manusia-vs-AI → latih classifier → validasi false-positive.
- AI Detector dengan highlight + disclaimer akurasi.
- Authorship/stylometry untuk verifikasi konsistensi penulis.

**Keluaran:** 13 fitur lengkap.

---

## Fase 5 — Skala & Polish 🚀
**Tujuan:** siap produksi & tumbuh.
- Perbesar korpus (jutaan → puluhan juta dokumen).
- Optimasi performa, caching, biaya storage.
- Billing/langganan penuh, dashboard admin, analitik.
- Keamanan, privasi, kepatuhan, dokumentasi pengguna.

**Keluaran:** platform produksi yang skalabel.

---

## Ringkasan Urutan Nilai

```
Fase 0  Fondasi
Fase 1  9 fitur ringan  ← produk cepat berguna
Fase 2  Citation Finder
Fase 3  Plagiarism      ← pembeda utama (berat)
Fase 4  AI Detector + Authorship
Fase 5  Skala & produksi
```

> Catatan: durasi tiap fase sengaja tidak dipatok di sini; akan ditentukan saat eksekusi sesuai sumber daya yang tersedia.
