# 06 — Legalitas & Kepatuhan

Dokumen ini merangkum aturan main agar ICALORA-LABS aman secara hukum. **Ini bukan nasihat hukum resmi** — untuk kepastian, konsultasikan dengan ahli hukum/HKI.

---

## Prinsip Inti

> **"Bisa diakses publik" TIDAK sama dengan "bebas hak cipta".**
> Yang menentukan boleh/tidaknya menyimpan & memakai ulang adalah **LISENSI**, bukan apakah gratis dibaca.

- Hampir semua artikel jurnal dilindungi hak cipta otomatis, bahkan yang gratis dibaca.
- Menyimpan, mengindeks ulang, dan memakai komersial **memerlukan izin lisensi**.

---

## Boleh vs Tidak Boleh

| Sumber / Jenis | Simpan & pakai komersial? | Catatan |
|---|---|---|
| Open Access **CC-BY / CC0** (OpenAlex, PMC OA, sebagian DOAJ) | ✅ Ya | Wajib atribusi (kecuali CC0) |
| Metadata & abstrak via Crossref/OpenAlex | ✅ Umumnya ya | OpenAlex CC0 |
| Common Crawl (web publik) | ✅ Ya | Patuhi ketentuan |
| Artikel gratis dibaca tapi **©All rights reserved** | ❌ Tidak | Hak cipta penuh |
| Konten berbayar (Elsevier, Springer, IEEE, Wiley, dll) | ❌ Tidak | Melanggar ToS & hak cipta |
| Scraping di balik paywall | ❌ **Dilarang** | Risiko hukum serius |

---

## Aturan Operasional ICALORA-LABS

1. **Whitelist lisensi** — pipeline hanya menyimpan dokumen dengan lisensi yang jelas mengizinkan reuse.
2. **Simpan metadata lisensi** per dokumen (untuk atribusi & audit).
3. **Gunakan API resmi** — ambil data lewat API publik penyedia, bukan scraping yang melanggar ToS.
4. **Atribusi** — tampilkan sumber & lisensi pada hasil yang relevan.
5. **Hormati robots.txt & rate limit** saat mengakses sumber web.

---

## Privasi Data Pengguna

- Dokumen yang diunggah pengguna adalah **milik pengguna** — jangan masukkan ke korpus publik tanpa izin eksplisit.
- Enkripsi at-rest; sediakan opsi **hapus otomatis** setelah proses.
- Patuhi regulasi privasi yang relevan (mis. UU PDP Indonesia, dan GDPR bila melayani UE).
- Kebijakan privasi & ToS yang jelas untuk pengguna.

---

## Transparansi Fitur

- **AI Detector**: wajib menampilkan **disclaimer akurasi** — hasil bersifat probabilistik, tidak boleh dijadikan satu-satunya dasar menuduh plagiarisme/kecurangan.
- **Plagiarism Checker**: jelaskan bahwa cakupan korpus terbatas pada sumber open-access (bukan seluruh literatur dunia), agar ekspektasi pengguna realistis.

---

## Pembeda vs Turnitin (dan batasannya)

- Turnitin mahal karena **lisensi konten berbayar** + arsip tugas mahasiswa bertahun-tahun.
- ICALORA-LABS **tidak** mencakup konten berbayar → lebih murah, tetap berguna, dan **legal**.
- Komunikasikan batasan ini secara jujur sebagai bagian dari positioning produk.

---

## Checklist Sebelum Rilis Komersial
- [ ] Verifikasi lisensi setiap sumber korpus
- [ ] ToS & Kebijakan Privasi disusun
- [ ] Disclaimer AI Detector tampil jelas
- [ ] Mekanisme hapus data pengguna
- [ ] Konsultasi ahli hukum/HKI
- [ ] Pendaftaran merek (DJKI/dgip.go.id)
