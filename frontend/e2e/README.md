# E2E Playwright — ICALORA-LABS

Uji end-to-end menyeluruh terhadap stack yang sedang berjalan (frontend Next.js
di `:58030` + backend via proxy `/api/backend`).

## Menjalankan

```bash
cd frontend
npm run test:e2e              # semua tes
npm run test:e2e -- e2e/tests/security.spec.ts   # satu berkas
```

Runner (`e2e/run.sh`) otomatis mencetak cookie sesi **admin** (user id 14) dan
**user biasa** (id 1) dari kontainer `icalora-backend`, lalu menyuntikkannya ke
browser — sehingga alur terproteksi dapat diuji tanpa OAuth Google.

Override bila perlu: `BASE_URL`, `ADMIN_ID`, `USER_ID`.

## Cakupan

| Berkas | Fokus |
|---|---|
| `public.spec.ts` | Semua halaman publik + 19 halaman fitur: HTTP < 400, judul, **font termuat**, **tanpa error konsol**, **tanpa tautan mati**, tanpa overflow horizontal; **tombol back/forward**; toggle tema; dua metode login; pesan pendaftaran ditutup. |
| `security.spec.ts` | Kontrol akses URL kritikal: `/dashboard` & `/admin-000` tanpa login; API admin **401** (tanpa cookie), **403** (user biasa), cookie **palsu → 401**; mutasi PATCH/PUT body-valid tetap ditolak; sidebar non-admin tak memuat link admin; konfirmasi **tidak ada data berubah** akibat uji. |
| `admin.spec.ts` | Panel Super Admin: navigasi sidebar → panel, tab Pengguna (tabel, statistik, tombol aksi, pencarian), tab Pengaturan (toggle + ≥19 switch fitur), proteksi diri sendiri (tombol baris sendiri disabled), tombol Dashboard/Keluar. |
| `dashboard.spec.ts` | Semua halaman alat `/dashboard/tools/*` memuat sehat (read-only, tidak mengeksekusi LLM), riwayat & akun, collapse sidebar. |

> Catatan: uji bersifat **read-only** terhadap data produksi — tidak ada
> penghapusan, reset sandi, atau perubahan pengaturan yang dieksekusi.
