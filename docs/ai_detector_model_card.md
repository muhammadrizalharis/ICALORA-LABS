# Model Card — AI Detector ICALORA (pipeline `2026.11-seg250-mlp-shortthr`)

## Ringkasan

| Aspek | Nilai |
|---|---|
| Model | MLP (1024 dim embedding bge-m3 + 6 fitur statistik → 128 ReLU → 1), dropout 0,2 |
| Berkas | `backend/app/services/ai_detector/model_emb.json` |
| Penggabung | `meta.blend_weights` = hanya embedding (statistik, model 6-fitur, LLM berbobot 0) |
| Kalibrasi | Platt seimbang, terpisah untuk teks < 300 kata dan ≥ 300 kata |
| Ambang (≥ 300 kata) | AI ≥ 50, campuran ≥ 25 |
| Ambang (< 300 kata) | AI ≥ 82,3, campuran ≥ 42,6 |
| Binoculars | tidak dipakai (terbalik pada model frontier) |

Ambang dipilih pada split **validasi** (manusia EN/ID) dengan target FPR ≤ 1 % (vonis AI)
dan ≤ 5 % (campuran), dengan batas bawah 50/25 agar skor tetap bermakna sebagai peluang.

## Data latih

- Data seed + `train_emb_v2/v2b` (model lokal: gemma, qwen, gpt-oss, sahabatai; termasuk humanized).
- 4.500 teks dari 10 model cloud (Claude Haiku/Sonnet/Opus 5.5, Gemini 3.8-flash/4-argon/4-hydrogen,
  GPT-6.1-sol, GPT-6-astra, Grok 4.7, Kimi K3), EN+ID, berbagai genre — termasuk 2.500 teks
  pendek (abstrak/paragraf 110–280 kata) khusus memperkuat recall teks pendek. Split per *prompt*
  (60/20/20) sehingga prompt yang sama tidak bocor antar-split.
- Manusia: 6.000 dokumen korpus pra-2021 (≥ 300 kata) + 3.500 abstrak pendek pra-2021
  (80–300 kata, EN/ID) + 1.388 jawaban manusia kasual HC3 (EN, pra-2023). Split per dokumen
  50/25/25. Tahun < 2021 (HC3 < 2023) dipilih agar label "manusia" pasti.
- Augmentasi format: teks AI diberi sitasi/angka/hard-wrap palsu, teks manusia dibersihkan,
  agar model tidak belajar jalan pintas format.

## Hasil (split test, pipeline produksi end-to-end, tanpa LLM)

| Kelompok | n | Vonis AI | Ditandai (AI/campuran) |
|---|---|---|---|
| AI cloud ≥ 300 kata | 295 | 99,7 % | 99,7 % |
| AI cloud < 300 kata | 629 | 98,1 % | 99,2 % |
| Manusia EN ≥ 300 kata | 825 | 0,5 % | 1,0 % |
| Manusia EN < 300 kata | 829 | 1,0 % | 2,2 % |
| Manusia ID ≥ 300 kata | 602 | 0,5 % | 0,5 % |
| Manusia ID < 300 kata | 336 | 0,9 % | 2,1 % |
| Manusia bahasa lain < 300 kata | 378 | 4,5 % | 10,6 % |

Dibanding model sebelumnya (v4e): recall teks AI pendek naik dari 94,0 % menjadi 98,1 %,
sementara FPR manusia (EN/ID) tetap ≤ 1 %. Manusia kasual EN (HC3) kini divonis AI 1,0 %
(sebelum pelatihan ulang ±2,7 %).

Eval set lama (429 dokumen, model lokal, sebagian besar < 300 kata), dibanding model sebelumnya (pr63):

| Kelompok | pr63: vonis AI | baru: vonis AI | pr63: ditandai | baru: ditandai |
|---|---|---|---|---|
| AI | 39 % | 53 % | 82 % | 80 % |
| AI di-humanize | 45 % | 47 % | 78 % | 73 % |
| Manusia | 5 % | 2,5 % | 18 % | 9 % |

Pada benchmark model cloud, model sebelumnya hanya menangkap ±4,7 %.

## Keterbatasan

- Teks < 300 kata (terutama abstrak) kurang andal: ambang dibuat lebih ketat sehingga
  sebagian teks AI pendek hanya ditandai "campuran".
- Bahasa selain Indonesia/Inggris: FPR lebih tinggi; laporan otomatis menandai keandalan "rendah".
- Generator baru di luar 14+ model di atas dan parafrase berat dapat menurunkan recall.
- Skor adalah estimasi statistik, bukan bukti kepengarangan.

## Reproduksi

1. `evaluate run --set <eval.jsonl> --out <hasil.jsonl> --no-llm --model <kandidat.json>` (kandidat tanpa kalibrasi).
2. Pilih Platt + ambang per panjang teks di split val, lalu tulis ke `meta.calibration`
   (`a`, `b`, `a_short`, `b_short`, `threshold_ai`, `threshold_mixed`,
   `threshold_ai_short`, `threshold_mixed_short`, `short_words`) dan `meta.blend_weights`.
