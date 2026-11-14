#!/usr/bin/env bash
# Backup ICALORA-LABS ke Google Drive (remote rclone 'gdrive').
#
# 1. PENUH  : pg_dump | zstd | rclone rcat -> gdrive:ICALORA-LABS-Backups/db/
#             Dialirkan langsung ke Drive — TIDAK ada file di disk server.
# 2. INTI   : semua tabel kecuali ISI korpus (corpus_* tetap ada skemanya) ->
#             disimpan lokal di ~/backups/icalora-core (bila < MAX_LOCAL_MB) dan
#             juga ke gdrive:ICALORA-LABS-Backups/db-core/.
#
# Rotasi: backup baru selesai -> backup lama di luar KEEP terbaru dihapus permanen
# (tidak masuk Trash Drive), baik di Drive maupun lokal. Ukuran total tetap.
#
# Ramah server bersama:
# - kompresi 2 thread, nice 19, ionice idle (unit systemd juga CPUQuota=200%);
# - menunggu backup proyek lain (rclone/restic/unit backup) selesai dulu agar
#   tidak berebut jaringan, lalu unggah dengan --bwlimit.
#
# Hanya menyentuh folder milik ICALORA. TIDAK PERNAH menyentuh folder proyek lain.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="$ROOT/backend/.env"
RCLONE="$HOME/bin/rclone"
REMOTE="gdrive:ICALORA-LABS-Backups"
PG_IMAGE="pgvector/pgvector:pg16"
KEEP="${KEEP:-7}"
KEEP_LOCAL="${KEEP_LOCAL:-7}"
LOCAL_DIR="${LOCAL_DIR:-$HOME/backups/icalora-core}"
MAX_LOCAL_MB="${MAX_LOCAL_MB:-2048}"
ZSTD_THREADS="${ZSTD_THREADS:-2}"
ZSTD_LEVEL="${ZSTD_LEVEL:-3}"
BWLIMIT="${BWLIMIT:-30M}"
WAIT_MAX_MIN="${WAIT_MAX_MIN:-240}"
OTHER_UNITS="computehub-backup axon-backup codeunical-backup"

log() { echo "[backup $(date '+%F %T')] $*"; }

[ -f "$ENV_FILE" ] || { log ".env tidak ditemukan: $ENV_FILE" >&2; exit 1; }
env_get() { grep -E "^$1=" "$ENV_FILE" | cut -d= -f2-; }
PGUSER="$(env_get POSTGRES_USER)"
PGDB="$(env_get POSTGRES_DB)"
PGPASS="$(env_get POSTGRES_PASSWORD)"
PGHOST="$(env_get POSTGRES_HOST)"
PGPORT="$(env_get POSTGRES_PORT)"
PGPORT="${PGPORT:-5432}"
TS="$(date -u +%Y%m%dT%H%M%SZ)"

others_busy() {
  pgrep -u "$USER" -x rclone >/dev/null && return 0
  pgrep -u "$USER" -x restic >/dev/null && return 0
  # shellcheck disable=SC2086
  systemctl --user is-active --quiet $OTHER_UNITS 2>/dev/null && return 0
  return 1
}

waited=0
while others_busy && [ "$waited" -lt "$WAIT_MAX_MIN" ]; do
  [ "$waited" -eq 0 ] && log "backup lain sedang berjalan; menunggu …"
  sleep 60
  waited=$((waited + 1))
done
[ "$waited" -gt 0 ] && log "menunggu $waited menit"

dump() {  # $@ = opsi pg_dump tambahan
  docker run --rm -e PGPASSWORD="$PGPASS" "$PG_IMAGE" \
    pg_dump -h "$PGHOST" -p "$PGPORT" -U "$PGUSER" -d "$PGDB" \
    --no-owner --no-privileges "$@"
}
compress() { nice -n 19 ionice -c3 zstd -q -T"$ZSTD_THREADS" -"$ZSTD_LEVEL"; }
upload() {  # stdin -> $1/$2 (nama .partial dulu, diganti setelah sukses)
  "$RCLONE" rcat "$1/.partial-$2" --bwlimit "$BWLIMIT" --drive-chunk-size 64M
  "$RCLONE" moveto "$1/.partial-$2" "$1/$2"
}
rotate_remote() {  # $1=folder $2=prefix
  "$RCLONE" delete "$1" --include ".partial-*" --drive-use-trash=false 2>/dev/null || true
  mapfile -t old < <("$RCLONE" lsf "$1" --include "$2_*.sql.zst" | sort -r | tail -n +"$((KEEP + 1))")
  for f in "${old[@]}"; do
    [ -n "$f" ] || continue
    log "  hapus lama: $1/$f"
    "$RCLONE" deletefile "$1/$f" --drive-use-trash=false
  done
}

# 1) Inti (kecil): lokal + Drive
CORE="icalora-core_${TS}.sql.zst"
mkdir -p "$LOCAL_DIR"
log "dump inti (tanpa isi corpus_*) -> $LOCAL_DIR/$CORE"
dump --exclude-table-data='corpus_*' | compress > "$LOCAL_DIR/.partial-$CORE"
mv "$LOCAL_DIR/.partial-$CORE" "$LOCAL_DIR/$CORE"
size_mb=$(( $(stat -c %s "$LOCAL_DIR/$CORE") / 1048576 ))
"$RCLONE" copyto "$LOCAL_DIR/$CORE" "$REMOTE/db-core/$CORE" --bwlimit "$BWLIMIT"
if [ "$size_mb" -gt "$MAX_LOCAL_MB" ]; then
  log "inti ${size_mb} MB > ${MAX_LOCAL_MB} MB: tidak disimpan di server (hanya Drive)"
  rm -f "$LOCAL_DIR/$CORE"
fi
rm -f "$LOCAL_DIR"/.partial-*
mapfile -t old_local < <(ls -1 "$LOCAL_DIR"/icalora-core_*.sql.zst 2>/dev/null | sort -r | tail -n +"$((KEEP_LOCAL + 1))")
for f in "${old_local[@]}"; do [ -n "$f" ] && rm -f "$f"; done
rotate_remote "$REMOTE/db-core" icalora-core
log "inti selesai (${size_mb} MB)"

# 2) Penuh: dialirkan langsung ke Drive (tanpa disk lokal)
FULL="icalora_${TS}.sql.zst"
log "dump penuh -> $REMOTE/db/$FULL (streaming, bwlimit $BWLIMIT)"
dump | compress | upload "$REMOTE/db" "$FULL"
log "unggah selesai: $("$RCLONE" lsf "$REMOTE/db/" --include "$FULL" --format s | numfmt --to=iec)B"
rotate_remote "$REMOTE/db" icalora

log "selesai $TS"
