# ICALORA-LABS frontend (Next.js) — build multi-tahap agar runtime ramping.
FROM node:22-slim AS builder

WORKDIR /app

# Install dependency dari lockfile (reproducible).
COPY package.json package-lock.json ./
RUN npm ci

# Salin sumber lalu build produksi.
COPY . .
RUN npm run build

# ---- Tahap runtime ----
FROM node:22-slim AS runner

ENV NODE_ENV=production
WORKDIR /app

# Hanya artefak yang diperlukan untuk `next start`.
COPY --from=builder /app/package.json /app/package-lock.json ./
COPY --from=builder /app/node_modules ./node_modules
COPY --from=builder /app/.next ./.next
COPY --from=builder /app/public ./public
COPY --from=builder /app/next.config.ts ./next.config.ts

RUN useradd -m -u 10002 webuser && chown -R webuser /app
USER webuser

EXPOSE 58030

# BACKEND_ORIGIN dipakai Route Handler proxy (default 127.0.0.1:58010 via host net).
# Bind ke 127.0.0.1 saja (host network) — hanya diakses lewat Cloudflare tunnel lokal.
CMD ["npx", "next", "start", "-p", "58030", "-H", "127.0.0.1"]
