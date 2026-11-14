# Rekomendasi Teknis, Kritik, dan Roadmap Implementasi ICALORA

> Prinsip utama: jangan mengejar jumlah model. Prioritaskan generalisasi
> lintas-generator, false positive yang rendah, kalibrasi skor, evaluasi
> bebas data leakage, dan keputusan `UNCERTAIN` ketika bukti tidak
> cukup. AI detector tidak dapat membuktikan identitas penulis atau
> memastikan secara mutlak bahwa teks dibuat AI.

------------------------------------------------------------------------

# 1. Ringkasan kondisi ICALORA

  --------------------------------------------------------------------------
  Komponen                   Status yang dilaporkan  Evaluasi dan pekerjaan
                                                     lanjutan
  -------------------------- ----------------------- -----------------------
  Preprocessing, bahasa,     Sekitar 250 kata, batas Bandingkan ukuran dan
  chunking                   paragraf, ID/EN         strategi segmentasi

  Burstiness, TTR, fitur     Model enam fitur        Ablation study dan
  gaya                                               korelasi fitur

  Semantik/kontekstual       BGE-M3 multilingual +   Embedding bukan bukti
                             classifier              asal-usul teks

  Hybrid                     Embedding + fitur + LLM Audit bobot, skala, dan
                             melalui `_blend`        kontribusi

  Skor segmen/agregasi       Peta segmen dan         Definisikan denominator
                             `ai_share` berbasis     dan interpretasi
                             kata                    

  False-positive guard       LLM dinonaktifkan untuk Pertahankan sementara;
                             ID setelah salah        perlu benchmark lebih
                             menandai 12/15 teks     besar
                             manusia                 

  Parafrase/generator        Retraining Qwen/Gemma   Uji generator yang
                             dan data parafrase      tidak dilihat saat
                                                     training

  HUMAN/AI/MIXED/UNCERTAIN   Kategori tersedia       Tetapkan definisi
                                                     operasional dan aturan
                                                     keputusan
  --------------------------------------------------------------------------

## 1.1 Kekurangan utama yang harus diselesaikan

1.  Evaluasi lintas-generator dan test set final.
2.  Probability calibration.
3.  Laporan transparan dan dapat direproduksi.
4.  Penanganan teks pendek.
5.  Ablation study.
6.  Perplexity, entropy, dan zero-shot detection yang benar.
7.  Validasi implementasi Binoculars pada teks input.

## 1.2 Prinsip pengembangan

-   Ukur kontribusi setiap komponen sebelum menambah model.
-   Pisahkan training, validation, calibration, dan test.
-   Jangan memilih threshold berdasarkan test final.
-   Jangan menganggap skor detector sebagai bukti kepengarangan.
-   Utamakan pengendalian false positive pada tulisan manusia.
-   Sediakan kategori uncertain dan insufficient evidence.

------------------------------------------------------------------------

# 2. Audit komponen yang sudah ada

## 2.1 Segmentasi sekitar 250 kata

250 kata layak menjadi baseline, tetapi belum tentu ukuran optimal.

Risiko: - segmen terlalu pendek kehilangan konteks; - segmen terlalu
panjang menyamarkan bagian dengan karakteristik berbeda; - batas
paragraf menghasilkan ukuran segmen tidak seimbang; - overlapping
windows dapat menghitung kata berulang jika agregasi tidak benar.

### Eksperimen ukuran segmen

  Eksperimen       Ukuran
  ------------ ----------
  S1             100 kata
  S2             150 kata
  S3             250 kata
  S4             350 kata
  S5             500 kata

Gunakan dataset dan protokol evaluasi yang sama. Ukur TPR, FPR, Macro
F1, stabilitas skor, waktu inferensi, dan kemampuan menemukan bagian AI
dalam dokumen campuran.

### Bandingkan strategi

1.  **Paragraph-boundary segmentation:** mengutamakan batas paragraf.
2.  **Fixed-window segmentation:** membagi berdasarkan jumlah kata atau
    token.
3.  **Overlapping-window segmentation:** jendela saling tumpang tindih.

Contoh overlap 50 kata:

``` text
Segment 1: kata 1–250
Segment 2: kata 201–450
Segment 3: kata 401–650
Segment 4: kata 601–850
```

Jika memakai overlap, petakan setiap kata ke posisi dokumen asli dan
lakukan deduplikasi sebelum menghitung AI share. Pertahankan 250 kata
sampai hasil eksperimen menunjukkan konfigurasi yang lebih baik.

## 2.2 Model enam fitur linguistik

Lakukan ablation study:

  Eksperimen   Fitur
  ------------ -------------------------------------
  A--F         Masing-masing fitur secara terpisah
  G            Seluruh enam fitur
  H            Enam fitur + BGE-M3

Catat FPR, TPR, precision, recall, Macro F1, AUROC, TPR@FPR, performa
per bahasa, domain, dan generator.

Periksa korelasi antarf fitur. Fitur yang berkorelasi tinggi mungkin
redundan, tetapi jangan menghapusnya tanpa menguji dampaknya. Empat
fitur yang terbukti efektif lebih baik daripada banyak fitur tanpa bukti
peningkatan.

## 2.3 BGE-M3

BGE-M3 adalah model embedding multibahasa, bukan detector asal-usul teks
secara langsung. Dua teks dengan topik sama dapat memiliki embedding
mirip meskipun satu ditulis manusia dan satu dihasilkan AI. Dua teks
manusia dengan topik berbeda dapat memiliki embedding berjauhan.

Rekomendasi: - pertahankan BGE-M3 sebagai representasi semantik; -
gunakan embedding sebagai input classifier yang dilatih dengan data
berlabel; - jangan menafsirkan cosine similarity sebagai bukti AI; - uji
kontribusinya melalui ablation study; - dokumentasikan checkpoint,
tokenizer, pooling, normalisasi, dan panjang input; - bandingkan dense
embedding dengan fitur lain hanya jika ada hipotesis dan evaluasi yang
jelas.

Model card: https://huggingface.co/BAAI/bge-m3

## 2.4 LLM dalam hybrid detection

LLM dapat menganggap teks formal, terstruktur, atau generik sebagai
AI-like. Karakteristik tersebut juga lazim dalam tulisan akademik
manusia.

Rekomendasi: - posisikan LLM sebagai komponen sekunder; - jangan
menjadikannya penentu utama; - tetap nonaktifkan untuk bahasa Indonesia
sampai lolos benchmark false positive; - pisahkan output LLM dari skor
detector utama; - gunakan LLM untuk membantu menyusun penjelasan, bukan
menyatakan identitas penulis.

Aktifkan kembali hanya jika evaluasi independen menunjukkan peningkatan
TPR pada FPR yang sama tanpa memperburuk kelompok penting.

------------------------------------------------------------------------

# 3. Prioritas P0 --- Cross-generator evaluation

## 3.1 Mengapa penting?

Jika model dilatih dan diuji menggunakan generator yang sama, model
mungkin mempelajari ciri generator yang sudah dikenal. Ini belum
membuktikan kemampuan mendeteksi generator baru.

Bedakan: - **In-domain:** generator dan domain sudah terwakili dalam
training. - **Out-of-domain:** generator atau domain ditahan dari
training dan tuning.

## 3.2 Rancangan eksperimen

  -----------------------------------------------------------------------
  Eksperimen        Training          Testing           Tujuan
  ----------------- ----------------- ----------------- -----------------
  E1                ChatGPT, Gemini   Data baru dari    Baseline
                                      ChatGPT, Gemini   in-domain

  E2                ChatGPT, Gemini,  Claude            Unseen generator
                    Qwen                                

  E3                Semua kecuali     DeepSeek          Generalisasi
                    DeepSeek                            

  E4                Semua kecuali     Llama             Generalisasi
                    Llama                               

  E5                Generator yang    Generator baru    Robustness
                    tersedia          yang ditahan      
  -----------------------------------------------------------------------

Nama generator di atas merupakan contoh; sesuaikan dengan data yang
benar-benar tersedia. Generator yang ditahan tidak boleh digunakan untuk
training, feature selection, threshold selection, hyperparameter tuning,
checkpoint selection, atau perubahan pipeline.

## 3.3 Cegah data leakage

Jangan membagi baris secara acak jika beberapa teks berasal dari prompt,
artikel sumber, dokumen, atau parafrase yang sama. Kelompokkan sampel
berdasarkan sumber atau kelompok asal sebelum split.

Manifest dataset yang disarankan:

``` text
sample_id
document_id
source_group_id
label
language
domain
generator
prompt_id
generation_date
transformation
split
word_count
```

Gunakan group-based split. Simpan test final yang tidak disentuh sampai
seluruh keputusan pengembangan selesai.

## 3.4 Dua laporan wajib

``` text
IN-DOMAIN
- Generator dikenal saat training.
- Sumber, prompt, dan dokumen tetap dipisahkan.
- Mengukur performa pada distribusi yang dikenal.

OUT-OF-DOMAIN
- Generator atau domain ditahan dari training.
- Tidak digunakan untuk tuning.
- Mengukur kemampuan generalisasi.
```

Jangan menggabungkan hasil keduanya menjadi satu angka tanpa rincian.

------------------------------------------------------------------------

# 4. Prioritas P0 --- Probability calibration

## 4.1 Skor mentah bukan otomatis probabilitas

Jika ICALORA menampilkan `87%`, angka tersebut belum tentu berarti
peluang teks dibuat AI sebesar 87%.

Pisahkan:

  -----------------------------------------------------------------------
  Field                               Makna
  ----------------------------------- -----------------------------------
  `raw_score`                         Skor mentah model

  `calibrated_score`                  Skor setelah kalibrasi

  `decision_confidence`               Informasi keyakinan keputusan
                                      berdasarkan validasi dan kondisi
                                      input
  -----------------------------------------------------------------------

Jangan menyamakan ketiganya.

## 4.2 Metode kalibrasi

Uji: 1. Platt Scaling. 2. Isotonic Regression. 3. Temperature Scaling,
terutama untuk neural network.

Platt Scaling:

\[ P\_{cal}=`\sigma`{=tex}(az+b) \]

`z` adalah skor/logit mentah; `a` dan `b` dipelajari dari calibration
set; `sigma` adalah sigmoid.

Gunakan calibration set terpisah. Jangan mempelajari parameter kalibrasi
dari test final.

## 4.3 Metrik

Laporkan: - Expected Calibration Error (ECE); - Brier Score; - Negative
Log-Likelihood (NLL); - Reliability Diagram.

Kalibrasi memperbaiki kesesuaian skor dengan frekuensi kejadian aktual.
Kalibrasi tidak otomatis memperbaiki kemampuan diskriminasi model.

Contoh interpretasi: jika banyak sampel menerima skor sekitar 80%,
sekitar 80% sampel dalam kelompok tersebut semestinya benar-benar
positif pada distribusi evaluasi yang relevan. Ini harus diuji, bukan
diasumsikan.

------------------------------------------------------------------------

# 5. Prioritas P0 --- TPR pada FPR tertentu

Accuracy saja tidak cukup. Salah menandai tulisan manusia sebagai AI
merupakan risiko utama.

Gunakan: - TPR@FPR 1%; - TPR@FPR 5%; - FPR pada teks manusia
Indonesia; - Macro F1; - precision dan recall; - AUROC; - AUPRC jika
kelas tidak seimbang.

TPR@FPR mengukur tingkat deteksi positif ketika false positive dibatasi
pada tingkat tertentu.

Contoh ilustratif:

  Model     FPR   TPR
  ------- ----- -----
  A          1%   85%
  B          1%   78%
  C          1%   92%

Model C memiliki TPR tertinggi pada FPR yang sama. Angka ini hanya
ilustrasi, bukan target atau hasil ICALORA.

Untuk penggunaan akademik, prioritaskan pengendalian FPR. Lebih baik
sistem menghasilkan `UNCERTAIN` daripada menuduh tulisan manusia tanpa
bukti memadai.

------------------------------------------------------------------------

# 6. Prioritas P0 --- False-positive benchmark bahasa Indonesia

## 6.1 Interpretasi 12 dari 15

Dari 15 teks manusia, 12 salah ditandai sebagai AI:

\[ FPR=`\frac{12}{15}`{=tex}=0.8=80% \]

Ini merupakan sinyal kegagalan yang kuat untuk penggunaan saat ini.
Namun, 80% belum merupakan estimasi FPR populasi yang presisi karena
sampel sangat kecil.

Keputusan menonaktifkan LLM untuk teks Indonesia sampai evaluasi ulang
merupakan tindakan yang masuk akal.

## 6.2 Ukuran benchmark

Panduan perencanaan: - 300 dokumen manusia untuk evaluasi awal; - 1.000
dokumen untuk evaluasi lebih kuat; - 3.000 atau lebih jika ingin
mengevaluasi false positive yang sangat rendah.

Jumlah tersebut bukan jaminan statistik otomatis.

Jika tidak ditemukan false positive, pendekatan sederhana rule of three
memberi batas atas 95% sekitar `3/n`:

    Sampel tanpa false positive   Perkiraan batas atas
  ----------------------------- ----------------------
                            300                     1%
                          1.000                   0,3%
                          3.000                   0,1%

Untuk laporan ilmiah, gunakan interval kepercayaan binomial yang sesuai,
seperti exact binomial atau Wilson, dan jelaskan asumsi independensi
sampel.

## 6.3 Komposisi data manusia

Sertakan: - artikel akademik; - skripsi atau karya ilmiah dengan izin; -
laporan teknis; - tulisan mahasiswa; - tulisan yang diedit
dosen/editor; - teks formal dan informal; - terjemahan manusia; - teks
dengan tata bahasa sangat baik; - teks dengan istilah teknis padat.

Catat provenance dan izin penggunaan data.

------------------------------------------------------------------------

# 7. Prioritas P0 --- Validasi Binoculars

## 7.1 Prinsip kerja

Binoculars adalah metode zero-shot machine-generated text detection yang
membandingkan perilaku probabilistik dua model bahasa yang berkaitan.
Secara konseptual, observer dan performer model digunakan untuk
menghasilkan skor gabungan.

Binoculars bukan sekadar perplexity dari satu model.

Paper: https://proceedings.mlr.press/v235/hans24a.html

## 7.2 Checklist implementasi

### Pasangan model

-   Pastikan pasangan model sesuai implementasi referensi.
-   Verifikasi checkpoint dan arsitektur.
-   Pastikan tokenizer dan konfigurasi sesuai.
-   Pastikan peran observer dan performer benar.
-   Jangan menganggap sembarang kombinasi Qwen dan Gemma otomatis valid.

### Probabilitas input

Pastikan sistem menghitung logits/probabilitas token untuk teks input
melalui forward pass model. Ini berbeda dari mengambil logprobs token
yang baru dihasilkan API generasi.

Periksa implementasi terhadap repository dan konfigurasi resmi
Binoculars. Jangan hanya mengandalkan logprob dari proses generasi
Ollama.

### Threshold

Threshold bahasa Inggris tidak otomatis valid untuk bahasa Indonesia.
Uji pada: - human Indonesia; - AI Indonesia; - human akademik
Indonesia; - AI akademik Indonesia; - teks campuran; - teks parafrase; -
teks yang diedit manusia.

Pilih threshold menggunakan validation set, bukan test final.

### GPU dan resource

Catat: - penggunaan VRAM; - batch size; - waktu inferensi; - antrean; -
model loading/unloading; - precision; - kegagalan out-of-memory.

Jangan menjalankan dua model besar bersamaan tanpa mengukur kebutuhan
memori.

## 7.3 Eksperimen integrasi

Uji secara terpisah: 1. Classifier ICALORA. 2. Binoculars. 3. Kombinasi
keduanya.

Integrasikan permanen hanya jika kombinasi meningkatkan hasil pada test
independen, terutama TPR pada FPR yang sama dan unseen-generator
evaluation.

------------------------------------------------------------------------

# 8. Prioritas P1 --- Token-level probability analysis

Untuk token `w_i`, surprisal:

\[ I(w_i)=-`\log `{=tex}P(w_i\|w\_{\<i}) \]

Rata-rata surprisal:

\[ `\bar `{=tex}I=`\frac{1}{N}`{=tex}`\sum`{=tex}\_{i=1}\^{N}I(w_i) \]

Fitur yang dapat diuji: - mean token log-probability; - variance token
log-probability; - distribusi dan kuantil surprisal; - statistik
entropy; - statistik per kalimat atau segmen.

Perplexity berkaitan langsung dengan rata-rata negative log-likelihood.
Jangan memperlakukan perplexity dan mean surprisal sebagai fitur yang
sepenuhnya independen.

Perhatikan kecocokan bahasa model evaluator, tokenizer, panjang konteks,
special token, dan ukuran input. Fitur probabilistik adalah sinyal
statistik, bukan bukti asal-usul teks.

------------------------------------------------------------------------

# 9. Prioritas P1 --- Document-level consistency

Analisis perubahan karakteristik antarbagiannya: - rata-rata panjang
kalimat; - lexical diversity; - distribusi part-of-speech; -
embedding; - token surprisal; - karakteristik sintaksis.

Perubahan sederhana:

\[ D_i=\|S_i-S\_{i-1}\| \]

`S_i` adalah representasi atau skor segmen ke-i.

Perubahan gaya tidak otomatis berarti pergantian penulis atau penggunaan
AI. Penyebab lain termasuk perpindahan bab, perubahan topik, kutipan,
tabel, dan perubahan tingkat formalitas. Gunakan fitur ini sebagai
sinyal tambahan, bukan keputusan tunggal.

------------------------------------------------------------------------

# 10. Prioritas P2 --- Paragraph structure analysis

Fitur yang dapat diuji:

  Fitur                Fungsi
  -------------------- ------------------------------
  Paragraph length     Panjang paragraf
  Sentence count       Jumlah kalimat
  Opening pattern      Karakteristik pembuka
  Closing pattern      Karakteristik penutup
  Transition density   Frekuensi kata transisi
  Topic continuity     Hubungan topik antarparagraf

Jangan menandai kata "Furthermore", "Moreover", "In addition", atau
"Selain itu" sebagai indikator AI secara langsung. Kata-kata tersebut
juga lazim digunakan manusia. Uji kontribusi fitur paragraf setelah
fitur lain dikontrol.

------------------------------------------------------------------------

# 11. Prioritas P1 --- Mixed-origin detection

Definisikan `MIXED` secara operasional dan bangun dataset dengan
komposisi asal-usul yang diketahui.

  Dataset    Komposisi
  ---------- -------------------
  Mixed-10   10% AI, 90% Human
  Mixed-25   25% AI, 75% Human
  Mixed-50   50% AI, 50% Human
  Mixed-75   75% AI, 25% Human
  Mixed-90   90% AI, 10% Human

Komposisi harus diketahui dari proses pembuatan data, bukan dari hasil
detector.

Uji kemampuan: 1. menemukan segmen AI-like; 2. menemukan segmen
human-like; 3. mengenali perubahan antarsemen; 4. memperkirakan proporsi
kata pada segmen yang ditandai; 5. mengeluarkan uncertain jika bukti
tidak cukup.

Variasikan posisi, panjang, dan jumlah segmen. Jangan hanya menguji pola
separuh pertama AI dan separuh kedua manusia.

------------------------------------------------------------------------

# 12. Definisi AI Share

Jika `ai_share` dihitung dari kata dalam segmen yang ditandai, jangan
menyebutnya persentase kata yang terbukti ditulis AI.

Contoh:

  Segmen      Kata Status
  -------- ------- ------------
  1            250 AI-like
  2            250 Human-like
  3            500 AI-like
  4          1.000 Human-like

\[ AI Flagged Word Share =
`\frac{250+500}{2000}`{=tex}`\times100`{=tex}%=37.5% \]

Interpretasi benar: 37,5% jumlah kata berada pada segmen yang ditandai
AI-like oleh detector. Ini bukan bukti bahwa kata-kata tersebut dibuat
AI.

Field yang disarankan:

``` text
ai_flagged_word_share
ai_flagged_segment_count
human_like_word_share
uncertain_word_share
total_analyzed_words
total_analyzed_segments
```

Dokumentasikan denominator dan perlakuan segmen uncertain. Jika
menggunakan overlapping windows, deduplikasi berdasarkan posisi kata
sebelum agregasi.

------------------------------------------------------------------------

# 13. Ensemble dan score fusion

## 13.1 Jangan merata-ratakan skor tanpa validasi

Sumber sinyal ICALORA: 1. statistical classifier; 2. BGE-M3 classifier;
3. LLM; 4. Binoculars.

Detector dapat memiliki skala dan pola kesalahan berbeda. Mereka juga
dapat mengulang sinyal yang sama. Hindari rata-rata sederhana:

\[ FinalScore=`\frac{A+B+C+D}{4}`{=tex} \]

## 13.2 Arsitektur yang disarankan

``` text
DOCUMENT INPUT
    |
PREPROCESSING
    |-- Language identification
    |-- Normalization
    |-- Segmentation
    |
PARALLEL DETECTORS
    |-- A: Linguistic features + classifier
    |-- B: BGE-M3 embedding + classifier
    |-- C: Binoculars
    |-- D: Optional LLM analysis
    |
META-CLASSIFIER / SCORE FUSION
    |
CALIBRATION
    |
UNCERTAINTY & DECISION POLICY
    |
HUMAN / AI / MIXED / UNCERTAIN
    |
EXPLANATORY REPORT
```

LLM bahasa Indonesia tetap nonaktif sampai lolos evaluasi.

## 13.3 Stacking

1.  Latih base detector secara terpisah.
2.  Hasilkan prediksi out-of-fold pada training set.
3.  Gunakan prediksi out-of-fold sebagai fitur meta-classifier.
4.  Latih meta-classifier, misalnya Logistic Regression.
5.  Kalibrasi menggunakan data terpisah.
6.  Evaluasi sekali pada test final independen.

Jangan melatih meta-classifier dengan prediksi in-sample base model
karena berisiko data leakage.

Analisis korelasi kesalahan antar-detector. Model tambahan hanya
bermanfaat jika memberi informasi baru dan meningkatkan hasil pada
evaluasi independen.

------------------------------------------------------------------------

# 14. Robustness testing

Uji kondisi berikut:

  -----------------------------------------------------------------------
  Kondisi                             Tujuan
  ----------------------------------- -----------------------------------
  Raw AI text                         Teks AI asli

  Human-edited AI                     Teks AI yang disunting manusia

  AI paraphrased                      Teks AI yang diparafrase

  Human academic text                 Mengukur false positive

  Machine translated                  Menguji perubahan terjemahan mesin

  Human + AI mixed                    Menguji dokumen campuran

  Different prompting                 Variasi instruksi generator

  Different domains                   Generalisasi lintas-domain

  Human text edited by grammar tools  Teks manusia yang diperbaiki alat
                                      tata bahasa
  -----------------------------------------------------------------------

Sertakan teks manusia berupa artikel akademik, laporan teknis, tulisan
mahasiswa, teks formal, terjemahan manusia, teks yang diedit
dosen/editor, dan tulisan dengan istilah teknis padat.

Catat setiap transformasi di metadata. Jangan menganggap semua parafrase
memiliki tingkat perubahan yang sama.

------------------------------------------------------------------------

# 15. Penanganan teks pendek dan bahasa tidak didukung

Jangan memaksakan keputusan AI atau HUMAN untuk semua input.

  -----------------------------------------------------------------------
  Kondisi                             Kebijakan
  ----------------------------------- -----------------------------------
  Di bawah batas minimum kata         Insufficient evidence

  Bahasa belum didukung               Unsupported language

  Banyak teks non-prosa               Limited evidence

  Kutipan dominan                     Tandai keterbatasan atau kecualikan
                                      bagian sesuai kebijakan

  Detector bertentangan               Uncertain

  Skor dekat threshold                Uncertain
  -----------------------------------------------------------------------

Tentukan batas minimum melalui eksperimen. Uji panjang misalnya 50, 100,
150, 250, dan 500 kata. Ukur FPR, TPR, dan stabilitas. Jangan menerapkan
threshold yang sama untuk semua panjang jika validasi menunjukkan
perbedaan performa.

------------------------------------------------------------------------

# 16. Aturan HUMAN / AI / MIXED / UNCERTAIN

  -----------------------------------------------------------------------
  Kategori                            Definisi operasional
  ----------------------------------- -----------------------------------
  HUMAN                               Bukti mendukung human-like dan
                                      memenuhi syarat keputusan

  AI                                  Bukti mendukung AI-like dan
                                      memenuhi syarat keputusan

  MIXED                               Ada pola segmen berbeda yang
                                      memenuhi aturan mixed-origin

  UNCERTAIN                           Bukti tidak cukup, detector
                                      bertentangan, atau skor dekat
                                      threshold

  INSUFFICIENT_EVIDENCE               Input terlalu pendek atau tidak
                                      memenuhi syarat

  UNSUPPORTED_LANGUAGE                Bahasa tidak didukung atau belum
                                      divalidasi
  -----------------------------------------------------------------------

Contoh mixed:

``` text
Segment 1 -> AI-like
Segment 2 -> AI-like
Segment 3 -> Human-like
Segment 4 -> Human-like
Document -> MIXED
```

Contoh uncertain:

``` text
Segment 1 -> AI-like
Segment 2 -> Uncertain
Segment 3 -> Human-like
Segment 4 -> Conflicting detector signals
Document -> UNCERTAIN
```

Threshold harus dipilih melalui validation set dengan mempertimbangkan
biaya false positive dan false negative, bukan berdasarkan intuisi.

------------------------------------------------------------------------

# 17. Struktur laporan deteksi

Jangan hanya menampilkan:

``` text
AI Score: 87%
Status: AI GENERATED
```

Struktur yang disarankan:

``` text
ICALORA DETECTION REPORT

Document information
- Document ID
- Language
- Word count
- Segment count
- Analysis date

Detection result
- Classification
- Raw score
- Calibrated score
- Decision confidence
- AI-flagged word share
- Human-like word share
- Uncertain word share

Detector outputs
- Linguistic classifier
- BGE-M3 classifier
- Binoculars
- LLM status/output, if enabled

Model information
- Classifier version
- Embedding model version
- Binoculars configuration
- Dataset version
- Training date
- Calibration version
- Threshold version

Segment evidence
- Segment ID
- Word range
- Detector scores
- Segment classification
- Uncertainty status

Limitations
- Supported language and domain
- Minimum text length
- Known failure conditions
- Interpretation warning
```

Contoh tampilan berikut hanya simulasi, bukan hasil ICALORA:

``` text
ICALORA Detection Report

Calibrated AI-like score: 76.4%

Document:
- Total words: 2,500
- Analyzed segments: 10

Segment distribution:
- AI-flagged words: 1,910
- Other / uncertain words: 590

Detector outputs:
- Statistical classifier: 0.81
- BGE-M3 classifier: 0.74
- Binoculars: 0.79
- LLM: Disabled

Model:
- Classifier: v1.2
- Embedding: BGE-M3
- Language: Indonesian
- Calibration: Validation-based

Interpretation:
The score represents a model estimate under validated
conditions. It does not establish author identity or prove
that AI was used.
```

Jangan tampilkan angka simulasi sebagai hasil produksi.

------------------------------------------------------------------------

# 18. Reproducibility dan version tracking

Catat: - model version dan checkpoint; - tokenizer version; - dataset
version; - training configuration; - random seed; - preprocessing
version; - segmentation configuration; - threshold version; -
calibration version; - tanggal training dan evaluasi; - hardware dan
software environment.

Contoh metadata:

``` json
{
  "system": "ICALORA",
  "pipeline_version": "1.0.0",
  "classifier_version": "classifier-v1",
  "embedding_model": "BAAI/bge-m3",
  "binoculars_version": "record-exact-version",
  "language": "id",
  "segmentation": {
    "strategy": "paragraph_boundary",
    "target_words": 250
  },
  "calibration_version": "calibration-v1",
  "threshold_version": "threshold-v1",
  "dataset_version": "dataset-v1"
}
```

Ganti seluruh nilai contoh dengan versi aktual. Jangan mencatat versi
yang belum benar-benar digunakan.

------------------------------------------------------------------------

# 19. Roadmap implementasi

## Phase 1 --- Evaluation Foundation (P0)

-   [ ] Audit dataset dan provenance.
-   [ ] Audit data leakage.
-   [ ] Buat group-based train/validation/test split.
-   [ ] Buat cross-generator evaluation.
-   [ ] Buat unseen-generator test.
-   [ ] Buat cross-domain evaluation.
-   [ ] Buat human false-positive benchmark bahasa Indonesia.
-   [ ] Laporkan TPR@FPR 1% dan 5%.

**Output:** benchmark yang dapat dipercaya dan baseline performa.

## Phase 2 --- Model Reliability (P0)

-   [ ] Implementasikan probability calibration.
-   [ ] Hitung ECE, Brier Score, dan NLL.
-   [ ] Buat reliability diagram.
-   [ ] Optimalkan threshold pada validation set.
-   [ ] Implementasikan uncertainty handling.
-   [ ] Implementasikan short-text handling.

**Output:** skor lebih terkalibrasi dan kebijakan keputusan yang aman.

## Phase 3 --- Detection Improvement (P1)

-   [ ] Validasi forward pass Binoculars.
-   [ ] Validasi pasangan model dan tokenizer.
-   [ ] Uji threshold Binoculars untuk bahasa Indonesia.
-   [ ] Uji token-level probability analysis.
-   [ ] Uji document-level consistency.
-   [ ] Uji mixed-origin benchmark.

**Output:** bukti kontribusi detector tambahan.

## Phase 4 --- Ensemble Optimization (P1)

-   [ ] Jalankan ablation study.
-   [ ] Analisis korelasi error antar-detector.
-   [ ] Uji classifier tunggal.
-   [ ] Uji score fusion.
-   [ ] Uji stacking dengan out-of-fold prediction.
-   [ ] Kalibrasi meta-classifier.
-   [ ] Uji pada test final independen.

**Output:** ensemble yang terbukti lebih baik daripada baseline.

## Phase 5 --- Reporting and Reproducibility (P2)

-   [ ] Buat laporan per segmen.
-   [ ] Pisahkan raw score dan calibrated score.
-   [ ] Perjelas AI-flagged word share.
-   [ ] Tambahkan model version tracking.
-   [ ] Tambahkan dataset version tracking.
-   [ ] Dokumentasikan batasan sistem.
-   [ ] Simpan hasil evaluasi dan konfigurasi.

**Output:** sistem yang dapat diaudit dan hasil yang dapat direproduksi.

------------------------------------------------------------------------

# 20. Hal yang tidak direkomendasikan

  -----------------------------------------------------------------------
  Hindari                             Alasan
  ----------------------------------- -----------------------------------
  Menambah banyak LLM sekaligus       Belum tentu menambah informasi baru

  Menambah fitur hanya karena         Risiko overfitting
  terlihat canggih                    

  Menggunakan threshold paper secara  Dataset dan domain berbeda
  langsung                            

  Menganggap embedding similarity     Similarity bukan provenance
  sebagai bukti AI                    

  Menganggap skor 90% sebagai         Belum tentu terkalibrasi
  kepastian 90%                       

  Mengaktifkan LLM Indonesia sebelum  Ada sinyal false positive serius
  evaluasi ulang                      

  Menggabungkan skor dengan rata-rata Skala dan pola kesalahan berbeda
  sederhana                           

  Menggunakan test set untuk memilih  Estimasi performa menjadi
  threshold                           optimistis

  Menganggap instalasi Binoculars     Inference dan output perlu
  berarti sudah terintegrasi          diverifikasi

  Mengklaim mendeteksi semua          Klaim tidak didukung tanpa
  generator                           pengujian luas
  -----------------------------------------------------------------------

------------------------------------------------------------------------

# 21. Referensi awal

1.  **Spotting LLMs With Binoculars: Zero-Shot Detection of
    Machine-Generated Text.** ICML 2024.\
    https://proceedings.mlr.press/v235/hans24a.html

2.  **A Practical Examination of AI-Generated Text Detectors for Large
    Language Models.** NAACL 2025.\
    Cari berdasarkan judul dan verifikasi metadata publikasi resmi
    sebelum mengutip.

3.  **On the Generalization and Adaptation Ability of Machine-Generated
    Text Detectors in Academic Writing.** KDD 2025.\
    Cari berdasarkan judul dan verifikasi metadata publikasi resmi
    sebelum mengutip.

4.  **BGE-M3: Multi-Functionality, Multi-Linguality,
    Multi-Granularity.**\
    https://huggingface.co/BAAI/bge-m3

5.  **NIST Generative AI Pilot Study / AI Risk Management Framework
    resources.**\
    https://www.nist.gov/itl/ai-risk-management-framework

Sebelum memasukkan referensi ke paper, verifikasi penulis, judul, tahun,
venue, DOI, dan URL versi publikasi resmi. Jangan menyalin metadata
bibliografi yang belum diperiksa.

------------------------------------------------------------------------

# 22. Kriteria penerimaan sebelum rilis

## Dataset dan evaluasi

-   [ ] Provenance data tercatat.
-   [ ] Tidak ada duplikasi lintas split.
-   [ ] Prompt dan dokumen sumber dikelompokkan.
-   [ ] Training, validation, calibration, dan test dipisahkan.
-   [ ] Unseen-generator evaluation tersedia.
-   [ ] Cross-domain evaluation tersedia.
-   [ ] Jumlah sampel per kelompok dilaporkan.

## Model

-   [ ] Setiap detector memiliki baseline sendiri.
-   [ ] Ablation study selesai.
-   [ ] Kontribusi BGE-M3 terukur.
-   [ ] Implementasi Binoculars diverifikasi.
-   [ ] Korelasi error antar-detector dianalisis.
-   [ ] Ensemble dibandingkan dengan detector tunggal.

## Statistik dan keputusan

-   [ ] FPR dan TPR dilaporkan.
-   [ ] TPR@FPR dilaporkan.
-   [ ] Calibration dievaluasi.
-   [ ] Threshold dipilih dari validation set.
-   [ ] Test final tidak digunakan untuk tuning.
-   [ ] Short-text policy tersedia.
-   [ ] Uncertain policy tersedia.

## Pelaporan

-   [ ] Raw score terpisah dari calibrated score.
-   [ ] AI-flagged word share didefinisikan.
-   [ ] Skor per segmen dapat ditelusuri.
-   [ ] Model dan dataset version tercatat.
-   [ ] Batasan sistem ditampilkan.
-   [ ] Tidak ada klaim bahwa detector membuktikan identitas penulis.

------------------------------------------------------------------------

# 23. Rekomendasi akhir

Urutan kerja yang disarankan:

1.  Cross-generator testing.
2.  Human false-positive benchmark bahasa Indonesia.
3.  Calibration dan TPR@FPR.
4.  Validasi Binoculars.
5.  Ablation study.
6.  Ensemble optimization.
7.  Explainability dan reporting.

**Kesimpulan:** ICALORA tidak membutuhkan lebih banyak model sebanyak ia
membutuhkan pembuktian bahwa model yang sudah ada bekerja pada data yang
belum pernah dilihatnya. Generalisasi lintas-generator, false positive
yang rendah, kalibrasi yang baik, serta evaluasi bebas data leakage akan
memberikan peningkatan kualitas yang lebih berarti daripada sekadar
menambah jumlah detector.

------------------------------------------------------------------------