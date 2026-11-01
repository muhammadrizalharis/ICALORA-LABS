# 01 — Peta Fitur ICALORA-LABS

Platform ICALORA-LABS meniru cakupan fitur toolkit akademik modern (seperti pada referensi gambar), terdiri dari **13 fitur**. Dikelompokkan berdasarkan tingkat kesulitan & kebutuhan sumber daya.

---

## Tabel Fitur

| # | Fitur | Inti Teknis | Kesulitan | Korpus/Model Sendiri? |
|---|---|---|---|---|
| 1 | **AI Chat** | LLM + antarmuka chat | 🟢 Mudah | ❌ |
| 2 | **Grammar Checker** | Grammar model / LLM | 🟢 Mudah | ❌ |
| 3 | **Paraphraser** | LLM rewrite | 🟢 Mudah | ❌ |
| 4 | **AI Rewriter** | LLM rewrite (varian gaya) | 🟢 Mudah | ❌ |
| 5 | **Humanizer** | LLM + penyesuaian gaya | 🟡 Sedang | ❌ |
| 6 | **AI Grader** | LLM + rubrik penilaian | 🟡 Sedang | ❌ |
| 7 | **Word Count** | Statistik teks | 🟢 Sangat mudah | ❌ |
| 8 | **Citation Finder** | API metadata (Crossref/OpenAlex) | 🟡 Sedang | ⚠️ API publik |
| 9 | **Reader Reactions** | LLM simulasi persepsi pembaca | 🟢 Mudah | ❌ |
| 10 | **Resume Builder** | Template + LLM | 🟢 Mudah | ❌ |
| 11 | **AI Detector** | Classifier + fitur statistik | 🔴 Sulit | ✅ Ya (dataset latih) |
| 12 | **Authorship** | Stylometry / verifikasi penulis | 🔴 Sulit | ✅ Ya |
| 13 | **Plagiarism Checker** | Index korpus + similarity | 🔴 Sangat berat | ✅✅ Ya (korpus besar) |

---

## Pengelompokan Strategis

### 🟢 Kelompok A — Fitur Ringan (cepat jalan, pakai LLM)
Word Count, Grammar, Paraphraser, Rewriter, Humanizer, AI Chat, AI Grader, Reader Reactions, Resume Builder.
→ **9 fitur** bisa aktif di fase awal tanpa korpus sendiri.

### 🟡 Kelompok B — Integrasi API
Citation Finder → Crossref, OpenAlex, DataCite (gratis & legal).

### 🔴 Kelompok C — Fitur Berat (butuh sumber daya sendiri)
Plagiarism Checker, AI Detector, Authorship.
→ Fokus utama kerja keras; perlu korpus + model yang dibangun khusus (lihat [03-data-strategy.md](./03-data-strategy.md)).

---

## Spesifikasi Ringkas per Fitur Berat

### Plagiarism Checker
- **Input:** dokumen (PDF/DOCX/teks).
- **Proses:** ekstraksi teks → segmentasi (kalimat/paragraf) → pencocokan ke korpus via (a) **MinHash/SimHash** untuk salinan persis/near-duplicate dan (b) **semantic embedding** untuk parafrase.
- **Output:** **Similarity Report** → persentase keseluruhan + highlight warna di teks + daftar sumber yang cocok + persentase per sumber.

### AI Detector
- **Input:** teks.
- **Proses:** fitur statistik (perplexity, burstiness) + classifier terlatih (fine-tune model open-source).
- **Output:** probabilitas "ditulis AI" + highlight per kalimat + **disclaimer akurasi wajib**.

### Authorship (Stylometry)
- **Input:** beberapa sampel tulisan.
- **Proses:** ekstraksi fitur gaya (panjang kalimat, distribusi kata fungsi, n-gram karakter) → bandingkan konsistensi.
- **Output:** skor kemiripan gaya antar-dokumen / verifikasi penulis.

---

## Prioritas Pembangunan
Lihat urutan lengkap di [04-roadmap.md](./04-roadmap.md).
