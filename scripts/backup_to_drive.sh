#!/usr/bin/env bash
# Backup ICALORA-LABS ke Google Drive (remote rclone 'gdrive').
#
# Tier COLD/arsip: pg_dump terkompresi zstd -> gdrive:ICALORA-LABS-Backups/db/
# Hanya menyentuh folder milik ICALORA. TIDAK PERNAH menyentuh folder proyek lain.
#
# Pemakaian:
#   scripts/backup_to_drive.sh              # backup DB penuh
#   KEEP=14 scripts/backup_to_drive.sh      # simpan 14 backup terbaru (default 7)
#
# Dipanggil manual atau via cron, mis. harian 03:00:
#   0 3 * * * /home/muhammadrizalharis/ICALORA-LABS/scripts/backup_to_drive.sh >> \
#       /home/muhammadrizalharis/ICALORA-LABS/backend/.logs/backup.log 2>&1
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="$ROOT/backend/.env"
RCLONE="$HOME/bin/rclone"
REMOTE="gdrive:ICALORA-LABS-Backups"
CONTAINER="icalora-postgres"
KEEP="${KEEP:-7}"

[ -f "$ENV_FILE" ] || { echo "[backup] .env tidak ditemukan: $ENV_FILE" >&2; exit 1; }
# Ambil kredensial DB dari .env (tidak pernah dicetak)
PGUSER="$(grep -E '^POSTGRES_USER=' "$ENV_FILE" | cut -d= -f2-)"
PGDB="$(grep -E '^POSTGRES_DB=' "$ENV_FILE" | cut -d= -f2-)"
PGPASS="$(grep -E '^POSTGRES_PASSWORD=' "$ENV_FILE" | cut -d= -f2-)"

TS="$(date -u +%Y%m%dT%H%M%SZ)"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
OUT="$TMP/icalora_${TS}.sql.zst"

echo "[backup] pg_dump ($PGDB) -> zstd …"
docker exec -e PGPASSWORD="$PGPASS" "$CONTAINER" \
  pg_dump -U "$PGUSER" -d "$PGDB" --no-owner --no-privileges \
  | zstd -q -T0 -12 -o "$OUT"

SIZE="$(du -h "$OUT" | cut -f1)"
echo "[backup] unggah $OUT ($SIZE) -> $REMOTE/db/"
"$RCLONE" copy "$OUT" "$REMOTE/db/" --no-traverse

echo "[backup] rotasi: simpan $KEEP terbaru"
mapfile -t OLD < <("$RCLONE" lsf "$REMOTE/db/" | sort -r | tail -n +"$((KEEP + 1))")
for f in "${OLD[@]:-}"; do
  [ -n "$f" ] || continue
  echo "[backup]   hapus lama: $f"
  "$RCLONE" deletefile "$REMOTE/db/$f"
done

echo "[backup] selesai $TS"
