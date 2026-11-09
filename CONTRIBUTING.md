# Alur Kontribusi ICALORA-LABS

Dokumen ini merangkum konvensi kontribusi untuk menjaga kualitas dan kerapihan
riwayat kode. ICALORA-LABS adalah perangkat lunak proprietary milik MRH INNOVEX
(lihat [LICENSE](./LICENSE)); kontribusi hanya untuk kolaborator yang diberi izin.

## Alur Perubahan

- **Perubahan besar** (fitur baru, refactor, perubahan skema DB): buat branch,
  ajukan Pull Request, review, lalu merge.
- **Perbaikan kecil / dokumentasi**: boleh langsung lewat PR ringkas.

```bash
git fetch origin
git switch -c <tipe>/<nama-branch> origin/main
# kerjakan perubahan
git add -A && git commit        # lihat konvensi di bawah
git push -u origin <tipe>/<nama-branch>
gh pr create --fill
```

## Konvensi

- **Merge PR**: squash (1 commit rapi per PR).
- **Pesan commit**: format `tipe(scope): ringkasan`
  (mis. `feat(plagiarism): ...`, `fix(ui): ...`, `perf(storage): ...`, `docs: ...`).

## Keamanan

- **Jangan pernah commit rahasia.** Berkas `.env` dan sejenisnya sudah di-gitignore.
- Pastikan tidak ada kredensial, token, atau data pribadi dalam perubahan Anda.
