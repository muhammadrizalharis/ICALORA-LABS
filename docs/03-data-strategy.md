# 03 — Strategi Data (Korpus & Dataset Sendiri)

Prinsip: **membangun sumber daya sendiri untuk ICALORA-LABS**, hanya dari sumber yang **lisensinya mengizinkan penyimpanan & penggunaan ulang**. Tidak mengambil dari proyek lain, dan **tidak scraping konten berbayar**.

> ⚠️ Pengingat penting: **"bisa dibaca publik" ≠ "bebas hak cipta"**. Yang menentukan adalah **lisensi**. Lihat [06-legal-compliance.md](./06-legal-compliance.md).

---

## A. Korpus untuk Plagiarism Checker

### Sumber legal (lisensi reuse)

| Sumber | Isi | Lisensi | Volume |
|---|---|---|---|
| **OpenAlex** | Metadata + abstrak ~250jt karya | CC0 (public domain) | Sangat besar |
| **PMC Open Access Subset** | Full-text artikel biomedis | CC-BY / CC-BY-NC | Jutaan |
| **DOAJ** | Direktori + link jurnal open access | Bervariasi (cek per-artikel) | Jutaan |
| **CORE.ac.uk** | Agregasi full-text open access | Bervariasi (cek per-artikel) | Puluhan juta |
| **arXiv** | Preprint sains | Bervariasi per-paper (filter!) | Jutaan |
| **Common Crawl** | Web publik | Data publik | Masif |

### Pipeline pengolahan

```
1. INGEST      → unduh via API resmi (bukan scraping)
2. FILTER      → hanya simpan item dengan lisensi reuse-friendly
3. CLEAN       → ekstrak teks, buang boilerplate, normalisasi
4. SEGMENT     → pecah jadi kalimat & paragraf
5. FINGERPRINT → MinHash / SimHash (deteksi salinan & near-dup)
6. EMBED       → vektor semantik (deteksi parafrase)
7. INDEX       → simpan ke MinHash index + vector DB
8. UPDATE      → jadwal incremental (berkala)
```

### Catatan desain
- Simpan **metadata lisensi** per dokumen (untuk atribusi & audit).
- Simpan **hash + embedding**, full-text di object storage.
- Mulai dari **domain terfokus** (misal: subset bidang tertentu) agar MVP cepat, lalu skalakan.

---

## B. Dataset untuk AI Detector

Dibangun sendiri — pasangan teks **manusia vs AI**.

| Kelas | Sumber |
|---|---|
| **Teks manusia** | Korpus open-access **pra-2020** (sebelum era LLM populer) + tulisan publik berlisensi |
| **Teks AI** | Generate sendiri memakai beberapa model berbeda, berbagai gaya & topik |

### Pipeline
```
1. Kumpulkan teks manusia (berlabel, legal)
2. Generate teks AI (multi-model, multi-prompt) → beri label
3. Ekstrak fitur: perplexity, burstiness, panjang kalimat, dll.
4. Latih classifier (fine-tune model open-source, mis. RoBERTa)
5. Validasi: akurasi, false-positive rate (SANGAT penting)
6. Kalibrasi ambang + tampilkan confidence + disclaimer
```

> ⚠️ **Wajib jujur:** AI detector tidak pernah 100% akurat. Selalu tampilkan tingkat keyakinan + disclaimer agar tidak menuduh orang secara keliru.

---

## C. Dataset untuk Authorship (Stylometry)

- Fitur gaya: distribusi kata fungsi (function words), panjang kalimat, n-gram karakter, kekayaan kosakata.
- Dataset: kumpulan tulisan berlabel penulis (dari sumber open-access) untuk melatih & menguji pembanding gaya.

---

## D. Penyimpanan & Skala

| Komponen | Teknologi | Untuk |
|---|---|---|
| Full-text korpus | Object storage (MinIO/S3) | Teks mentah & bersih |
| Fingerprint | Tabel MinHash (Postgres/khusus) | Pencarian exact/near-dup cepat |
| Embedding | pgvector / Qdrant | Semantic/parafrase search |
| Metadata | PostgreSQL | Lisensi, sumber, DOI, dsb. |

### Strategi bertahap
1. **MVP korpus kecil** (ratusan ribu dokumen, 1 bidang) → buktikan pipeline.
2. **Skala menengah** (jutaan) → tambah bidang.
3. **Skala besar** (puluhan juta) → optimasi index & biaya storage.
