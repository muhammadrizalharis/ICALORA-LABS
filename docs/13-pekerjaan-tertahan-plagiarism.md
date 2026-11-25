# Pekerjaan Tertahan & Belum Dikerjakan — ICALORA-LABS

Dicatat 2026-11-19, diperbarui 2026-11-20. Semua perbaikan sebelumnya sudah ada di `main`
(PR #94–#105) dan dideploy. Dokumen ini hanya memuat yang **belum selesai** dan alasannya.

## Ringkasan prioritas (diperbarui 2026-11-25)

| # | Item | Status | Pemilik |
|---|---|---|---|
| 1 | Ganti `SESSION_SECRET` produksi | **selesai 2026-11-24** (terverifikasi) | - |
| 2 | Banner "paper terbit" salah-tuduh (Springer) | **selesai** (PR #112) | - |
| 3 | `semantic_match` kosong di job produksi | **selesai** (PR #111); terbukti job produksi 97,2% | - |
| 4 | MDPI miss (teks pendek) | **selesai** (PR #113); 3,8% -> 100% | - |
| 5 | Durasi job bervariasi (225 -> 976 dtk) | **dijelaskan & dibatasi** (PR #115 + anggaran total), lihat "Durasi job" | - |
| 6 | Penerbit yang tetap gagal | batas diketahui (lihat tabel) | - |
| 7 | Peran admin, Google login, token 0, teks "Gratis", lint, demo ganda, mode hemat | **selesai** (PR #104-#110) | - |
| 8 | Bot Telegram: semua perintah diuji, galat jelas | **selesai** (PR #114) | - |
| 9 | Panel admin biasa/super diuji di browser | **selesai** (2026-11-25) | - |
| 10 | Ambang semantik divalidasi lintas bidang | **selesai** (6 paper, 3 bidang) | - |
| 11 | 8 peringatan lint frontend | **selesai** (aturan kembali `error`) | - |
| 12 | Kartu "sedang diproses" hilang saat refresh | **selesai** (PR #121) | - |
| 13 | Embedding korpus lokal gagal/lambat saat berebut (data produksi nyata) | **selesai**: akar masalah = bge-m3 sebagian di CPU; dipindah ke GPU 1 (~100x lebih cepat) + turun-mutu (PR #123-#124) | - |
| 14 | Bot: /cek memblokir bot & timeout 180 dtk | **selesai** (PR #123) | - |

## Hasil 2026-11-25

### Durasi job (diukur, bukan ditebak)

Hasil job kini memuat `online_timings` (detik per fase: `identity`, `broad`, `local_check`,
`semantic`) dan log INFO `Cek plagiarisme selesai: ...`. Timeout fase identitas/luas yang dulu
ditelan diam-diam kini tercatat WARNING.

- Pengukuran bersih (tanpa beban lain), dokumen 9.000 karakter tanpa judul: 594 dtk
  (identitas 19, **luas 534**, lokal 42) dan 468 dtk (identitas 63, **luas 383**, lokal 22).
  Fase luas = 80-90% waktu dan memang dirancang 5-10 menit (kalimat kueri adaptif 60-220).
  Outlier 594 dtk yang dulu tak bisa direproduksi = perilaku normal fase luas.
- Pengukuran terkontaminasi (proses uji yatim masih memakai LLM): 976 dtk dengan `semantic` = 240,0
  (kena batas, hasil dibuang). Penyebab sebenarnya: server embedding bge-m3 dipakai bersama,
  hanya separuh di VRAM (GPU penuh pengguna lain), load host ~54 -> ~1 dtk/jendela.
- Perbaikan: (a) `find_semantic_source` taat tenggat lunak dan mengembalikan kandidat terbaik yang
  sempat selesai; (b) `online_total_budget_seconds=1140`: fase luas & semantik dipangkas dinamis
  sehingga total job selalu < 20 menit (batas polling frontend). Sebelumnya jumlah batas per-fase
  bisa 180+840+lokal+240 > 20 mnt.
- **Lewati fase luas** (PR #118): bila pass identitas menemukan SATU paper teks-penuh OA yang memuat
  >= 90% isi dokumen (shingle 5 kata, `single_source_coverage`), pencarian luas dilewati. Diukur di
  produksi pada paper PLOS utuh: 468 dtk -> 109 dtk, hasil identik (100%, terbit). Dokumen separuh
  salinan (cakupan ~45%) TIDAK dilewati (luas 391 dtk, indeks 32,4%). Konsekuensi yang disengaja:
  laporan salinan-utuh hanya menampilkan sumber itu (tanpa sumber sekunder). Matikan dengan
  `ONLINE_SKIP_BROAD_COVERAGE=0`. Hasil memuat `online_broad_skipped`.
- **Embedding gagal tak lagi menggagalkan job** (PR #119): saat server embedding bersama kewalahan
  (load host sampai 93) satu timeout membuang job di langkah terakhir. Kini lanjut tanpa pencarian
  semantik korpus lokal; hasil memuat `local_corpus_unavailable` dan UI/PDF menampilkan catatan.
  Diuji dengan embedding dipaksa gagal terhadap DB nyata (bukan tes otomatis: butuh DB).
- **Ligatur** (PR #117/#118): berkas dan teks tempelan menguraikan "ﬁ ﬂ ﬀ ﬃ ﬄ ﬅ ﬆ" (bukan NFKC
  penuh, agar "m²" tak berubah); sorotan frontend disamakan (`expandLigatures`).
- **Docling TIDAK dipasang**: benchmark 21 PDF (15 acak + 6 terpilih): identik di 11/15 acak, lebih
  baik 2, lebih buruk 2; cold start 76 dtk; tak ada pemicu andal. Layak dipertimbangkan lagi hanya
  bila ada PDF nyata pengguna yang hasil ekstraksinya buruk (mis. karakter rusak > 1 per 1.000).

### Validasi ambang semantik (`semantic_match_cos=0,80`, `semantic_min_coverage=35`)

6 paper OA / 3 bidang (pendidikan ID, keuangan ID, medis EN); tiap paper diparafrase agresif oleh LLM
(4 potongan ~800 karakter), dibandingkan ke teks penuh ke-6 paper (6 positif, 30 negatif):

- Negatif (paper lain, termasuk satu bidang): **0% dari 30 pasangan** melewati 0,80;
  cosine rata-rata 0,56-0,72.
- Positif: 5 dari 5 potongan prosa terdeteksi (cakupan 57-75%; 4 paper di atas 57%). Satu "miss"
  (12,5%) ternyata potongan DAFTAR PUSTAKA (nama/judul rujukan, bukan prosa) - artefak uji.
- Putaran kedua (2026-11-25), 4 paper bidang lain (CS/evolusi-NN IEEE, teknik sipil Elsevier, ilmu
  sosial EN, ekonomi ID), parafrase agresif LLM 3 potongan/paper (potongan prosa, bukan daftar pustaka):
  **4 dari 4 terdeteksi** (cakupan 45,5 / 46,7 / 54,5 / 66,7%, ambang 35%) dan **0% pada 12 pasangan
  negatif**. Total kini 10 paper, 3+ bidang, ID & EN. Satu paper uji (hukum ID) gagal diunduh.
  Catatan: sumber dibatasi 250 jendela per paper (server embedding lambat), jadi cakupan positif bisa
  sedikit lebih rendah dari yang sebenarnya.
- Ambang tidak diubah. Batas: bahasa selain ID/EN dan bidang yang sangat teknis/rumus belum diuji.

### Jangkauan identitas (Springer/Frontiers)

Uji ulang dengan sampel acak paper berkutip rendah (bukan yang terkenal), fase identitas saja:

| Skenario | Frontiers | Springer |
|---|---|---|
| Tanpa judul/abstrak (hanya isi) | 6/6 ketemu | 3/5 ketemu |
| Dengan judul/abstrak (kondisi nyata) | - | 2/2 yang tadi meleset: ketemu (11 dtk, 50 dtk) |

Dua paper Springer yang meleset (teks tanpa judul) tetap meleset di pipeline penuh (indeks 4,1% dan
2,6%): keduanya preprint ResearchSquare. Jadi batas yang tersisa sempit: dokumen TANPA judul/abstrak
dari paper berkutip rendah yang tak terindeks baik oleh OpenAlex. Dokumen normal (ada judul) aman.

### Embedding berbatas waktu (temuan dari pemakaian nyata)

Dua pemeriksaan asli Super Admin (24 Nov malam) sama-sama kehilangan korpus lokal dan membuang
374-389 dtk di `local_check` (timeout embedding 120 dtk x 3 percobaan); satu job memakan 1.171 dtk
(batas polling frontend 1.200). Pemicu: pemeriksaan plagiarisme dan AI detector berjalan serempak
dan berebut server embedding bersama (bge-m3, sebagian di CPU: ~1,5 dtk/jendela).

Perbaikan (PR #123, #124):
- `embed_chunks_budgeted`: batch 8, anggaran 150 dtk, timeout 60 dtk per batch, urutan menyebar
  sehingga hasil PARSIAL tetap mewakili seluruh dokumen; tak pernah melempar; menyerah setelah 2
  kegagalan beruntun. Hasil memuat `local_corpus_partial` / `local_corpus_unavailable` (catatan di
  UI & PDF).
- Embedding dokumen dijalankan PARALEL dengan fase identitas/luas (terikat-jaringan).
- Semaphore konkurensi embedding (`EMBED_MAX_CONCURRENCY`=2) untuk jalur massal dan jalur cepat
  TERPISAH (uji pertama menunjukkan jalur massal bisa membuat jalur cepat kelaparan).
- Fase semantik memakai jalur cepat + tenggat sungguhan (sebelumnya satu batch bisa melewati tenggat).
- Setelan: `LOCAL_EMBED_BUDGET_SECONDS`=150, `LOCAL_EMBED_CALL_TIMEOUT`=60, `LOCAL_EMBED_BATCH`=8.

Diukur di produksi (paper PLOS utuh, lewati-pencarian-luas aktif):

| Kondisi | Total | Korpus lokal |
|---|---|---|
| Sebelum (job nyata, berebut) | 452-1.171 dtk | hilang, 374-389 dtk terbuang |
| Normal, tanpa beban lain | **45 dtk** (sebelumnya ~109) | terperiksa, `embed_wait` 0 dtk |
| 1 job embedding pengganggu | 78 dtk | terperiksa |
| 2 job pengganggu (server jenuh penuh) | 81 dtk | **tetap hilang**, tapi gagal cepat + catatan |

**Akar masalah ditemukan dan diperbaiki (2026-11-25).** Layanan `ollama-embed` (:11437) memuat bge-m3
hanya 0,6 dari 1,24 GB di VRAM (sisanya CPU), `NUM_PARALLEL=1`, dan berada di slice CPU berbatas 50%
sementara host ber-load 50 dari 64 inti; GPU 0 penuh 92% oleh pengguna lain, padahal GPU 1 hampir
kosong (7,8 dari 45 GB). Layanan `ollama-gpu1` (:11436, GPU 1 saja) memuat bge-m3 penuh di GPU.
Diukur: 16 jendela x 2000 karakter **76 dtk (:11437) vs 0,9 dtk (:11436, setelah muat 24 dtk)**;
`embed_chunks` 20 potongan 29,8 dtk -> 0,3 dtk. Vektor kedua server kompatibel (cosine 0,99999,
dim 1024), jadi indeks korpus tetap valid (uji: 32 sumber korpus ditemukan).

Perubahan (hanya `backend/.env`, tidak masuk git): `OLLAMA_EMBED_BASE_URL=http://127.0.0.1:11436`
dan `OLLAMA_EMBED_KEEP_ALIVE=5m` (WAJIB: nilai lama `server` mengikuti `KEEP_ALIVE=0` milik :11436 dan
membuat model dimuat ulang 24 dtk tiap panggilan). Model dimuat saat dipakai dan dilepas setelah 5
menit idle (sesuai preferensi tanpa-pin). Rollback: kembalikan kedua nilai (`:11437`, `server`).
Layanan `ollama-embed` milik pengguna lain TIDAK disentuh. Risiko: :11436 dipakai bersama
(`MAX_LOADED_MODELS=2`); bila model pengguna lain mengusir bge-m3, panggilan pertama berikutnya
lambat sekali lalu normal, dan turun-mutu yang ditambahkan PR #123/#124 tetap melindungi job.

Batas jujur: bila server embedding jenuh penuh, korpus lokal tetap tak terjangkau; yang berubah
hanya kerugiannya (81 dtk, bukan 6+ menit) dan pengguna diberi tahu. Setelah pindah ke GPU 1,
kondisi jenuh jauh lebih jarang karena embedding ~100x lebih cepat.

### Bot Telegram: /cek tidak lagi memblokir

Perintah teks berat berjalan di thread (maks. 3 serempak), /cek langsung dibalas "Memeriksa..." dan
memakai timeout 1.500 dtk; /ping dkk. tetap dijawab selama pemeriksaan. Sebelumnya loop bot
sekuensial sehingga satu /cek menahan semua perintah ~2 menit.

### Panel admin (browser, produksi)

Admin biasa: hanya tab Pengguna, tombol "+ Tambah" hanya pada pengguna biasa (tidak pada diri
sendiri/admin/demo), badge "Anda"; menambah token via UI berhasil dan tercatat di Log Tindakan.
Super Admin: 4 tab (Aktivitas, Pengguna, Log Tindakan, Pengaturan). Akun uji sudah dihapus.
Catatan: alat browser sulit mengeklik tombol karena animasi (perlu `force`), bukan bug aplikasi.

### Bot Telegram

Semua perintah diuji (help, whoami, ping, status, hitung, grammar, parafrase, humanize, cek,
perintah tak dikenal, secret salah, services/logs). `/cek` memakan 83-106 dtk (batas bot 180 dtk);
timeout & galat HTTP kini dijawab dengan pesan jelas (402/401/403/413/429/503). Teks panjang
sebaiknya lewat situs.


## Hasil 2026-11-21

- **semantic_match kosong**: akarnya teks hasil ekstraksi PDF yang dibungkus per baris. Kalimat
  terbelah, jendela "dua kalimat" menjadi serpihan (86, bukan 36), deteksi None. Perbaikan `_unwrap`
  (sambung baris tunggal). Sebelum None, sesudah 97,2% pada PDF dan kandidat yang sama; kontrol
  negatif (paper lain, topik sama, terbungkus PDF) tetap tidak ditandai.
- **Banner salah (Springer)**: entri daftar pustaka dianggap "halaman depan" karena potongan naskah
  tak memuat judul bab References, sehingga paper yang hanya DIKUTIP dituduh (kecocokan teks 0,0%).
  Zona judul 5000 -> 2500 karakter, dan banner berdasar judul wajib terbukti (>=5% isi dokumen
  dijelaskan, ATAU >=20% teks sumber termuat, ATAU teks penuh OA). BMC (DOI sendiri) tetap berbanner.
- **MDPI**: paper asli ada di antara 381 kandidat (peringkat 4 menurut kata abstrak) tetapi tak
  lolos gerbang unduhan karena naskah tanpa abstrak. Jalur cadangan: <=8 kandidat sepokok diunduh
  teks penuhnya. MDPI 3,8% -> 100%; PLOS/IEEE tetap 100%.

### Hasil uji penerbit (1 paper per penerbit, tanpa judul/abstrak)

| Penerbit | Hasil |
|---|---|
| PLOS, IEEE, Copernicus, Nature | terdeteksi 100% |
| BMC | 100% (DOI sendiri); hasil lama "miss" = unduhan teks penuh tak stabil |
| MDPI | 100% setelah PR #113 (sebelumnya 3,8%) |
| Springer | dengan judul/abstrak: ketemu; tanpa judul: 3/5 (lihat "Jangkauan identitas") |
| Frontiers | 6/6 ketemu pada uji ulang sampel acak (tanpa judul) |
| Taylor & Francis | **diblokir penerbit** (HTTP 403, hanya 122 karakter); tak bisa diatasi secara sah |
| Elsevier, Wiley, SAGE | tak teruji: teks penuh tak bisa diunduh untuk 4 paper pertama |

Batas yang tersisa (bukan bug kode): penerbit yang memblokir bot, dan paper yang tak terjangkau
pencarian kandidat (Frontiers, Springer).

## Keamanan & auth (2026-11-20)

### 1. `SESSION_SECRET` produksi — SELESAI (2026-11-24)

Sebelumnya produksi memakai kunci bawaan yang tertulis di kode, sehingga cookie sesi (termasuk
Super Admin) bisa dipalsukan. Kunci acak sudah diset di `backend/.env` dan backend + bot direstart.
Terverifikasi: cookie yang dipalsukan dengan kunci bawaan ditolak (`authenticated: false`, layanan
401), sesi sah Super Admin dan panel admin berfungsi, bot (token internal) 200 / tanpa token 401,
`/health/providers` -> `session_secret_default: false`, peringatan CRITICAL tak muncul lagi.
Catatan: percobaan pertama user gagal karena barisnya tidak tersimpan di `.env`; selalu verifikasi
dengan `grep -c '^SESSION_SECRET=.' backend/.env` (tanpa menampilkan nilainya).

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

- **Dokumen yang seluruhnya diparafrase**: kini ada deteksi semantik (embedding bge-m3 vs teks penuh
  kandidat OA) sebagai INDIKASI, tidak masuk Similarity Index. Hanya bekerja bila paper sumber
  ditemukan dan teks penuhnya terbuka; bergantung pada kecepatan server embedding bersama.
- **Paper berbayar / diblokir penerbit**: teks penuh tak bisa diambil secara sah.
- **Mesin web SearXNG** rapuh (Brave/DuckDuckGo/Startpage sering terblokir); layanan itu dipakai
  bersama, jangan diuji berat. Bukan pengganti OpenAlex.
- Ambang banner "paper terbit" = ≥ 70% isi dokumen cocok dengan satu sumber teks penuh OA
  (heuristik). Dokumen yang menyalin hampir seluruh satu paper juga mendapat banner;
  catatan netral sudah ditampilkan.

## Opsional / diamati

### 9. Peringatan lint lama — SELESAI (2026-11-25)

- Backend: ruff 0 error. Frontend: eslint 0 error / 0 warning; aturan `react-hooks/set-state-in-effect`
  kembali ke `error` (TopNav & TokenEditor ditulis ulang; enam efek fetch/hidrasi-saat-mount diberi
  pengecualian per-baris beralasan).

### 10. Baris pengguna demo ganda — SELESAI

Tujuh baris demo tak terpakai dihapus (13 -> 6). Penyebab ditemukan (2026-11-25): `create_demo_user()`
versi awal melakukan `INSERT` tanpa upsert, dan `google_sub` NULL tidak kena unique index (NULL tak
dianggap sama di Postgres), sehingga tiap demo-login membuat baris baru. Endpoint `/auth/demo-login`
sudah tidak ada di kode sekarang, jadi tidak bisa terulang. Enam baris tersisa (id 1,2,3,4,7,13)
dibiarkan karena sebagian memuat riwayat lama; id 2 dipakai untuk uji.

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
| `SESSION_SECRET` | acak 64 hex (sudah diset) | Jangan di-commit; mengganti = semua pengguna login ulang |

## Pemantauan

- `GET /health/providers` memuat `rate_limited_today` (jumlah HTTP 429 per penyedia hari ini)
  dan `openalex_budget_exhausted`.
- Hasil tiap job memuat `online_openalex_calls`, `online_rate_limited`, `online_budget_exhausted`,
  dan `online_timings` (detik per fase).
- Setelan baru: `ONLINE_TOTAL_BUDGET_SECONDS` (bawaan 1140) = anggaran total job;
  `ONLINE_SKIP_BROAD_COVERAGE` (bawaan 90, 0 = nonaktif) = ambang melewati pencarian luas.
