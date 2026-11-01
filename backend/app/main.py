"""Titik masuk aplikasi FastAPI ICALORA-LABS by MRH INNOVEX."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import features, health, ingest, tools
from app.core.config import get_settings

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description="Backend ICALORA-LABS (akademik AI toolkit) by MRH INNOVEX",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(features.router)
app.include_router(tools.router)
app.include_router(ingest.router)


@app.get("/")
def root() -> dict:
    return {"name": settings.app_name, "status": "ok", "docs": "/docs"}
