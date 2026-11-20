# Pekerjaan Tertahan & Belum Dikerjakan — ICALORA-LABS

Dicatat 2026-11-19, diperbarui 2026-11-20. Semua perbaikan sebelumnya sudah ada di `main`
(PR #94–#105) dan dideploy. Dokumen ini hanya memuat yang **belum selesai** dan alasannya.

## Ringkasan prioritas (diperbarui 2026-11-20 malam)

| # | Item | Status | Pemilik |
|---|---|---|---|
| 1 | Ganti `SESSION_SECRET` produksi (**kritis**) | belum dilakukan | user |
| 2 | **Banner "paper terbit" muncul padahal indeks 2-4%** (Springer, BMC) | **temuan baru, belum diselidiki** | AI |
| 3 | **`semantic_match` kosong pada job produksi** (uji langsung 97,2%) | **sedang direproduksi** | AI |
| 4 | Penerbit yang gagal: MDPI, Frontiers, Springer, BMC, T&F, Elsevier, Wiley | analisis di bawah | AI |
| 5 | Peran admin biasa, Google login, token 0, teks "Gratis", lint, demo ganda | **selesai** (PR #104-#110) | - |
| 6 | Saldo akun id 18 (1000) | dibiarkan (keputusan user) | - |
| 7 | Mode hemat OpenAlex | **terbukti**: 9-21 pencarian/job (dulu ±110-140) | - |

## Temuan 2026-11-20 malam (BELUM SELESAI — lanjutkan dari sini)

### A. Banner "paper terbit" berisiko salah-tuduh

Uji penerbit (naskah = paper OA terbaru dengan 10% awal dibuang): pada **Springer** dan **BMC**
`publication_match` bernilai True padahal indeks hanya 2,0% dan 4,4% dan DOI paper aslinya tidak
ketemu. Artinya sumber LAIN dianggap "identik" lewat heuristik `title_identity`/containment di
`plagiarism/__init__.py` (`_title_in_front_matter` >= 0,70). Banner ini baru ditampilkan sejak
PR #96, jadi bisa menuduh paper yang salah. Langkah: cetak `publication_match` untuk dua kasus itu,
cari sinyal yang meloloskan, ketatkan (mis. wajib `fulltext_oa` atau containment tinggi), tambah tes.

### B. `semantic_match` kosong di job produksi

Deteksi parafrase (PR #110) pada dokumen yang diparafrase agresif: uji langsung terhadap kandidat
menghasilkan **97,2%** (35/36, 7,6 dtk), tetapi job produksi (`tool_history` id 184, sudah dihapus
bila lewat 3 hari) menyimpan `semantic_match: None`, padahal sumber IJHT ada di hasil dengan teks
penuh. Pengecualian di `_run_plagiarism_merged` ditelan diam-diam (`except Exception`). Reproduksi
sedang berjalan di dalam container (skrip trace di sesi); langkah berikutnya: tambahkan
`logger.warning(..., exc_info=True)` pada blok itu, jalankan ulang, temukan penyebab (timeout
240 dtk? kandidat di `extra` beda dengan hasil `identity_candidates`? embedding di container?).

### C. Hasil uji penerbit lain (1 paper per penerbit, tanpa judul/abstrak)

| Penerbit | Hasil | Catatan |
|---|---|---|
| PLOS | HIT 100% | 9 pencarian |
| IEEE | HIT 100% | 8 pencarian |
| MDPI | miss | paper ketemu tapi **teks penuh < 15.000 karakter** (gagal diunduh) |
| BMC | miss | idem; banner salah (lihat A) |
| Taylor & Francis | miss | idem |
| Frontiers | miss | paper tidak ketemu |
| Springer | miss | banner salah (lihat A) |
| Elsevier, Wiley | tak teruji | teks penuh tak bisa diunduh untuk 4 paper pertama |

Pola: deteksi berhasil bila teks penuh bisa diunduh (PLOS, IEEE). Kegagalan utama = **pengunduhan
teks penuh** dari penerbit yang memblokir bot / hanya HTML. Belum ada perbaikan; perlu dikaji
(Unpaywall / URL PDF alternatif / Crawl4AI milik server untuk halaman penerbit).
Skrip uji (sementara) ada di `/tmp/v/pubs.py` dan akan hilang; tulis ulang bila perlu.

### D. Kuota OpenAlex

Pengukuran nyata lewat header `x-ratelimit-remaining`: job penuh mode hemat = 9-21 pencarian
(90-210 kredit). Kuota harian $1 = 10.000 kredit. Uji malam ini menghabiskan sekitar 2.000 kredit
(banyak uji paralel).

## Keamanan & auth (2026-11-20)

### 1. `SESSION_SECRET` produksi masih nilai bawaan (publik) — KRITIS

Produksi memakai `icalora-dev-secret-change-me` (tertulis di kode). Siapa pun yang tahu nilainya
bisa memalsukan cookie sesi untuk akun mana pun, termasuk admin. Terbukti: token demo yang dibuat
dari mesin dev diterima produksi. Kode sudah menambah log CRITICAL saat startup dan flag
`session_secret_default` di `GET /health/providers`, tetapi **nilainya belum diganti**
(sengaja tidak diubah oleh AI: rahasia tidak boleh lewat AI, dan semua pengguna akan keluar sekali).

Langkah (dijalankan user di server):

```
echo "SESSION_SECRET=$(openssl rand -hex 32)" >> ~/ICALORA-LABS/backend/.env
cd ~/ICALORA-LABS && docker compose -f deploy/docker/docker-compose.app.yml up -d --no-deps backend bot
```

Verifikasi: `/health/providers` → `session_secret_default: false`. Token internal bot diturunkan dari
secret ini, jadi backend dan bot harus direstart bersamaan.

### 4. Login Google belum diuji end-to-end

Penyebab bug (proxy menimpa `Set-Cookie` ganda) sudah diperbaiki dan dibuktikan dengan image asli +
server tiruan (sebelum: 1 cookie, sesudah: 2). Alur Google sungguhan butuh akun Google pengguna,
jadi belum diuji. Cek: masuk lewat Google → harus mendarat di `/dashboard`, tombol "Masuk" berubah
menjadi chip profil.

## Token

### 5. Saldo akun yang sudah ada

`default_token_grant` live sudah **0** (hanya untuk pendaftar baru). Akun id 18
(`105841103223@student.unismuh.ac.id`) masih bersaldo 1000; admin (id 14) dan akun demo
tidak dipotong. Keputusan: nolkan saldo id 18 atau biarkan.

### 6. Peran "admin biasa"

Hanya ada satu peran admin (Super Admin). Token diberikan lewat panel Super Admin
(`/admin=-000` → kolom Token). Bila perlu admin biasa yang hanya boleh memberi token, itu butuh
sistem peran baru (tabel/kolom peran, pemeriksaan di endpoint admin, UI).

### 7. Teks "Gratis"

Pemakaian kini dibatasi token, tetapi beberapa teks masih berkata "Gratis":
`frontend/src/app/page.tsx` ("Gratis, legal, dan tanpa batas tersembunyi"), `StatsBar.tsx`
("Biaya: Gratis"), `cara-pakai/page.tsx` (FAQ "Berapa biayanya?"), dan kartu "Paket: Gratis"
sudah diganti jadi "Peran". Perlu kalimat yang selaras (mis. "gratis untuk akun terdaftar,
saldo token diatur admin").

## Plagiarism Checker — identitas paper terbit

## Konteks singkat

Dokumen yang diunggah tanpa judul/abstrak (mis. mulai dari Pendahuluan) dikenali sebagai paper
terbit lewat pass identitas di `backend/app/services/plagiarism/online.py`:
judul/DOI/abstrak → frasa isi (`fulltext.search` OpenAlex) → query istilah-khas (hanya bila perlu).
Hasil terukur: naskah tanpa judul 0,6–2,5% → ±97–100% bila OpenAlex tersedia.

**Ketergantungan utama:** pencarian frasa isi dokumen hanya dikerjakan OpenAlex. Kuota gratisnya
$1/hari (±1.000 pencarian) dibagi per key. Tanpa kuota, naskah tanpa judul hanya ±3% (diuji).
Laporan memberi catatan bila kuota habis (`online_budget_exhausted`).

## Tertahan (menunggu kuota OpenAlex reset ±08.00 WITA)

### 2. Validasi mode hemat OpenAlex — menunggu reset kuota (±08.00 WITA)

Mode hemat (PR #102) memperkirakan ±11–23 panggilan OpenAlex per job (dari ±110–140), tetapi
**belum terukur** karena kuota nol saat dikerjakan.

Langkah validasi:
1. Setelah kuota reset, jalankan satu job penuh dari naskah **tanpa judul** (Plagiarism Checker).
2. Baca `online_openalex_calls` pada hasil (tabel `tool_history`, kolom `result`).
3. Kriteria lulus: panggilan ≈ 11–23 **dan** paper terbit tetap terdeteksi (≥ 97%, ada banner
   "identik dengan paper yang sudah terbit").
4. Jika panggilan jauh di atas target, periksa urutan tahap di `_resolve_publication`.

### 3. Uji paper dari penerbit lain — menunggu reset kuota

Deteksi baru terbukti pada IIETA dan 9 jurnal Indonesia (OJS). Belum diuji: MDPI, Frontiers, PLOS,
Springer OA, Nature/BMC, Elsevier OA, Wiley, T&F, IEEE OA.

Cara: ambil 1–2 paper OA per penerbit (OpenAlex filter `doi_starts_with`, `is_oa:true`), hapus
judul/abstrak, jalankan pass identitas, catat HIT/MISS dan penyebab MISS (PDF tak terunduh,
gerbang unduh teks penuh, dll).

## Key Semantic Scholar (cadangan pencarian frasa) — diuji, TIDAK dipasang ke kode

Key diterima dan terpasang di `.env` (2026-11-19). Hasil uji pada naskah TEST4 (paper IIETA, terbit
Agustus 2026), 6 frasa isi 9-kata ke `/graph/v1/snippet/search`, jeda 1,2 dtk + retry bertahap:

- **Keandalan dari server ini rendah:** 4 dari 6 panggilan gagal (429 atau koneksi diputus) walau
  memakai key. Penyebabnya (jaringan server atau batas laju) belum dipastikan.
- **Dua panggilan yang berhasil tidak menemukan paper targetnya** (0/6 frasa). Dugaan: indeks
  potongan teks Semantic Scholar belum memuat paper yang baru terbit — belum diverifikasi pada
  paper lama.
- Catatan teknis: `snippet/search` tidak menerima `fields=paper.title` (400); kolom paper bawaan
  hanya `corpusId`/`title`/penulis, tanpa DOI (butuh panggilan tambahan untuk memetakan ke DOI).

Kesimpulan: **bukan pengganti** OpenAlex `fulltext.search` untuk paper baru terbit. Belum
dihubungkan ke pass identitas. Bisa diuji ulang pada paper lama bila ada kebutuhan.

## Batas yang diketahui (belum diputuskan)

(Item 8 pada ringkasan: dokumen yang seluruhnya diparafrase.)

- **Dokumen yang seluruhnya diparafrase** tidak terdeteksi (uji: 0,1%). Pencarian mengandalkan
  frasa persis. Solusinya pencocokan semantik terhadap teks penuh paper yang teridentifikasi —
  pekerjaan baru yang cukup besar.
- **Paper berbayar / diblokir penerbit**: teks penuh tak bisa diambil secara sah.
- **Mesin web SearXNG** rapuh (Brave/DuckDuckGo/Startpage sering terblokir); layanan itu dipakai
  bersama, jangan diuji berat. Bukan pengganti OpenAlex.
- Ambang banner "paper terbit" = ≥ 70% isi dokumen cocok dengan satu sumber teks penuh OA
  (heuristik). Dokumen yang menyalin hampir seluruh satu paper juga mendapat banner;
  catatan netral sudah ditampilkan.

## Opsional / diamati

### 9. Peringatan lint lama (sudah ada sebelum pekerjaan ini)

- Backend: 2 di `online.py` (urutan impor, `_WORD_RE` didefinisikan dua kali), E501 di `reports.py`
  dan beberapa file `ingest/` & `ai_detector/`.
- Frontend: ESLint `react-hooks/set-state-in-effect` di `TopNav.tsx`, `lib/auth.tsx`, `login/page.tsx`.

### 10. Baris pengguna demo ganda

Tabel `users` memuat 13 baris `demo@icalora.local` (id 1–13, semua `is_demo`). Diduga tiap login demo
membuat baris baru; penyebab belum diselidiki. Tidak berdampak ke pengguna nyata (login demo
dimatikan di produksi), tetapi perlu dirapikan bila login demo dipakai lagi.

### Catatan fitur yang sudah ada namun terbatas

- OCR PDF pindaian: hanya di Plagiarism Checker, maks 40 halaman (`ocr_max_pages`); tool lain menolak
  PDF pindaian dengan pesan jelas.

## Setelan terkait (`backend/.env`)

| Setelan | Bawaan | Keterangan |
|---|---|---|
| `OPENALEX_API_KEY` | kosong | Key gratis; tanpa key kuota dibagi per-IP dan mudah habis |
| `OPENALEX_ENABLED` | `true` | `false` = OpenAlex tidak dipanggil sama sekali |
| `OPENALEX_SENTENCE_SEARCH` | `false` | Pencarian per-kalimat OpenAlex (boros kuota) |
| `OLLAMA_KEEP_ALIVE` | `5m` | Model dilepas dari VRAM setelah idle |
| `SESSION_SECRET` | **belum diset** | WAJIB acak di produksi (lihat item 1) |

## Pemantauan

- `GET /health/providers` memuat `rate_limited_today` (jumlah HTTP 429 per penyedia hari ini)
  dan `openalex_budget_exhausted`.
- Hasil tiap job memuat `online_openalex_calls`, `online_rate_limited`, `online_budget_exhausted`.
