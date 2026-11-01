# 10 — Strategi Penyimpanan Korpus (Hemat & Skalabel)

Korpus ICALORA-LABS akan berisi **ratusan ribu hingga jutaan** dokumen akademik.
Jika disimpan naif (semua teks/PDF mentah), penyimpanan meledak jadi puluhan–ratusan GB.
Dokumen ini menetapkan strategi agar penyimpanan **seminimal mungkin** tanpa mengorbankan
akurasi deteksi.

## Prinsip inti

> **Jangan simpan "file"-nya. Simpan representasi yang dibutuhkan tiap fitur.**

Tiga fitur utama butuh data berbeda — jadi tidak perlu menyimpan teks lengkap untuk semuanya:

| Fitur | Data yang dibutuhkan | Ukuran / dokumen |
|-------|----------------------|------------------|
| Plagiarisme copy / near-copy | **Fingerprint** (MinHash/SimHash dari shingle) | ~0.5 KB |
| Plagiarisme parafrase / semantik | **Embedding vektor** (terkuantisasi) | 0.3–1.5 KB |
| AI detector | **Model classifier** + fitur perplexity (bukan korpus) | ~0 / dokumen |
| Render kutipan yang cocok | **Teks mentah** terkompресi, diambil **on-demand** | ~10 KB |

## Arsitektur penyimpanan berlapis

```
┌─────────────────────────────────────────────────────────────┐
│ Tier 1 — METADATA (PostgreSQL)                              │
│   DOI, judul, penulis, lisensi, URL sumber, tanggal         │
│   TOAST/lz4 otomatis. ~0.5 KB/dok                           │
├─────────────────────────────────────────────────────────────┤
│ Tier 2 — FINGERPRINT (PostgreSQL / index khusus)           │
│   MinHash 128 perm (512 B) atau SimHash 64-bit (8 B)        │
│   Inti deteksi copy/near-copy. Sangat ringan.               │
├─────────────────────────────────────────────────────────────┤
│ Tier 3 — EMBEDDING (pgvector / Qdrant)                     │
│   Model 384-dim, kuantisasi int8 (384 B) atau binary (48 B) │
│   Coarse-to-fine: binary utk kandidat → int8/float utk rerank│
├─────────────────────────────────────────────────────────────┤
│ Tier 4 — TEKS MENTAH (SeaweedFS, zstd)                     │
│   Hanya diambil saat ada match utk ditampilkan.             │
│   Opsional 0 GB: fetch ulang dari URL open-access.          │
└─────────────────────────────────────────────────────────────┘
```

## Estimasi nyata — 500.000 paper

Rata-rata paper ≈ 6.000 kata ≈ **40 KB teks mentah**.
Naif: 500K × 40KB = **20 GB teks saja** (belum vektor/PDF).

Dengan strategi berlapis:

| Komponen | Teknik | Ukuran |
|----------|--------|--------|
| Metadata | Postgres + TOAST | ~250 MB |
| Fingerprint | MinHash 512 B/dok | ~256 MB |
| Teks mentah | zstd ~4x di SeaweedFS (atau 0 jika fetch-on-demand) | ~5 GB (atau 0) |
| Embedding | 384-dim int8, ~20 chunk/dok | ~4 GB + index |
| **TOTAL** | | **~8–12 GB** |

> vs ~50+ GB kalau naif. Muat nyaman di disk server (sisa ~197 GB) dan tetap aman
> saat skala ke jutaan dokumen.

## Format file: JANGAN pakai ZIP

| Opsi | Rasio teks | Verdict |
|------|-----------|---------|
| ❌ ZIP/gzip (DEFLATE) | ~3x | Tua, per-file, lambat |
| ✅ **zstd** (lvl 19) | ~4–4.5x | **Terbaik**: cepat + rasio bagus + streaming |
| ✅ **Parquet + zstd** | ~4–5x | Terbaik untuk batch kolumnar (ingest korpus) |
| ✅ **brotli** | ~4.5–5x | Rasio sedikit lebih baik, lebih lambat |

Catatan: **PostgreSQL TOAST** otomatis mengompресi kolom teks panjang (lz4) — gratis.

## Kuantisasi vektor (penghemat terbesar)

Embedding adalah komponen paling "berat". Tekan dengan:

| Metode | Ukuran (768-dim) | Catatan |
|--------|------------------|---------|
| float32 (default) | 3072 B | Baseline, boros |
| float16 / `halfvec` | 1536 B | Nyaris tanpa kehilangan akurasi |
| int8 (scalar quant) | 768 B | ~1% drop recall, 4x hemat |
| binary (1 bit/dim) | 96 B | Untuk kandidat kasar, lalu re-rank |

Plus:
- Gunakan model **384-dim** (mis. all-MiniLM) daripada 768-dim → langsung 2x hemat.
- **Matryoshka embeddings** — bisa dipotong ke 256/128-dim tanpa latih ulang.

## Teknik tambahan

- **Deduplikasi sebelum ingest** — korpus open-access penuh duplikat (preprint + versi
  terbit). Near-dedup pakai MinHash memangkas 20–40% **sebelum** apa pun disimpan.
- **Buang PDF asli** — simpan hanya teks ternormalisasi (PDF 10–20x lebih besar dari teksnya).
- **Chunking hemat** — embed per-seksi, bukan per-kalimat, agar jumlah vektor terkendali.
- **Fetch-on-demand** — karena sumber legal & open-access, teks penuh bisa diambil ulang
  via DOI/URL saat dibutuhkan, sehingga Tier 4 bisa ~0 GB.

## Keputusan

1. Deteksi copy/near-copy → **MinHash/SimHash** (Tier 2), bukan vektor.
2. Deteksi semantik/parafrase → **embedding 384-dim + kuantisasi int8**, coarse-to-fine.
3. Teks mentah → **zstd** di SeaweedFS, diambil on-demand; PDF asli tidak disimpan.
4. Batch korpus / pipeline ingest → **Parquet + zstd**.
5. Dedup wajib di tahap ingest.

Lihat juga: [docs/03 — Strategi Data](03-data-strategy.md), [docs/08 — Database & Keamanan](08-database-security.md).
