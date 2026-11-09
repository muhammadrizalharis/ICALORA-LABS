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
- [x] **Kompresi berkas tersimpan**: bytea dioptimasi (PyMuPDF garbage-collect + deflate untuk PDF) lalu dikompres zstd (level 19) sebelum disimpan, dan didekompres transparan saat dibaca. Kolom baru `compression`/`stored_size`; kompatibel mundur (baris lama `compression=NULL` dibaca apa adanya). Verifikasi round-trip end-to-end merender laporan PDF identik.
- [x] **Cek Sumber Daring (tanpa unduh)**: lapis pelengkap opsional yang mengquery API akademik gratis real-time (OpenAlex, Crossref, arXiv, Wikipedia; CORE pluggable) — 0 GB disk, pencocokan lokal via `_chunk_match`. Arsitektur provider pluggable (`plagiarism/online.py`, endpoint `/tools/plagiarism-online`, tombol di `PlagiarismReport.tsx`).
  - Catatan: **CORE** diblokir di tingkat jaringan dari server HPC (Cloudflare menolak TLS) → `CORE_ENABLED=false`; key disimpan untuk masa depan. Pemakaian produk CORE perlu konfirmasi lisensi (ToS §3).
- [x] **Sumber daring OTOMATIS tergabung ke skor utama**: tiap laporan plagiarisme kini menggabungkan kandidat daring (OpenAlex/Crossref/arXiv/Wikipedia) langsung ke `_chunk_match`, sehingga **satu Indeks Integritas** mencakup korpus lokal + daring. `check_plagiarism(doc, top_k, extra_candidates)`, helper `online_candidates()`, endpoint `/tools/plagiarism{,-file}` jalur async + `run_in_threadpool`. Hanya menaikkan `copy_index` (verbatim), tidak menyentuh jalur semantik → tidak menambah false positive; sumber daring tanpa kecocokan nyata dibuang. Lencana **DARING** di daftar sumber + catatan penyedia di PDF/layar. Contoh: teks "Attention Is All You Need" 1.8% (lokal) → 83.1% (gabungan).
- [x] **Deteksi identitas publikasi (reverse-containment)** — mengatasi kasus "paper yang sudah terbit malah skor 2%". API daring hanya mengekspos **abstrak**, bukan teks penuh; dokumen 10rb kata yang dibandingkan dengan abstraknya sendiri (~300 kata) hanya menghasilkan ~2% doc-containment walau dokumen itu memang paper tersebut. Solusi: hitung **containment terbalik** = `|shingles(sumber) ∩ shingles(dok)| / |shingles(sumber)|` (porsi teks SUMBER yang termuat di dokumen). Abstrak sendiri ≈100% termuat → ditandai `publication_match` (banner oranye + badge "abstrak NN% termuat"). Tidak memalsukan Indeks Integritas (badan teks tak terverifikasi) — tetap jujur, hanya menambah sinyal terpisah. Ambang `_PUBMATCH_MIN=0.75`, abaikan sumber <40 kata. Terverifikasi: paper DOI `10.47852/bonviewjdsis62028311` → `containment=100%`, `integrity_index` tetap jujur. (Issue #3)
- [x] Semua tool "rich" dikonversi ke alur redirect-ke-Beranda (Grader, Resume, Citation, AI-Detector, Authorship, Hidden-text, Publikasi, Writing-report, Transkrip, Rewrite, TOC, Improve, Reactions).
- [x] Unified history viewer (`HistoryResultView.tsx`) + `GenericResult` sebagai fallback.

---

## 🔲 Belum Selesai

### 1. Tampilan hasil kaya per-tool (prioritas tinggi)
Saat ini hanya `plagiarism-checker` yang punya view khusus; tool lain jatuh ke `GenericResult` yang generik. Buat view bespoke di dalam unified viewer untuk:

- [x] **ai-detector** — gauge probabilitas AI + highlight per-kalimat.
- [x] **ai-grader** — bar per-kriteria + ring nilai huruf + daftar saran.
- [x] **citation-finder** — pemilih gaya sitasi (APA/MLA/Chicago/…) + tombol salin per sumber.
- [x] **authorship** — skor kemiripan gaya + rincian fitur stilometrik + mode pembanding.
- [x] **hidden-text** — daftar temuan (karakter tersembunyi, teks putih, typo).
- [x] **publikasi-jurnal** — tata letak rekomendasi jurnal + skor kesiapan.
- [x] **grammar-checker (writing report)** — daftar isu tata bahasa + teks terkoreksi.
- [x] **transkrip-audio** — tampilkan segmen berwaktu (timestamp) + metadata bahasa/durasi/model.
- [x] **resume-builder, reader-reactions, daftar-isi, perbaikan-dokumen, ai-rewriter** — rapikan render teks (bukan JSON mentah).

### 2. Halaman detail "Informasi File + Aksi" (dari screenshot Mulfu, kata-kata orisinal)
- [x] Layout **dua kolom** di `dashboard/history/view/[id]/page.tsx`.
- [x] Panel **Informasi File** universal: Report ID, SHA-256/hash, judul, tipe tool, tanggal, status/expired.
- [x] Panel **Aksi** universal: **Lihat (buka PDF)**, **Download**, **Parafrase ulang**, **Periksa ulang**, dan langkah lanjutan.

### 3. Login Google (kode SELESAI — tinggal kredensial & konfigurasi)
Alur OAuth penuh sudah ada (`/auth/google/login`, `/auth/google/callback`, token exchange, userinfo, upsert user, set session). Yang kurang murni konfigurasi:

- Domain publik ICALORA **sudah live**: `https://icalora-lab.calyzr-ai.my.id` (menumpang tunnel Cloudflare `calyzr-ai.my.id`, same-origin ke frontend :58030 yang proxy backend :58010).
- [ ] Buat **OAuth 2.0 Client ID** (tipe: Web application) di Google Cloud Console.
- [ ] Set **Authorized redirect URI** = `https://icalora-lab.calyzr-ai.my.id/api/backend/auth/google/callback`.
- [x] Siapkan variabel URL publik di `backend/.env` (`GOOGLE_REDIRECT_URI`, `FRONTEND_BASE_URL`).
- [ ] Isi kredensial di `backend/.env`:
  - [ ] `GOOGLE_CLIENT_ID=...`
  - [ ] `GOOGLE_CLIENT_SECRET=...`
- [ ] Restart `icalora-backend.service`, verifikasi tombol "Masuk dengan Google" & alur callback berhasil.

### 4. Backend / Data (berjalan di latar)
- [x] **Embedding korpus** mencapai target **25%** (5.861.751 dari 23.415.245 dokumen = 25,03%). Worker dihentikan di target; rebuild indeks HNSW berjalan di VM (fase "loading tuples"). JANGAN sentuh konfigurasi Ollama.

---

## 🌐 Opsi Deploy / Hosting (keputusan arsitektur)

- **Backend TIDAK bisa di Vercel**: butuh GPU, tugas lama (menit), Ollama + Postgres lokal → wajib tetap di server GPU dan diekspos via satu URL publik.
- **Frontend (Next.js) bisa di Vercel** (dapat domain gratis `*.vercel.app`), TAPI:
  - [ ] Jika pindah ke Vercel: browser harus panggil backend publik langsung (`NEXT_PUBLIC_API_BASE`), bukan proxy `/api/backend` (kena timeout serverless).
  - [ ] Konsekuensi beda-origin: set cookie sesi `SameSite=None; Secure` + buka CORS.
- **Rekomendasi: Opsi A — tetap self-host semua (same-origin)**, ekspos via **Cloudflare Tunnel (named)**. Tidak wajib domain berbayar; Login Google langsung bisa tanpa ubah cookie/CORS.
- Keputusan: **FINAL — Opsi A diterapkan.** ICALORA live di `https://icalora-lab.calyzr-ai.my.id` via tunnel `calyzr-ai.my.id` (ingress tambahan → `localhost:58030`). App calyzr lama tidak terganggu.

---

## ⚙️ Catatan Deploy
- Frontend: `cd frontend && npx next build && systemctl --user restart icalora-frontend.service`
- Backend: `systemctl --user restart icalora-backend.service`
- Verifikasi: `curl` ke `:58030/dashboard` dan `:58010/auth/me` harus `200`.
- Commit sebagai `muhammadrizalharis` + trailer `Co-authored-by: Copilot`.
