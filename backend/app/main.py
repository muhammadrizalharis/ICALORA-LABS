"""Titik masuk aplikasi FastAPI ICALORA-LABS by MRH INNOVEX."""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import auth, features, health, ingest, tools
from app.core.config import DEFAULT_SESSION_SECRET, get_settings
from app.services.jobs import fail_orphaned_jobs

settings = get_settings()
logger = logging.getLogger("icalora.main")


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """Saat startup: tutup job yatim dari proses sebelumnya.

    Tugas latar belakang (mis. cek plagiarisme / deteksi AI) berjalan di dalam
    proses ini; bila proses mati/di-restart saat deploy, job yang sedang
    berjalan tidak akan pernah selesai. Tandai sebagai gagal agar klien langsung
    tahu dan dapat menjalankan ulang, bukan menunggu hingga batas waktu.
    """
    if get_settings().session_secret == DEFAULT_SESSION_SECRET:
        logger.critical(
            "SESSION_SECRET memakai nilai BAWAAN (publik): cookie sesi bisa dipalsukan "
            "siapa pun. Set SESSION_SECRET acak di backend/.env lalu restart backend & bot."
        )
    try:
        n = fail_orphaned_jobs()
        if n:
            logger.info("Menutup %d job yatim saat startup.", n)
    except Exception:  # noqa: BLE001
        logger.warning("Gagal menyapu job yatim saat startup.", exc_info=True)
    yield


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description="Backend ICALORA-LABS (akademik AI toolkit) by MRH INNOVEX",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(auth.router)
app.include_router(features.router)
app.include_router(tools.router)
app.include_router(ingest.router)


@app.get("/")
def root() -> dict:
    return {"name": settings.app_name, "status": "ok", "docs": "/docs"}
