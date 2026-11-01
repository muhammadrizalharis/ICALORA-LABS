# 11 — Spesifikasi Report Viewer (Similarity, Writing, AI)

Dokumen ini menetapkan desain **laporan hasil** ICALORA-LABS, terinspirasi dari
praktik terbaik industri (Turnitin, Grammarly) namun dengan **desain, nama elemen,
skema warna, dan ikon yang ORISINAL** milik ICALORA-LABS — bukan salinan identik —
agar aman dari masalah merek & hak cipta UI.

> Referensi analisis: `docs/report.pdf` (gaya laporan Writing/Grammarly) dan
> `docs/TURNITIN.pdf` (gaya laporan Similarity/Integrity). Kedua PDF hanya acuan
> internal, tidak dipublikasikan ulang.

---

## A. Similarity Report (fitur Plagiarism Checker)

Struktur 3 bagian: **Overview → Daftar Sumber → Tampilan Dokumen**.

### A.1 Halaman Overview
- **Skor besar**: `NN% Kemiripan Keseluruhan` (angka dominan, gauge/lingkaran).
  - Deskripsi: "Total gabungan semua kecocokan, termasuk sumber yang tumpang tindih."
- **Filter aktif** (yang dikecualikan): Bibliografi, Teks dalam kutipan.
- **Kelompok Kecocokan (Match Groups)** — panel kiri, tiap baris: ikon berwarna + jumlah + %:
  | Kelompok | Arti | Warna (orisinal ICALORA) |
  |----------|------|--------------------------|
  | Tidak Disitasi/Dikutip | cocok tanpa sitasi & tanpa tanda kutip | merah |
  | Kutipan Hilang | mirip sumber tapi tak ada tanda kutip | oranye |
  | Sitasi Hilang | ada tanda kutip, tanpa sitasi | kuning |
  | Disitasi & Dikutip | ada sitasi + tanda kutip | hijau |
- **Sumber Teratas (Top Sources)** — panel kanan, ringkasan per kategori %:
  - Sumber Internet, Publikasi, Karya Terkirim (paper mahasiswa/pengguna lain).

### A.2 Daftar Sumber Berperingkat
Tiap sumber satu baris:
- **Badge nomor** (lingkaran berwarna, warna di-rotate per peringkat).
- **Tag tipe**: `Internet` / `Publikasi` / `Karya Terkirim` (pil berwarna).
- **Nama sumber** (domain atau judul/penulis) + **persentase** di kanan.

### A.3 Tampilan Dokumen (Document View)
- Render teks asli pengguna (boleh 1 atau 2 kolom).
- **Highlight** pada rentang teks yang cocok, warna mengikuti sumbernya.
- **Badge nomor** di margin kiri, sejajar baris highlight → klik untuk lompat ke sumber.
- **Panel sumber** samping/popover: cuplikan sumber + tautan + % kecocokan rentang itu.
- Interaksi: klik highlight → sorot sumber terkait; toggle filter (bibliografi/kutipan).

### A.4 Model data (ringkas)
```
SimilarityReport
  submissionId, overallPercent, filters{bibliography, quoted}
  matchGroups[]: {type, count, percent}
  topCategories[]: {type, percent}
  sources[]: {rank, type, name, url?, percent}
  matches[]: {startOffset, endOffset, sourceRank, snippet}
```

---

## B. Writing Report (Grammar Checker & sejenisnya)

- **Metrik Umum**: jumlah karakter, kata, kalimat, estimasi waktu baca & bicara.
- **Skor**: gauge melingkar 0–100 + "lebih baik dari X% teks".
- **Masalah Penulisan**: total `Issues left`, `Critical`, `Advanced`.
- **Rincian kategori**: mis. Kejelasan (Clarity), Ketepatan (Correctness),
  Keterlibatan (Engagement), Penyampaian (Delivery) — tiap kategori ber-sub-hitung.
- **Bagian Plagiarisme**: tautan silang ke Similarity Report (jika sudah dicek).

### Model data
```
WritingReport
  metrics{characters, words, sentences, readingTime, speakingTime}
  score, betterThanPercent
  issues{total, critical, advanced}
  categories[]: {name, count, subitems[]: {label, count}}
```

---

## C. AI Writing Report (AI Detector)

- **Skor AI**: `NN% kemungkinan dihasilkan AI` + gauge + **disclaimer akurasi** wajib
  ("indikatif, bukan bukti pasti; dapat salah pada penulis non-native").
- **Highlight** kalimat/paragraf yang terindikasi AI (gradasi keyakinan).
- **Penjelasan**: sinyal yang dipakai (perplexity, burstiness, stylometry) — ringkas.

### Model data
```
AIReport
  aiLikelihoodPercent, confidenceBand
  segments[]: {startOffset, endOffset, aiProbability}
  disclaimer
```

---

## D. Prinsip desain & kepatuhan

1. **Orisinal** — logo, nama elemen, palet warna, dan ikon dibuat sendiri untuk
   ICALORA-LABS; tidak memakai merek/aset Turnitin atau Grammarly.
2. **Konsisten** dengan komponen UI shell (shadcn/ui + Tailwind, lihat docs/05).
3. **Aksesibel** — warna highlight punya kontras cukup + label teks (bukan warna saja).
4. **Ekspor** — semua laporan dapat diekspor ke PDF (dibuat sendiri, mis. via jsPDF/server render).
5. **Disclaimer akurasi** wajib pada AI Detector (lihat docs/06 kepatuhan).

Lihat juga: [docs/01 — Fitur](01-features.md), [docs/02 — Arsitektur](02-architecture.md),
[docs/06 — Legal & Kepatuhan](06-legal-compliance.md).
