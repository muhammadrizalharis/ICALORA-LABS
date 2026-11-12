#!/usr/bin/env bash
# Jalankan suite E2E Playwright terhadap stack yang sedang berjalan.
# Mint cookie sesi admin (id 14) & user biasa (id 1) langsung dari kontainer
# backend agar alur terproteksi dapat diuji tanpa OAuth.
set -euo pipefail

cd "$(dirname "$0")/.."

ADMIN_ID="${ADMIN_ID:-14}"
USER_ID="${USER_ID:-1}"

export BASE_URL="${BASE_URL:-http://127.0.0.1:58030}"
export ADMIN_TOKEN="$(docker exec icalora-backend python -c "from app.services import auth; print(auth.make_session_token(${ADMIN_ID}))")"
export USER_TOKEN="$(docker exec icalora-backend python -c "from app.services import auth; print(auth.make_session_token(${USER_ID}))")"

echo "BASE_URL=$BASE_URL  admin_id=$ADMIN_ID  user_id=$USER_ID"
npx playwright test --config e2e/playwright.config.ts "$@"
