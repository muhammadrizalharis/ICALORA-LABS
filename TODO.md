# ICALORA-LABS — Daftar Pekerjaan (Roadmap & Checklist)

> Dokumen pelacakan agar tidak ada permintaan yang terlupakan.
> Terakhir diperbarui: 2026-11-09. Centang `[x]` bila selesai.

---

## ✅ Sudah Selesai

- [x] Cari & kumpulkan pembahasan ICALORA-LABS dari riwayat + repo backup, rangkum ke markdown.
- [x] Perbaiki sidebar dashboard yang "menggantung" (sticky `top-0` + `self-start`, `nav` flex).
- [x] Tulis ulang semua copy/teks turunan Mulfu agar tidak melanggar hak cipta (banner, estimasi, disclaimer).
- [x] Infrastruktur job + redirect: submit tool → otomatis ke Beranda, job berjalan di latar meski pindah halaman (`lib/jobs.ts`, `lib/useJobs.ts`).
- [x] Status per-dokumen di Beranda: **Sedang diproses / Selesai / Gagal** (`RecentDocuments.tsx`).
- [x] Retensi riwayat **3 hari** (auto-purge `purge_expired_history`, filter interval di query).
- [x] Laporan plagiarisme ala Turnitin: dokumen penuh + highlight multi-warna, Match Groups, Top Sources, filter pengecualian (bibliografi/kutipan), ring skor (`PlagiarismReport.tsx`, `lib/plagiarismReport.ts`).
- [x] Tombol **Lihat Laporan (PDF)** & **Unduh Laporan** pada report plagiarisme.
- [x] **Laporan berformat identik dengan berkas asli**: unggah PDF → berkas asli disimpan di VM (tabel `tool_file`, bytea), laporan dirender dengan PyMuPDF = sampul ringkasan integritas + highlight ditimpakan langsung di atas halaman dokumen asli (`plagiarism/report_pdf.py`, endpoint `/tools/plagiarism-file` & `/tools/plagiarism-report/{id}`).
- [x] **Taksonomi kecocokan orisinal** (bukan tiruan Turnitin/Mulfu): Salinan Langsung / Kemiripan Kuat / Indikasi Parafrase / Sumber Terkredit — berbasis keparahan & sifat kecocokan.
- [x] **Indeks integritas gabungan** lebih kritis untuk akademik: menggabungkan salinan langsung + kemiripan leksikal + komponen parafrase semantik, ambang pencocokan diperketat (0.55→0.30).
- [x] Penyimpanan berkas di **VM Postgres** (bukan disk HPC) + ikut **auto-purge 3 hari** dan cascade saat riwayat dihapus.
- [x] **Cek Sumber Daring (tanpa unduh)**: lapis pelengkap opsional yang mengquery API akademik gratis real-time (OpenAlex, Crossref, arXiv, Wikipedia; CORE pluggable) — 0 GB disk, pencocokan lokal via `_chunk_match`. Arsitektur provider pluggable (`plagiarism/online.py`, endpoint `/tools/plagiarism-online`, tombol di `PlagiarismReport.tsx`).
  - Catatan: **CORE** diblokir di tingkat jaringan dari server HPC (Cloudflare menolak TLS) → `CORE_ENABLED=false`; key disimpan untuk masa depan. Pemakaian produk CORE perlu konfirmasi lisensi (ToS §3).
- [x] Backend menyimpan `document_text` (cap 60k) + `document_truncated` untuk highlight sisi klien.
- [x] Semua tool "rich" dikonversi ke alur redirect-ke-Beranda (Grader, Resume, Citation, AI-Detector, Authorship, Hidden-text, Publikasi, Writing-report, Transkrip, Rewrite, TOC, Improve, Reactions).
- [x] Unified history viewer (`HistoryResultView.tsx`) + `GenericResult` sebagai fallback.

---

## 🔲 Belum Selesai

### 1. Tampilan hasil kaya per-tool (prioritas tinggi)
Saat ini hanya `plagiarism-checker` yang punya view khusus; tool lain jatuh ke `GenericResult` yang generik. Buat view bespoke di dalam unified viewer untuk:

- [ ] **ai-detector** — gauge probabilitas AI + highlight per-kalimat.
- [ ] **ai-grader** — bar per-kriteria + ring nilai huruf + daftar saran.
- [ ] **citation-finder** — pemilih gaya sitasi (APA/MLA/Chicago/…) + tombol salin per sumber.
- [ ] **authorship** — skor kemiripan gaya + rincian fitur stilometrik + mode pembanding.
- [ ] **hidden-text** — daftar temuan (karakter tersembunyi, teks putih, typo).
- [ ] **publikasi-jurnal** — tata letak rekomendasi jurnal + skor kesiapan.
- [ ] **grammar-checker (writing report)** — daftar isu tata bahasa + teks terkoreksi.
- [ ] **transkrip-audio** — tampilkan segmen berwaktu (timestamp) + metadata bahasa/durasi/model.
- [ ] **resume-builder, reader-reactions, daftar-isi, perbaikan-dokumen, ai-rewriter** — rapikan render teks (bukan JSON mentah).

### 2. Halaman detail "Informasi File + Aksi" (dari screenshot Mulfu, kata-kata orisinal)
- [ ] Layout **dua kolom** di `dashboard/history/view/[id]/page.tsx`.
- [ ] Panel **Informasi File** universal: Report ID, SHA-256/hash, judul, tipe tool, tanggal, status/expired.
- [ ] Panel **Aksi** universal: **Lihat (buka PDF)**, **Download**, **Parafrase ulang**, **Periksa ulang**, dan langkah lanjutan.

### 3. Login Google (kode SELESAI — tinggal kredensial & konfigurasi)
Alur OAuth penuh sudah ada (`/auth/google/login`, `/auth/google/callback`, token exchange, userinfo, upsert user, set session). Yang kurang murni konfigurasi:

- [ ] Buat **OAuth 2.0 Client ID** (tipe: Web application) di Google Cloud Console.
- [ ] Set **Authorized redirect URI** = `https://<DOMAIN-PUBLIK>/api/backend/auth/google/callback`.
- [ ] Isi variabel di `backend/.env`:
  - [ ] `GOOGLE_CLIENT_ID=...`
  - [ ] `GOOGLE_CLIENT_SECRET=...`
  - [ ] `GOOGLE_REDIRECT_URI=https://<DOMAIN-PUBLIK>/api/backend/auth/google/callback`
  - [ ] `FRONTEND_BASE_URL=https://<DOMAIN-PUBLIK>`
- [ ] Restart `icalora-backend.service`, verifikasi tombol "Masuk dengan Google" muncul & alur callback berhasil.
- [ ] (Catatan) Domain publik ICALORA perlu dikonfirmasi — web diakses via Cloudflare Tunnel + nginx.

### 4. Backend / Data (berjalan di latar)
- [ ] **Embedding korpus** lanjut ke target **25%+** (saat ini ~19,3% dari 23,4 juta dokumen). Worker berjalan; JANGAN sentuh konfigurasi Ollama.

---

## 🌐 Opsi Deploy / Hosting (keputusan arsitektur)

- **Backend TIDAK bisa di Vercel**: butuh GPU, tugas lama (menit), Ollama + Postgres lokal → wajib tetap di server GPU dan diekspos via satu URL publik.
- **Frontend (Next.js) bisa di Vercel** (dapat domain gratis `*.vercel.app`), TAPI:
  - [ ] Jika pindah ke Vercel: browser harus panggil backend publik langsung (`NEXT_PUBLIC_API_BASE`), bukan proxy `/api/backend` (kena timeout serverless).
  - [ ] Konsekuensi beda-origin: set cookie sesi `SameSite=None; Secure` + buka CORS.
- **Rekomendasi: Opsi A — tetap self-host semua (same-origin)**, ekspos via **Cloudflare Tunnel (named)**. Tidak wajib domain berbayar; Login Google langsung bisa tanpa ubah cookie/CORS.
- Keputusan: _belum final — menunggu konfirmasi user._

---

## ⚙️ Catatan Deploy
- Frontend: `cd frontend && npx next build && systemctl --user restart icalora-frontend.service`
- Backend: `systemctl --user restart icalora-backend.service`
- Verifikasi: `curl` ke `:58030/dashboard` dan `:58010/auth/me` harus `200`.
- Commit sebagai `muhammadrizalharis` + trailer `Co-authored-by: Copilot`.
