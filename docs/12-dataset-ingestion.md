# 12 — Ingest Dataset (Korpus) di Latar Belakang

Dokumen ini menjelaskan cara ICALORA-LABS membangun korpusnya sendiri secara
**otomatis, di latar belakang, resumable**, dan **hemat disk**.

> Prinsip: unduh **penuh** (cakupan semua dokumen), **proses streaming** per batch,
> simpan **ringkas & terkompresi**. Snapshot mentah tidak pernah mendarat utuh di disk.

---

## A. Arsitektur penyimpanan 3 lapis

```
TIER 1 — HOT  (WAJIB lokal: Postgres)   metadata + MinHash + embedding(kuantisasi)
              kecil (GB), cepat (ms). Inti mesin deteksi.
TIER 2 — WARM (object storage lokal)    full-text terkompresi (zstd), on-demand
              untuk menampilkan kalimat sumber di laporan.
TIER 3 — COLD (Drive via rclone, opsi)  arsip snapshot mentah + cadangan DB.
              lambat = tak masalah (jarang diakses).
```

Mesin pencari (LSH MinHash + similarity vektor) **harus** di Tier 1 — Google Drive
tidak bisa jadi database (latensi detik + tak bisa query vektor). Tier 1 sudah
sangat kecil berkat representasi ringkas, jadi server tidak bengkak.

### Estimasi ukuran hot tier

| Dokumen | metadata+MinHash+embedding |
|---|---|
| 1 juta | ~1.3 GB |
| 10 juta | ~13 GB |
| 100 juta | ~130 GB |

Pengendali utama di skala besar = **embedding**. Gunakan **kuantisasi** (halfvec/int8/
binary), bukan pindah ke Drive. Binary → 100 juta embedding ≈ 13 GB.

---

## B. Sumber & status

| Sumber | Key? | Metode | Status |
|---|---|---|---|
| **OpenAlex** | ❌ | Snapshot S3 anonim (`s3://openalex/data/jsonl/works`) | ✅ aktif |
| PMC Open Access | ❌ | AWS Open Data (full-text CC-BY) | ⏳ berikutnya |
| Crossref | email | REST (metadata) | ⏳ |
| CORE.ac.uk | API key | REST / dump | ⏳ (perlu key) |
| Semantic Scholar | API key | Datasets API | ⏳ (perlu key) |

> ⚠️ OpenAlex **REST API** kini butuh API key gratis untuk *cursor paging*
> (paging biasa dibatasi 10.000). Karena itu kita pakai **snapshot S3** yang
> **tanpa key** dan memang dirancang untuk bulk.

### Kunci API (opsional, gratis) — untuk membuka sumber tambahan
Isi di `backend/.env` (jangan commit):
```
CORE_API_KEY=...              # daftar: https://core.ac.uk/services/api
SEMANTIC_SCHOLAR_API_KEY=...  # minta: https://www.semanticscholar.org/product/api
NCBI_API_KEY=...              # dari akun NCBI (naikkan limit PMC/PubMed)
CONTACT_EMAIL=...             # mailto polite-pool (OpenAlex/Crossref REST)
```

---

## C. Pipeline OpenAlex (aktif)

```
list part files  s3://openalex/data/jsonl/works/updated_date=*/part_*.gz  (terbaru dulu)
  → stream .gz (unduh-saat-baca, tanpa file di disk)
  → per record: rekonstruksi abstrak dari abstract_inverted_index
  → filter (ada abstrak, bukan paratext/retracted)
  → MinHash 128-perm  +  metrik teks
  → simpan batch: corpus_documents (teks zstd) + corpus_fingerprints
```

**Resumable:** `ingest_jobs.cursor` menyimpan key part terakhir yang selesai.
Jika terputus/di-restart, worker melewati part yang sudah selesai. Idempoten via
`ON CONFLICT (source, external_id) DO NOTHING`.

### Menjalankan (latar belakang)
```bash
cd backend && . .venv/bin/activate
python -u -m app.ingest.openalex --target 1000000 > .logs/ingest_openalex.log 2>&1 &
```

### Memantau
```bash
curl -s http://127.0.0.1:58010/ingest/status | python3 -m json.tool
# atau pantau file .logs/ingest_openalex.log
```

### Menghentikan dengan aman
Kirim SIGTERM/SIGINT ke PID worker → status jadi `paused`, cursor tersimpan,
lanjut otomatis saat dijalankan lagi.

---

## D. Skema tabel (lihat `app/ingest/schema.sql`)

- `corpus_documents` — metadata + `text_zstd` (abstrak terkompresi) + `has_embedding`.
- `corpus_fingerprints` — MinHash (bytea, 128×uint64).
- `corpus_embeddings` — `vector(1024)` (bge-m3), diisi Tahap-2 di GPU.
- `ingest_jobs` — status resumable per sumber.

---

## E. Tahap-2 — Embedding di GPU (menyusul)

Dokumen tanpa embedding (`has_embedding=false`) diproses batch memakai **GPU**
(bge-m3 via Ollama bersama) lalu disimpan ke `corpus_embeddings`. Dipisah dari
Tahap-1 agar cakupan cepat terbentuk dulu dan GPU dipakai terjadwal/terbatas
(tidak mengganggu proses pengguna lain di server).
