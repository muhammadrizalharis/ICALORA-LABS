# Alur Kontribusi ICALORA-LABS

Repo ini melayani aplikasi **langsung dari direktori kerja**
(`~/ICALORA-LABS` menjalankan service systemd `icalora-backend` &
`icalora-frontend`). Karena itu branch `main` = versi yang sedang **live**.
Untuk menjaga web tetap stabil, ikuti alur berikut.

## Kebijakan hybrid

| Jenis perubahan | Alur |
|---|---|
| 🔴 Mendesak (bug live, service down, aset rusak) | Commit langsung ke `main`, lalu restart service |
| 🟢 Fitur / perubahan besar (fitur baru, refactor, perubahan skema DB) | Branch + Pull Request, review, baru merge |

## Pull Request lewat git worktree (wajib)

Jangan `git checkout` branch fitur di `~/ICALORA-LABS` — itu mengubah kode
yang dilayani service live. Pakai **worktree terpisah**:

```bash
cd ~/ICALORA-LABS
git fetch origin
git worktree add ~/icalora-pr/<nama-branch> -b <tipe>/<nama-branch> origin/main
# kerjakan perubahan di ~/icalora-pr/<nama-branch>
cd ~/icalora-pr/<nama-branch>
git add -A && git commit        # lihat konvensi commit di bawah
git push -u origin <tipe>/<nama-branch>
gh pr create --fill
```

Setelah PR di-merge (squash) di GitHub, deploy ke live:

```bash
cd ~/ICALORA-LABS
git pull --ff-only origin main
systemctl --user restart icalora-backend.service icalora-frontend.service
git worktree remove ~/icalora-pr/<nama-branch>
```

## Konvensi

- **Merge PR**: squash (1 commit rapi per PR).
- **Penulis commit**: `muhammadrizalharis <muhammadrizalharis@users.noreply.github.com>`.
- **Trailer**: setiap commit diakhiri
  `Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>`.
- **Pesan commit**: format `tipe(scope): ringkasan` (mis. `feat(plagiarism): ...`,
  `fix(ui): ...`, `perf(storage): ...`, `docs(todo): ...`).

## Pengingat penyimpanan & privasi

- Semua berkas pengguna disimpan di **VM Postgres** (bukan disk HPC) dan ikut
  **auto-purge 3 hari**.
- Jangan pernah menyentuh konfigurasi Ollama bersama.
- Jangan commit rahasia; `backend/.env` di-gitignore.
