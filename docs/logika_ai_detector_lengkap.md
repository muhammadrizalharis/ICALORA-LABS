# Logika Pengecekan AI Detector

## Penjelasan teknis, lengkap, dan terstruktur

> **Catatan penting:** AI Detector tidak mengetahui secara langsung
> siapa yang menulis sebuah teks. Sistem memperkirakan apakah
> karakteristik teks lebih menyerupai teks yang dihasilkan AI atau teks
> yang ditulis manusia berdasarkan model, data, dan metode yang
> digunakan. Hasilnya merupakan estimasi, bukan bukti kepengarangan.

------------------------------------------------------------------------

## Daftar Isi

1.  [Pengertian AI Detector](#1-pengertian-ai-detector)
2.  [Gambaran umum alur deteksi](#2-gambaran-umum-alur-deteksi)
3.  [Text preprocessing](#3-text-preprocessing)
4.  [Feature extraction](#4-feature-extraction)
    -   [Perplexity](#41-perplexity)
    -   [Entropy dan token
        probability](#42-entropy-dan-token-probability)
    -   [Burstiness dan variasi
        kalimat](#43-burstiness-dan-variasi-kalimat)
    -   [Lexical features](#44-lexical-features)
    -   [Syntactic features](#45-syntactic-features)
    -   [Semantic dan contextual
        features](#46-semantic-dan-contextual-features)
    -   [Stylometric features](#47-stylometric-features)
5.  [Metode dan model deteksi](#5-metode-dan-model-deteksi)
6.  [Deteksi per segmen dan agregasi
    skor](#6-deteksi-per-segmen-dan-agregasi-skor)
7.  [AI text watermarking](#7-ai-text-watermarking)
8.  [Kesalahan dan keterbatasan AI
    Detector](#8-kesalahan-dan-keterbatasan-ai-detector)
9.  [AI Detector vs. plagiarism
    checker](#9-ai-detector-vs-plagiarism-checker)
10. [Evaluasi performa](#10-evaluasi-performa-ai-detector)
11. [Dukungan bahasa Indonesia](#11-ai-detection-untuk-bahasa-indonesia)
12. [Arsitektur untuk membangun AI
    Detector](#12-merancang-ai-detector-sendiri)
13. [Contoh alur perhitungan dan
    pseudocode](#13-contoh-alur-perhitungan-dan-pseudocode)
14. [Prinsip interpretasi hasil](#14-prinsip-interpretasi-hasil)
15. [Kesimpulan](#15-kesimpulan)
16. [Referensi dan bacaan lanjutan](#16-referensi-dan-bacaan-lanjutan)

------------------------------------------------------------------------

# 1. Pengertian AI Detector

AI Detector atau *AI-generated text detector* adalah sistem komputasi
yang memperkirakan apakah suatu teks memiliki karakteristik yang lebih
dekat dengan teks buatan manusia (*human-written*) atau teks yang
dihasilkan model kecerdasan buatan (*AI-generated*).

Contoh sumber teks AI antara lain model bahasa seperti ChatGPT, Gemini,
Claude, dan model generatif lainnya. Namun, kemampuan suatu detector
untuk mengenali keluaran model tertentu bergantung pada data pelatihan,
model pemeriksa, bahasa, domain, dan pembaruan sistem tersebut.

AI Detector dapat menggunakan satu atau beberapa pendekatan berikut:

-   **Statistical language modeling:** menganalisis probabilitas dan
    keterdugaan urutan token.
-   **Linguistic analysis:** menganalisis kosakata, tata bahasa,
    sintaksis, dan struktur kalimat.
-   **Stylometry:** mengukur karakteristik gaya penulisan.
-   **Machine learning classification:** mempelajari pola dari kumpulan
    teks berlabel.
-   **Deep learning:** mempelajari representasi teks yang lebih kompleks
    melalui neural network.
-   **Watermark detection:** memeriksa pola khusus yang sengaja
    disisipkan saat teks AI dihasilkan.

## 1.1 Apa yang sebenarnya diukur?

Detector tidak memiliki akses otomatis ke riwayat pengetikan, pikiran
penulis, atau identitas pembuat teks. Jika sistem hanya menerima teks
biasa, sistem terutama memeriksa bukti yang terkandung dalam teks
tersebut.

Karena itu, hasil seperti `80% AI` tidak boleh ditafsirkan sebagai:

-   80% kata dalam dokumen pasti ditulis AI;
-   terdapat bukti pasti bahwa penulis menggunakan ChatGPT;
-   probabilitas bahwa orang tertentu melakukan kecurangan adalah 80%;
-   80% dokumen merupakan plagiarisme.

Makna skor bergantung pada definisi skor yang digunakan oleh penyedia
alat. Skor dapat berupa proporsi segmen yang ditandai, skor klasifikasi,
atau estimasi probabilitas yang telah atau belum dikalibrasi.

## 1.2 Human-written dan AI-generated bukan selalu dua kategori yang bersih

Dalam praktiknya terdapat teks campuran (*mixed-origin text*), misalnya:

-   manusia menulis seluruh teks;
-   AI membuat draf, lalu manusia menyuntingnya;
-   manusia menulis draf, lalu AI memperbaiki tata bahasa;
-   manusia dan AI menyusun bagian yang berbeda;
-   AI menghasilkan teks, lalu teks diterjemahkan atau diparafrasekan.

Sistem dua kelas yang hanya mengenal `Human` dan `AI` dapat kesulitan
menangani kasus campuran. Untuk penggunaan yang lebih bertanggung jawab,
kategori `uncertain` atau `mixed` dapat dipertimbangkan.

------------------------------------------------------------------------

# 2. Gambaran umum alur deteksi

Arsitektur konseptual AI Detector dapat digambarkan sebagai berikut:

``` text
INPUT DOCUMENT
      |
      v
TEXT VALIDATION
      |
      v
PREPROCESSING
(normalization, tokenization, segmentation)
      |
      v
FEATURE EXTRACTION
(statistical, lexical, syntactic, semantic, stylometric)
      |
      v
DETECTION MODEL
(rule-based / machine learning / deep learning / zero-shot)
      |
      v
SCORE ESTIMATION
      |
      v
SEGMENT AGGREGATION
      |
      v
OUTPUT REPORT
(AI-like / human-like / uncertain, with limitations)
```

Alur ini merupakan gambaran umum, bukan arsitektur wajib bagi semua
produk. Sebuah detector komersial dapat memakai model end-to-end tanpa
menampilkan fitur-fitur antara secara eksplisit. Ada juga sistem yang
menggunakan model bahasa sebagai evaluator dan tidak memakai classifier
tradisional.

## 2.1 Input dan validasi dokumen

Sebelum analisis, sistem dapat memeriksa:

-   apakah berkas dapat dibaca;
-   apakah teks cukup panjang;
-   apakah bahasa termasuk bahasa yang didukung;
-   apakah konten berupa prosa, kode, daftar, tabel, atau kutipan;
-   apakah jumlah teks yang dapat dianalisis memenuhi batas minimum;
-   apakah dokumen mengandung karakter rusak atau hasil OCR yang buruk.

Tidak semua jenis teks cocok untuk deteksi. Kode program, daftar
pustaka, tabel, rumus, kutipan pendek, dan butir-butir singkat memiliki
karakteristik berbeda dari prosa biasa.

## 2.2 Mengapa teks dapat dibagi menjadi segmen?

Dokumen panjang dapat dibagi menjadi kalimat, paragraf, atau jendela
token (*token windows*). Tujuannya antara lain:

1.  menangkap perubahan pola dalam dokumen;
2.  menghindari satu skor global menutupi variasi antarbagiannya;
3.  memungkinkan penandaan bagian tertentu;
4.  membatasi panjang masukan yang dapat diproses model.

Ukuran segmen dan tumpang tindih antarsegmen (*overlap*) memengaruhi
hasil. Segmen yang terlalu pendek dapat kehilangan konteks; segmen
terlalu panjang dapat menyamarkan perubahan lokal.

------------------------------------------------------------------------

# 3. Text preprocessing

*Preprocessing* mengubah dokumen menjadi representasi yang dapat
diproses oleh sistem. Langkah yang digunakan bergantung pada model
deteksi.

## 3.1 Normalisasi teks

Normalisasi dapat meliputi:

-   penanganan spasi berlebih;
-   penyamaan representasi karakter Unicode;
-   penanganan tanda kutip dan tanda hubung;
-   penghapusan artefak HTML atau format dokumen;
-   pemulihan paragraf dan pemisah kalimat.

Normalisasi harus dilakukan hati-hati. Tanda baca, huruf kapital,
pemenggalan paragraf, dan format tertentu dapat menjadi fitur gaya
penulisan. Menghapus semuanya dapat membuang informasi yang berguna.

## 3.2 Tokenization

Tokenisasi memecah teks menjadi unit yang disebut token. Token tidak
selalu sama dengan kata. Pada tokenizer subword, satu kata dapat dibagi
menjadi beberapa token; tanda baca juga dapat menjadi token tersendiri.

Contoh konseptual:

``` text
Teks:
Artificial intelligence can support research.

Token berbasis kata:
["Artificial", "intelligence", "can", "support", "research", "."]

Token model:
Bergantung pada tokenizer dan kosakata model yang digunakan.
```

Perplexity dan probabilitas token harus dihitung menggunakan tokenizer
serta model bahasa yang konsisten. Nilai dari dua model dengan tokenizer
berbeda tidak selalu dapat dibandingkan langsung.

## 3.3 Sentence segmentation

Sistem mengidentifikasi batas kalimat. Hal ini diperlukan jika detector
menganalisis panjang kalimat, pola sintaksis, atau skor pada tingkat
kalimat.

Tantangan segmentasi meliputi singkatan, angka desimal, gelar, kutipan,
dan format daftar.

## 3.4 Language identification

Sistem dapat mengidentifikasi bahasa dokumen. Hal ini penting karena:

-   model bahasa tertentu hanya mendukung bahasa tertentu;
-   pola tata bahasa berbeda ant bahasa;
-   fitur yang efektif pada bahasa Inggris belum tentu efektif pada
    bahasa Indonesia;
-   teks campuran dapat memerlukan penanganan khusus.

## 3.5 Segmentation atau chunking

Dokumen dapat dibagi menjadi beberapa *chunk* berdasarkan jumlah token
atau batas paragraf. Sistem perlu menjaga konteks secukupnya dan
menghindari pemotongan yang merusak struktur kalimat.

------------------------------------------------------------------------

# 4. Feature extraction

*Feature extraction* adalah proses mengubah teks menjadi ciri atau
representasi yang dapat digunakan untuk klasifikasi. Fitur dapat
bersifat eksplisit (misalnya rata-rata panjang kalimat) atau dipelajari
secara otomatis oleh neural network.

Penting: tidak ada satu fitur yang secara universal membedakan tulisan
manusia dari tulisan AI. Fitur-fitur ini merupakan sinyal statistik yang
dapat saling tumpang tindih.

## 4.1 Perplexity

### Pengertian

*Perplexity* (PPL) mengukur seberapa tidak terduga suatu urutan token
menurut model bahasa tertentu. Secara intuitif, perplexity yang lebih
rendah berarti model lebih mudah memprediksi token-token dalam teks
tersebut.

Untuk urutan token (w_1, w_2, `\ldots`{=tex}, w_N), perplexity dapat
ditulis:

\[ PP(W)=`\exp`{=tex}`\left`{=tex}(
-`\frac{1}{N}`{=tex}`\sum`{=tex}*{i=1}\^{N}
`\ln `{=tex}P(w_i`\mid `{=tex}w_1,`\ldots`{=tex},w*{i-1})
`\right`{=tex}) \]

Keterangan:

-   (W): urutan token dalam teks;
-   (N): jumlah token yang dinilai;
-   (w_i): token ke-(i);
-   (P(w_i`\mid `{=tex}w\_{\<i})): probabilitas token saat ini
    berdasarkan konteks sebelumnya;
-   (`\ln`{=tex}): logaritma natural;
-   (`\exp`{=tex}): fungsi eksponensial.

Bentuk ekuivalennya adalah:

\[ PP(W)=`\left`{=tex}(`\prod`{=tex}\_{i=1}\^{N}
`\frac{1}{P(w_i\mid w_{<i})}`{=tex}`\right`{=tex})\^{1/N} \]

### Contoh perhitungan sederhana

Misalkan model memberikan probabilitas token yang dinilai sebesar 0,50;
0,40; dan 0,25. Dengan menyederhanakan konteks token untuk ilustrasi:

\[
PP=`\left`{=tex}(`\frac{1}{0.50\times0.40\times0.25}`{=tex}`\right`{=tex})\^{1/3}
\]

\[ PP=(20)\^{1/3}`\approx 2.71`{=tex} \]

Angka tersebut adalah hasil ilustrasi matematis, bukan ambang batas AI
Detector.

### Interpretasi

-   Perplexity rendah: token relatif mudah diprediksi oleh model yang
    digunakan.
-   Perplexity tinggi: token relatif sulit diprediksi oleh model yang
    digunakan.

Sebagian pendekatan deteksi mengamati bahwa teks yang dihasilkan oleh
model generatif tertentu dapat memiliki probabilitas tinggi di bawah
model bahasa yang relevan. Namun, hal ini bukan hukum universal.

Tulisan manusia yang formal, generik, atau menggunakan ungkapan umum
juga dapat memiliki perplexity rendah. Teks AI yang kreatif, teknis,
atau tidak lazim dapat memiliki perplexity lebih tinggi.

### Keterbatasan

Perplexity sangat bergantung pada:

-   model bahasa yang dipakai untuk menghitungnya;
-   tokenizer;
-   bahasa dan domain;
-   panjang serta kualitas teks;
-   cara menangani token awal dan konteks;
-   apakah model evaluator sama atau mirip dengan model generator.

Karena itu, nilai PPL dari model berbeda tidak boleh dibandingkan secara
naif.

## 4.2 Entropy dan token probability

Probabilitas token menunjukkan seberapa besar kemungkinan model
memberikan token tertentu pada konteks yang tersedia. *Entropy*
menggambarkan ketidakpastian distribusi probabilitas model.

Untuk distribusi token (p_1,`\ldots`{=tex},p_k):

\[ H=-`\sum`{=tex}\_{j=1}\^{k}p_j`\log `{=tex}p_j \]

Entropy tinggi berarti distribusi probabilitas lebih menyebar; entropy
rendah berarti probabilitas lebih terkonsentrasi pada sedikit pilihan.

Dalam deteksi, statistik probabilitas atau entropy dapat digunakan
sebagai fitur. Akan tetapi, entropy bukan bukti asal-usul teks. Nilainya
mencerminkan perilaku model evaluator terhadap teks, bukan identitas
penulis.

## 4.3 Burstiness dan variasi kalimat

Istilah *burstiness* digunakan dalam beberapa konteks analisis teks.
Pada pembahasan AI Detector, istilah ini sering dipakai secara informal
untuk menggambarkan variasi panjang atau pola kalimat. Implementasi
ilmiah harus mendefinisikan secara eksplisit apa yang diukur, karena
tidak ada satu rumus burstiness yang wajib dipakai semua detector.

Misalnya, panjang kalimat dalam jumlah kata:

``` text
Kalimat 1: 7 kata
Kalimat 2: 24 kata
Kalimat 3: 5 kata
Kalimat 4: 19 kata
```

Salah satu ukuran variasi adalah koefisien variasi:

\[ CV=`\frac{\sigma_L}{\mu_L}`{=tex} \]

Keterangan:

-   (`\sigma`{=tex}\_L): standar deviasi panjang kalimat;
-   (`\mu`{=tex}\_L): rata-rata panjang kalimat.

Nilai CV yang lebih tinggi menunjukkan variasi relatif yang lebih besar.

Contoh dua pola:

**Pola relatif seragam**

-   AI can process large datasets.
-   AI can identify complex patterns.
-   AI can improve decision-making.
-   AI can support scientific research.

**Pola lebih bervariasi**

-   AI can process large datasets.
-   However, the ability to identify complex patterns does not
    automatically mean that every prediction is correct.
-   This is important.
-   Especially in scientific research, interpretation requires careful
    evaluation.

Contoh ini hanya menunjukkan variasi struktur. Tidak dapat disimpulkan
bahwa contoh pertama pasti AI atau contoh kedua pasti manusia. Model AI
dapat menghasilkan variasi yang tinggi, dan penulis manusia dapat
menulis dengan pola yang konsisten.

## 4.4 Lexical features

Fitur leksikal memeriksa karakteristik kosakata, antara lain:

  Fitur                  Makna
  ---------------------- -----------------------------------------------
  Word frequency         Frekuensi kata
  Vocabulary diversity   Keragaman kosakata
  Repeated phrases       Pengulangan frasa
  N-grams                Urutan satu atau beberapa token
  Function words         Kata fungsi, misalnya preposisi dan konjungsi
  Rare words             Kata yang jarang muncul
  Type-token ratio       Rasio kata unik terhadap total kata

### Type-Token Ratio (TTR)

\[ TTR=`\frac{V}{N}`{=tex} \]

-   (V): jumlah tipe kata unik;
-   (N): jumlah token kata.

Contoh:

``` text
AI improves technology.
AI improves productivity.
```

Jika tokenisasi berbasis kata menghasilkan enam token dan empat kata
unik, maka:

\[ TTR=`\frac{4}{6}`{=tex}`\approx0.667`{=tex} \]

TTR sederhana cenderung menurun ketika teks semakin panjang. Karena itu,
untuk membandingkan teks dengan panjang berbeda, peneliti dapat
mempertimbangkan *moving-average type-token ratio* (MATTR), ukuran
berbasis jendela, atau ukuran keragaman leksikal lainnya.

### N-gram

N-gram adalah urutan token bersebelahan:

-   unigram: satu token;
-   bigram: dua token;
-   trigram: tiga token.

Contoh bigram:

``` text
"artificial intelligence"
"intelligence can"
"can support"
"support research"
```

Frekuensi dan pola N-gram dapat digunakan sebagai fitur, tetapi sangat
dipengaruhi topik, domain, dan kosakata.

## 4.5 Syntactic features

Fitur sintaksis mengukur struktur gramatikal kalimat. Contohnya:

-   panjang kalimat;
-   jumlah klausa;
-   kedalaman parse tree;
-   distribusi part-of-speech (POS);
-   pola subjek, predikat, dan objek;
-   penggunaan kalimat aktif dan pasif;
-   struktur dependensi antarkata;
-   kompleksitas sintaksis.

Contoh POS tagging:

``` text
The researchers analyzed the data.

The          -> Determiner
researchers  -> Noun
analyzed     -> Verb
the          -> Determiner
data         -> Noun
```

*Dependency parsing* memetakan hubungan gramatikal, misalnya kata kerja
sebagai pusat kalimat dan kata benda sebagai subjek atau objek.

Fitur sintaksis dapat membantu classifier mempelajari pola, tetapi
struktur formal dan gramatikal juga lazim pada tulisan akademik manusia.

## 4.6 Semantic dan contextual features

Analisis semantik berfokus pada makna dan hubungan antarkalimat. Model
dapat menghasilkan *embedding*, yaitu representasi vektor dari teks.

Kemiripan dua embedding sering dihitung dengan cosine similarity:

\[ `\operatorname{CosSim}`{=tex}(A,B)=
`\frac{A\cdot B}{\|A\|\|B\|}`{=tex} \]

Nilai mendekati 1 menunjukkan arah vektor yang mirip. Ini tidak berarti
dua kalimat pasti identik maknanya, dan kemiripan tinggi bukan bukti
teks AI.

Fitur semantik dapat mencakup:

-   kesamaan topik antarkalimat;
-   kesinambungan pembahasan;
-   pengulangan gagasan;
-   perubahan topik;
-   hubungan antarparagraf;
-   representasi kontekstual dari Transformer.

Contoh vektor empat dimensi berikut hanya ilustrasi:

\[ S_1=\[0.21,0.42,0.13,0.87\] \]

\[ S_2=\[0.23,0.39,0.15,0.82\] \]

Dalam sistem nyata, embedding umumnya memiliki dimensi jauh lebih besar
dan dihasilkan oleh model tertentu.

## 4.7 Stylometric features

*Stylometry* mempelajari karakteristik gaya penulisan. Fitur yang dapat
dianalisis meliputi:

-   rata-rata panjang kata;
-   panjang kalimat;
-   frekuensi tanda baca;
-   penggunaan huruf kapital;
-   frekuensi kata ganti;
-   penggunaan konjungsi;
-   variasi paragraf;
-   distribusi kata fungsi;
-   pola pengulangan ungkapan.

Stylometry dapat digunakan untuk mempelajari konsistensi gaya seorang
penulis jika tersedia beberapa sampel yang relevan dan sah. Namun,
perubahan gaya tidak membuktikan penggunaan AI. Perubahan dapat
disebabkan penyuntingan, perubahan genre, instruksi penulisan, atau
penggunaan sumber yang berbeda.

------------------------------------------------------------------------

# 5. Metode dan model deteksi

## 5.1 Rule-based detection

Pendekatan berbasis aturan menggunakan kondisi yang ditentukan manusia.
Contoh berikut hanya pseudocode ilustratif:

``` python
score = 0

if perplexity < threshold_ppl:
    score += 1

if sentence_variation < threshold_variation:
    score += 1

if repetition_score > threshold_repetition:
    score += 1

if score >= decision_threshold:
    prediction = "AI-like"
else:
    prediction = "Not flagged as AI-like"
```

`threshold_ppl`, `threshold_variation`, `threshold_repetition`, dan
`decision_threshold` harus ditentukan melalui eksperimen pada data yang
representatif. Angka ambang tidak boleh diambil begitu saja dari contoh
atau diterapkan universal.

**Kelebihan:**

-   mudah dipahami;
-   mudah diaudit;
-   relatif sederhana untuk dibuat.

**Kekurangan:**

-   aturan kaku;
-   sulit menangani variasi bahasa dan domain;
-   rentan terhadap perubahan pola generasi;
-   fitur sederhana mudah tumpang tindih antara teks manusia dan AI.

## 5.2 Machine learning-based detection

Model supervised learning dilatih menggunakan teks berlabel, misalnya
`human` dan `AI`.

Contoh data:

  Dokumen                                       Label
  --------------------------------------------- -------
  Teks manusia dengan asal-usul terverifikasi   Human
  Keluaran model AI dengan asal-usul tercatat   AI
  Teks manusia lain                             Human
  Keluaran generator lain                       AI

Fitur dapat berupa statistik, leksikal, sintaksis, atau embedding.
Algoritma yang dapat diuji:

-   Logistic Regression;
-   Support Vector Machine (SVM);
-   Random Forest;
-   Gradient Boosting atau XGBoost;
-   Naive Bayes untuk representasi tertentu.

Classifier belajar memisahkan representasi fitur berdasarkan label
pelatihan. Pada SVM, misalnya, model mencari batas keputusan yang
memisahkan kelas dengan margin tertentu.

Kinerja pada data uji yang berasal dari sumber sama belum tentu
menunjukkan kemampuan generalisasi ke model AI atau domain yang belum
pernah dilihat.

## 5.3 Deep learning-based detection

Deep learning dapat mempelajari representasi dari urutan token secara
langsung.

Arsitektur yang mungkin digunakan:

-   **CNN:** menangkap pola lokal pada urutan token;
-   **LSTM:** memodelkan ketergantungan berurutan;
-   **BiLSTM:** memproses konteks dari dua arah;
-   **Transformer encoder:** membangun representasi kontekstual;
-   **BERT dan turunannya:** menghasilkan embedding kontekstual yang
    dapat diteruskan ke classifier.

Contoh alur classifier berbasis Transformer:

``` text
Input tokens
    |
Transformer encoder
    |
Document representation (mis. [CLS] atau pooling)
    |
Dense layer
    |
Softmax / classification head
    |
Predicted class
```

Misalnya keluaran model:

\[ P(Human)=0.18,`\qquad `{=tex}P(AI)=0.82 \]

Model memilih kelas AI karena skor keluaran untuk kelas tersebut lebih
tinggi. Namun, angka 0,82 belum tentu berarti probabilitas empiris yang
terkalibrasi sebesar 82%. Kalibrasi harus diuji secara terpisah.

## 5.4 Zero-shot dan model-based detection

Pendekatan zero-shot mencoba menilai teks tanpa melatih classifier
khusus menggunakan dataset berlabel yang sama seperti supervised
learning. Beberapa metode menggunakan probabilitas dari model bahasa
atau membandingkan teks asli dengan teks yang telah dimodifikasi.

Contoh penelitian/metode yang dikenal:

-   DetectGPT;
-   Fast-DetectGPT;
-   GLTR.

### Gagasan DetectGPT

Secara umum, pendekatan DetectGPT mengamati perubahan log-probability
ketika teks asli dibandingkan dengan beberapa versi teks yang
diperturbasi atau dimodifikasi. Intuisi dasarnya berkaitan dengan
karakteristik geometri distribusi probabilitas model bahasa.

Metode ini tidak sekadar memeriksa apakah satu kalimat terdengar formal.
Ia menggunakan model bahasa dan prosedur pembandingan probabilitas.
Kinerjanya tetap bergantung pada model, generator, jenis teks, dan
kondisi evaluasi.

### Gagasan GLTR

GLTR (*Giant Language Model Test Room*) memvisualisasikan peringkat atau
probabilitas token menurut model bahasa. Visualisasi tersebut membantu
pemeriksa melihat seberapa sering token yang digunakan termasuk pilihan
berperingkat tinggi menurut model. Ini adalah alat analisis, bukan bukti
definitif kepengarangan.

------------------------------------------------------------------------

# 6. Deteksi per segmen dan agregasi skor

Beberapa detector memberikan highlight pada bagian tertentu. Secara
konseptual, prosesnya dapat berupa:

1.  membagi dokumen menjadi segmen;
2.  menghitung representasi atau skor setiap segmen;
3.  menerapkan classifier atau model deteksi;
4.  menggabungkan skor segmen;
5.  menampilkan ringkasan dan bagian yang ditandai.

Contoh ilustrasi:

  Segmen       Skor model ilustratif
  ---------- -----------------------
  Segmen 1                      0,90
  Segmen 2                      0,35
  Segmen 3                      0,82
  Segmen 4                      0,55

Skor tersebut bukan hasil pemeriksaan nyata. Angka hanya menunjukkan
bahwa skor antarbagian dapat bervariasi.

## 6.1 Cara sederhana menghitung proporsi segmen

Misalnya terdapat 100 segmen yang memenuhi syarat dan 65 segmen
ditandai. Sistem sederhana dapat menghitung:

\[ Score=`\frac{65}{100}`{=tex}`\times100`{=tex}%=65% \]

Namun, ini hanya satu kemungkinan metode agregasi. Sistem lain dapat
menggunakan:

-   proporsi berdasarkan jumlah kata;
-   proporsi berdasarkan jumlah token;
-   rata-rata skor segmen;
-   rata-rata berbobot panjang;
-   agregasi dengan threshold;
-   model klasifikasi tingkat dokumen.

Karena itu, persentase dari dua produk berbeda tidak otomatis sebanding.

## 6.2 Skor segmen bukan selalu probabilitas

Jika model menghasilkan nilai 0,8, nilai itu bisa berupa:

-   probabilitas softmax yang belum dikalibrasi;
-   skor keputusan yang dinormalisasi;
-   skor kemiripan;
-   skor heuristik;
-   estimasi proporsi teks yang ditandai.

Pengguna perlu memeriksa dokumentasi penyedia alat sebelum mengartikan
skor sebagai probabilitas.

## 6.3 Contoh laporan yang bertanggung jawab

Laporan yang baik seharusnya menyampaikan:

-   bagian yang dianalisis;
-   bahasa dan jenis teks yang didukung;
-   skor dan definisi skor;
-   metode atau versi model jika tersedia;
-   keterbatasan dan ketidakpastian;
-   peringatan agar hasil tidak menjadi satu-satunya dasar keputusan.

------------------------------------------------------------------------

# 7. AI text watermarking

*Watermarking* berbeda dari deteksi pasif berbasis karakteristik teks.

Pada watermarking, mekanisme khusus diterapkan ketika model menghasilkan
teks. Mekanisme tersebut memengaruhi pemilihan token sehingga pola
statistik tertentu dapat diperiksa oleh detector yang kompatibel.

Alur konseptual:

``` text
AI text generator
       |
       v
Watermarking mechanism
       |
       v
Generated text with watermark signal
       |
       v
Compatible watermark detector
       |
       v
Statistical test / watermark evidence
```

## 7.1 Perbedaan dengan passive detection

  -----------------------------------------------------------------------
  Passive AI detection                Watermark detection
  ----------------------------------- -----------------------------------
  Menganalisis karakteristik teks     Memeriksa sinyal yang sengaja
  yang tersedia                       disisipkan

  Tidak memerlukan watermark dari     Memerlukan generator dan detector
  generator                           yang kompatibel

  Dapat diterapkan pada teks tanpa    Tidak dapat mengandalkan sinyal
  watermark                           jika watermark tidak ada

  Menghasilkan estimasi berdasarkan   Menguji keberadaan pola watermark
  pola                                
  -----------------------------------------------------------------------

Watermark dapat melemah akibat penyuntingan, parafrase, pemotongan, atau
penerjemahan. Tidak ditemukannya watermark juga tidak membuktikan teks
ditulis manusia.

------------------------------------------------------------------------

# 8. Kesalahan dan keterbatasan AI Detector

Dua jenis kesalahan klasifikasi yang utama adalah *false positive* dan
*false negative*.

## 8.1 False positive

False positive terjadi ketika teks manusia ditandai sebagai AI.

Contoh faktor yang dapat meningkatkan risiko:

-   bahasa akademik yang formal;
-   kalimat generik dan umum;
-   struktur yang konsisten;
-   teks sangat pendek;
-   penggunaan bahasa kedua;
-   domain yang memiliki pola terminologi dan sintaksis terbatas.

Contoh kalimat:

> This study aims to analyze the impact of information technology on
> organizational performance.

Kalimat tersebut lazim dalam penulisan akademik. Jika detector
menandainya, hasil itu tidak membuktikan kalimat dibuat AI.

## 8.2 False negative

False negative terjadi ketika teks AI tidak dikenali sebagai AI.

Penyebab yang mungkin:

-   teks disunting manusia;
-   parafrase mengubah pola permukaan;
-   teks diterjemahkan;
-   generator tidak terwakili dalam data pelatihan;
-   model deteksi tidak cocok dengan domain atau bahasa;
-   teks sangat pendek atau tidak memenuhi kriteria analisis.

## 8.3 Distribution shift

*Distribution shift* terjadi ketika distribusi data saat penggunaan
berbeda dari distribusi data pelatihan.

Contoh:

-   training menggunakan keluaran model AI generasi lama;
-   pengujian menggunakan model generasi baru;
-   training didominasi teks bahasa Inggris;
-   pengujian menggunakan bahasa Indonesia;
-   training menggunakan artikel umum;
-   pengujian menggunakan paper akademik teknis.

Perubahan ini dapat menurunkan kinerja model.

## 8.4 Mengapa detector tidak dapat menjadi bukti tunggal?

Karakteristik tulisan manusia dan AI saling tumpang tindih. Model juga
dapat salah, terutama pada bahasa, domain, atau jenis dokumen yang tidak
terwakili dengan baik.

Untuk keputusan akademik, hasil detector sebaiknya diperlakukan sebagai
sinyal awal yang memerlukan pemeriksaan manusia dan bukti pendukung.
Pemeriksaan dapat mempertimbangkan draf, catatan riset, riwayat revisi,
sumber rujukan, dan kemampuan penulis menjelaskan isi
tulisannya---dengan tetap menghormati privasi dan prosedur institusi.

------------------------------------------------------------------------

# 9. AI Detector vs. Plagiarism Checker

Keduanya memiliki tujuan dan dasar analisis yang berbeda.

  -----------------------------------------------------------------------
  Aspek                   AI Detector             Plagiarism Checker
  ----------------------- ----------------------- -----------------------
  Tujuan                  Memperkirakan           Menemukan kemiripan
                          kemungkinan teks AI     dengan sumber lain

  Dasar analisis          Pola statistik,         Pencocokan teks dan
                          linguistik, atau model  sumber pembanding

  Memerlukan korpus       Tidak selalu            Umumnya ya
  pembanding                                      

  Hasil umum              AI score atau segmen    Similarity score dan
                          yang ditandai           sumber kecocokan

  Menemukan salinan       Bukan fungsi utama      Salah satu fungsi utama
  identik                                         

  Menilai asal teks       Tidak                   Tidak selalu; kecocokan
  secara pasti                                    perlu ditafsirkan
  -----------------------------------------------------------------------

Contoh:

-   Dokumen ditulis sendiri dengan kalimat orisinal: similarity bisa
    rendah, tetapi AI detector masih dapat memberi skor AI-like.
-   Dokumen menyalin paragraf dari sumber tanpa atribusi: similarity
    checker dapat menemukan kecocokan, sementara AI detector belum tentu
    menandainya.

**AI score bukan similarity score, dan similarity score bukan AI
score.**

------------------------------------------------------------------------

# 10. Evaluasi performa AI Detector

Untuk menilai kualitas model, gunakan data uji dengan label asal-usul
yang dapat diverifikasi. Evaluasi tidak cukup hanya melaporkan accuracy.

Misalkan sistem diuji pada 1.000 dokumen dengan hasil:

  Kondisi                 Jumlah
  --------------------- --------
  True Positive (TP)         400
  False Positive (FP)         50
  False Negative (FN)        100
  True Negative (TN)         450
  Total                    1.000

Anggap kelas positif adalah `AI-generated`.

## 10.1 Accuracy

Proporsi seluruh prediksi yang benar:

\[ Accuracy=`\frac{TP+TN}{TP+TN+FP+FN}`{=tex} \]

\[ Accuracy=`\frac{400+450}{1000}`{=tex}=0.85=85% \]

## 10.2 Precision

Dari seluruh dokumen yang diprediksi AI, berapa bagian yang benar-benar
AI?

\[ Precision=`\frac{TP}{TP+FP}`{=tex} \]

\[ Precision=`\frac{400}{400+50}`{=tex}=0.8889=88.89% \]

## 10.3 Recall

Dari seluruh dokumen AI yang sebenarnya, berapa bagian yang berhasil
ditemukan?

\[ Recall=`\frac{TP}{TP+FN}`{=tex} \]

\[ Recall=`\frac{400}{400+100}`{=tex}=0.80=80% \]

## 10.4 F1-score

Rata-rata harmonik precision dan recall:

\[
F1=2`\times`{=tex}`\frac{Precision\times Recall}{Precision+Recall}`{=tex}
\]

Dengan nilai di atas:

\[ F1`\approx84.21`{=tex}% \]

## 10.5 False Positive Rate (FPR)

Proporsi dokumen manusia yang salah ditandai sebagai AI:

\[ FPR=`\frac{FP}{FP+TN}`{=tex} \]

\[ FPR=`\frac{50}{50+450}`{=tex}=0.10=10% \]

FPR sangat penting dalam konteks pendidikan. Jika false positive tinggi,
banyak tulisan manusia berpotensi salah ditandai.

## 10.6 Mengapa accuracy saja tidak cukup?

Jika dataset tidak seimbang, accuracy dapat menyesatkan. Misalnya, jika
95% dokumen adalah manusia, classifier yang selalu memprediksi `Human`
dapat memperoleh accuracy 95%, tetapi sama sekali gagal mendeteksi AI.

Karena itu, evaluasi sebaiknya mencakup:

-   precision;
-   recall;
-   F1-score;
-   specificity;
-   false positive rate;
-   ROC-AUC;
-   PR-AUC;
-   confusion matrix;
-   kalibrasi probabilitas;
-   interval kepercayaan jika memungkinkan.

## 10.7 Desain evaluasi yang kuat

Agar hasil penelitian dapat dipertanggungjawabkan:

1.  Pisahkan data berdasarkan dokumen, bukan potongan acak dari dokumen
    yang sama.
2.  Hindari teks duplikat atau parafrase dekat yang tersebar pada
    training dan testing.
3.  Catat model AI, tanggal generasi, prompt, bahasa, dan proses
    penyuntingan.
4.  Uji lintas-generator: model yang tidak digunakan saat training harus
    masuk pengujian.
5.  Uji lintas-domain: misalnya esai, artikel akademik, dan teks umum.
6.  Uji lintas-bahasa jika sistem ditujukan untuk multibahasa.
7.  Laporkan FPR secara eksplisit.
8.  Lakukan analisis kesalahan dan ablation study.
9.  Tetapkan threshold berdasarkan tujuan dan biaya kesalahan, bukan
    memilih threshold yang terlihat paling bagus pada test set.
10. Gunakan test set final yang tidak dipakai untuk memilih model atau
    threshold.

------------------------------------------------------------------------

# 11. AI Detection untuk bahasa Indonesia

Kemampuan deteksi sangat bergantung pada dukungan bahasa dan kualitas
data. Model yang diuji pada bahasa Inggris belum tentu bekerja dengan
baik pada bahasa Indonesia.

Beberapa karakteristik bahasa Indonesia yang perlu diperhatikan:

-   afiksasi: `me-`, `ber-`, `di-`, `ter-`, `-kan`, `-i`, `-an`;
-   reduplikasi: `buku-buku`, `berulang-ulang`;
-   kata majemuk;
-   variasi formal dan informal;
-   penggunaan kata serapan;
-   variasi ejaan dan tanda baca;
-   campur kode Indonesia--Inggris.

Contoh hubungan morfologis:

-   melakukan;
-   dilakukan;
-   pelaksanaan;
-   pelaksanaannya.

Sistem yang tidak memiliki tokenizer atau model bahasa yang memadai
untuk bahasa Indonesia dapat menghasilkan representasi yang kurang
tepat.

## 11.1 Dataset bahasa Indonesia

Dataset yang baik sebaiknya mencakup:

-   tulisan manusia dengan izin dan provenance yang jelas;
-   teks AI dari beberapa generator;
-   berbagai topik dan tingkat formalitas;
-   teks akademik dan nonakademik;
-   variasi panjang dokumen;
-   teks campuran manusia--AI;
-   teks yang mengalami penyuntingan;
-   teks dari model yang tidak dipakai pada pelatihan.

Label harus didasarkan pada proses pembuatan yang terdokumentasi, bukan
pada dugaan pemeriksa.

## 11.2 Dukungan bahasa produk

Jangan mengasumsikan semua produk mendukung bahasa Indonesia hanya
karena antarmukanya dapat menerima teks Indonesia. Periksa dokumentasi
resmi produk untuk:

-   bahasa yang didukung;
-   jenis konten yang dianalisis;
-   panjang minimum dan maksimum;
-   versi model;
-   batasan laporan;
-   kebijakan penggunaan skor.

Dukungan bahasa dan kinerja deteksi merupakan dua hal yang berbeda.
Bahasa yang tercantum sebagai bahasa yang didukung pun tetap memiliki
tingkat kesalahan.

------------------------------------------------------------------------

# 12. Merancang AI Detector sendiri

Jika ingin mengembangkan AI Detector, pendekatan hybrid dapat menjadi
salah satu hipotesis penelitian yang layak diuji. Namun, model hybrid
tidak otomatis lebih baik daripada model tunggal. Keunggulannya harus
dibuktikan secara eksperimental.

## 12.1 Tujuan sistem

Tentukan lebih dahulu:

-   bahasa target;
-   jenis dokumen;
-   apakah targetnya klasifikasi dokumen atau penandaan segmen;
-   apakah teks campuran akan menjadi kelas tersendiri;
-   model generator yang ingin diuji;
-   risiko false positive yang dapat diterima;
-   kebutuhan penjelasan hasil.

## 12.2 Pengumpulan dataset

Dua kelompok dasar:

**Human-written** - artikel atau esai dengan asal-usul yang jelas; -
tulisan yang dibuat manusia dan diperoleh secara etis; - dokumen dengan
izin penggunaan yang sesuai.

**AI-generated** - keluaran model yang dicatat nama dan versinya; -
prompt dan tanggal generasi; - parameter generasi jika tersedia; -
keluaran mentah sebelum penyuntingan.

Tambahkan kelompok teks campuran bila relevan. Catat seluruh proses
penyuntingan agar label tidak ambigu.

## 12.3 Skema metadata

Contoh kolom metadata:

  Kolom               Keterangan
  ------------------- ----------------------------------------
  document_id         Identitas internal dokumen
  text                Isi dokumen
  label               Human, AI, atau Mixed
  language            Bahasa
  domain              Akademik, umum, teknis, dan sebagainya
  generator           Nama model jika AI
  model_version       Versi model
  generation_date     Tanggal generasi
  prompt_id           Referensi prompt
  edited              Apakah teks disunting
  editing_method      Jenis penyuntingan
  source_provenance   Bukti asal-usul data
  split_group         Kelompok pemisahan data

Jangan menyimpan data pribadi yang tidak diperlukan. Pastikan hak
penggunaan data, persetujuan, dan ketentuan lisensi dipenuhi.

## 12.4 Kandidat fitur

  Kelompok      Kandidat fitur
  ------------- ----------------------------------------------
  Statistical   Perplexity, entropy, log-likelihood
  Lexical       TTR, MATTR, frekuensi kata, N-gram
  Syntactic     POS distribution, dependency features
  Structural    Rata-rata panjang kalimat, variasi paragraf
  Semantic      Sentence embeddings, semantic similarity
  Contextual    Representasi IndoBERT atau model multibahasa

Tidak semua fitur harus digunakan. Pilih berdasarkan hipotesis, kualitas
pengukuran, biaya komputasi, dan hasil ablation study.

## 12.5 Kandidat model

Model baseline: - Logistic Regression; - SVM; - Random Forest; -
Gradient Boosting.

Model neural: - BiLSTM; - Transformer encoder; - IndoBERT atau model
bahasa Indonesia/multibahasa yang sesuai.

Model hybrid: - gabungkan fitur statistik dan linguistik dengan
embedding Transformer; - lakukan feature fusion; - gunakan classifier
akhir seperti MLP atau Logistic Regression.

## 12.6 Arsitektur hybrid konseptual

``` text
                 INPUT DOCUMENT
                        |
                 PREPROCESSING
                        |
             +----------+----------+
             |                     |
             v                     v
      FEATURE BRANCH A       FEATURE BRANCH B
      Statistical &          Contextual
      Linguistic              Representation
             |                     |
             v                     v
      Perplexity, CV,         IndoBERT /
      lexical, syntax         Transformer
             |                     |
             +----------+----------+
                        |
                   FEATURE FUSION
                        |
                 CLASSIFICATION
                        |
               SCORE + UNCERTAINTY
                        |
             HUMAN / AI / MIXED /
                  UNCERTAIN
```

## 12.7 Ablation study

Ablation study menguji kontribusi komponen dengan membandingkan:

1.  fitur statistik saja;
2.  fitur linguistik saja;
3.  Transformer saja;
4.  statistik + linguistik;
5.  Transformer + fitur statistik;
6.  seluruh fitur hybrid.

Jika model hybrid tidak meningkatkan kinerja secara konsisten pada test
set lintas-domain, kompleksitas tambahan mungkin tidak sepadan.

## 12.8 Pencegahan data leakage

Data leakage dapat membuat hasil evaluasi terlihat lebih tinggi daripada
kemampuan sebenarnya.

Contoh kesalahan: - paragraf dari dokumen yang sama masuk ke training
dan testing; - versi parafrase dekat tersebar di dua split; - prompt
atau template yang sama mendominasi kedua split; - preprocessing atau
pemilihan fitur menggunakan informasi dari test set; - threshold dipilih
berdasarkan hasil test set final.

Solusi: - split berdasarkan dokumen atau kelompok sumber; - deduplikasi
sebelum split; - lakukan pemilihan fitur pada training/validation
saja; - gunakan validation set untuk pemilihan threshold; - simpan test
set final untuk evaluasi sekali pada akhir eksperimen.

------------------------------------------------------------------------

# 13. Contoh alur perhitungan dan pseudocode

Contoh berikut adalah ilustrasi konseptual. Nilai threshold dan fitur
bukan standar universal dan tidak boleh dipakai untuk menuduh penulis.

## 13.1 Pipeline sederhana

``` python
def detect_text(text):
    # 1. Validasi
    if not text or len(text.strip()) == 0:
        return {"status": "invalid_input"}

    # 2. Preprocessing
    normalized_text = normalize(text)
    sentences = split_sentences(normalized_text)
    tokens = tokenize(normalized_text)

    # 3. Feature extraction
    features = {
        "perplexity": calculate_perplexity(tokens),
        "sentence_cv": calculate_sentence_length_cv(sentences),
        "lexical_diversity": calculate_lexical_diversity(tokens),
        "repetition": calculate_repetition_features(tokens),
        "syntax": extract_syntactic_features(sentences),
        "embedding": create_contextual_embedding(normalized_text)
    }

    # 4. Classification
    score = trained_classifier.predict_score(features)

    # 5. Interpretasi
    # Threshold harus ditetapkan dari validation set.
    prediction = apply_validated_threshold(score)

    return {
        "score": score,
        "prediction": prediction,
        "limitations": "Model memberikan estimasi, bukan bukti kepengarangan."
    }
```

Fungsi seperti `normalize`, `calculate_perplexity`, dan
`trained_classifier` harus diimplementasikan menggunakan library dan
model yang dipilih. Pseudocode ini bukan program siap jalan.

## 13.2 Contoh agregasi skor segmen

Misalkan sistem menghitung skor untuk setiap segmen. Jika skor merupakan
nilai yang dapat dibandingkan dan panjang segmen digunakan sebagai
bobot, rata-rata berbobot dapat ditulis:

\[ S\_{doc}=`\frac{\sum_{i=1}^{m} n_i s_i}`{=tex}
{`\sum`{=tex}\_{i=1}\^{m} n_i} \]

Keterangan:

-   (m): jumlah segmen;
-   (n_i): jumlah token atau kata pada segmen ke-(i);
-   (s_i): skor segmen ke-(i).

Rumus ini hanya contoh agregasi. Penggunaannya harus sesuai dengan
definisi skor model. Jika skor segmen bukan skala yang sebanding,
rata-rata berbobot tidak tepat.

## 13.3 Threshold dan keputusan

Classifier dapat menghasilkan skor (s). Keputusan sederhana:

\[ `\hat{y}`{=tex}=
```{=tex}
\begin{cases}
AI, & s\geq t\\
Human, & s<t
\end{cases}
```
\]

Nilai (t) adalah threshold yang dipilih berdasarkan validation set dan
tujuan penggunaan. Threshold yang lebih rendah biasanya meningkatkan
recall tetapi dapat meningkatkan false positive; threshold lebih tinggi
dapat mengurangi false positive tetapi melewatkan lebih banyak teks AI.

Untuk sistem yang bertanggung jawab, rentang skor yang tidak meyakinkan
dapat dilaporkan sebagai `uncertain`, bukan dipaksa menjadi keputusan
biner.

------------------------------------------------------------------------

# 14. Prinsip interpretasi hasil

Sebelum menggunakan hasil AI Detector, periksa pertanyaan berikut:

1.  Apakah bahasa dokumen didukung oleh detector?
2.  Apakah dokumen memenuhi persyaratan panjang dan jenis konten?
3.  Apakah skor menunjukkan probabilitas, proporsi teks, atau skor
    internal?
4.  Apakah alat menandai kalimat, paragraf, atau keseluruhan dokumen?
5.  Apakah versi model dan tanggal pemeriksaan diketahui?
6.  Apakah model diuji pada domain dan generator yang relevan?
7.  Berapa tingkat false positive yang dilaporkan?
8.  Apakah terdapat bukti lain selain skor detector?

**Prinsip utama:** hasil AI Detector adalah indikator untuk pemeriksaan
lebih lanjut, bukan bukti tunggal bahwa seseorang menggunakan AI atau
melakukan pelanggaran akademik.

Untuk konteks akademik, hasil perlu ditafsirkan bersama kebijakan
institusi, proses penulisan, draf, catatan riset, sumber, dan
klarifikasi penulis. Pemeriksaan harus proporsional dan memberi
kesempatan kepada penulis untuk menjelaskan proses kerjanya.

------------------------------------------------------------------------

# 15. Kesimpulan

AI Detector bekerja dengan memperkirakan apakah karakteristik teks lebih
menyerupai teks yang dihasilkan AI atau teks yang ditulis manusia.
Sistem dapat menganalisis probabilitas token, perplexity, entropy,
variasi kalimat, kosakata, struktur sintaksis, representasi semantik,
dan gaya penulisan.

Fitur-fitur tersebut kemudian dapat digunakan oleh rule-based system,
machine learning classifier, deep learning model, atau pendekatan
zero-shot. Sebagian sistem memeriksa teks per segmen dan menggabungkan
skor menjadi laporan dokumen. Watermark detection merupakan pendekatan
berbeda karena memeriksa sinyal yang sengaja disisipkan saat generasi.

Tidak ada satu fitur yang dapat membuktikan asal-usul teks. Teks manusia
dan AI dapat memiliki karakteristik yang tumpang tindih. Karena itu,
false positive, false negative, dan distribution shift merupakan
persoalan penting.

Untuk membangun detector yang dapat dipertanggungjawabkan, diperlukan
dataset dengan provenance yang jelas, evaluasi lintas-model dan
lintas-domain, pencegahan data leakage, pelaporan FPR, kalibrasi skor,
serta interpretasi manusia. Dalam penggunaan akademik, AI Detector
sebaiknya menjadi alat bantu pemeriksaan, bukan satu-satunya dasar
keputusan.

------------------------------------------------------------------------

# 16. Referensi dan bacaan lanjutan

Daftar berikut merupakan titik awal untuk mempelajari bidang ini.
Periksa kembali metadata bibliografi, versi, dan tautan penerbit sebelum
menggunakannya dalam daftar pustaka akademik.

1.  **DetectGPT: Zero-Shot Machine-Generated Text Detection using
    Probability Curvature.** Mitchell et al. (2023). Membahas deteksi
    zero-shot melalui karakteristik log-probability teks dan perturbasi.
    -   https://arxiv.org/abs/2301.11305
2.  **Fast-DetectGPT: Efficient Zero-Shot Detection of Machine-Generated
    Text via Conditional Probability Curvature.** Membahas pendekatan
    deteksi yang lebih efisien berbasis probabilitas kondisional.
    -   https://arxiv.org/abs/2310.05130
3.  **GLTR: Statistical Detection and Visualization of Generated Text.**
    Gehrmann, Strobelt, dan Rush (2019). Memperkenalkan pendekatan
    visualisasi peringkat probabilitas token untuk membantu pemeriksaan
    teks generatif.
    -   https://aclanthology.org/P19-3019/
4.  **A Survey on LLM-Generated Text Detection: Necessity, Methods, and
    Future Directions.** Bacaan tinjauan untuk memahami metode dan
    tantangan deteksi teks hasil model bahasa besar.
    -   https://arxiv.org/
5.  **Turnitin -- AI Writing Detection and AI Writing Report
    documentation.** Dokumentasi resmi untuk memahami definisi skor,
    cakupan, batasan, dan interpretasi laporan produk.
    -   https://guides.turnitin.com/
6.  **GLTR project.** Implementasi dan penjelasan visualisasi statistik
    teks.
    -   https://gltr.io/

## Catatan penggunaan referensi

-   Artikel ilmiah harus diperiksa melalui laman penerbit atau
    repositori resmi.
-   Dokumentasi produk dapat berubah seiring pembaruan model.
-   Jangan menganggap metode penelitian tertentu sebagai cara kerja
    pasti produk komersial, kecuali penyedia produk mengungkapkannya.
-   Jangan mengutip angka performa dari satu dataset sebagai jaminan
    kinerja pada bahasa, domain, atau generator lain.
