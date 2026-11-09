# ICALORA-LABS backend (FastAPI/uvicorn) + bot Telegram.
# Image tunggal dipakai dua service (backend & bot) dengan perintah berbeda.
FROM python:3.10-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# Dependensi sistem:
# - WeasyPrint butuh pango/cairo/gdk-pixbuf/ffi + font untuk render PDF HTML
# - ffmpeg untuk faster-whisper (ASR) via PyAV
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpango-1.0-0 libpangocairo-1.0-0 libcairo2 libgdk-pixbuf-2.0-0 \
    libffi-dev shared-mime-info fonts-dejavu-core fonts-liberation \
    ffmpeg curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install dependency Python lebih dulu (layer cache) lalu kode.
COPY pyproject.toml ./
COPY app ./app
RUN pip install --no-cache-dir .

# Buat folder log (dipakai beberapa modul) dan user non-root.
RUN mkdir -p /app/.logs && useradd -m -u 10001 appuser && chown -R appuser /app
USER appuser

EXPOSE 58010

# Default: jalankan API. Service bot menimpa command di compose.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "58010"]
