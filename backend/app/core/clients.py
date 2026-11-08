"""Klien koneksi ke infrastruktur: PostgreSQL, Redis, SeaweedFS (S3)."""

from __future__ import annotations

import boto3
import redis
from botocore.config import Config as BotoConfig
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from app.core.config import get_settings

settings = get_settings()

engine: Engine = create_engine(
    settings.database_url, pool_pre_ping=True, pool_size=5, max_overflow=10
)


def redis_client() -> redis.Redis:
    return redis.Redis.from_url(settings.redis_url, decode_responses=True)


_corpus_cache: dict[str, float] = {"size": 0.0, "ts": 0.0}
_embedded_cache: dict[str, float] = {"size": 0.0, "ts": 0.0}


def corpus_size() -> int:
    """Jumlah dokumen korpus (cache 5 menit) untuk cakupan laporan yang jujur.

    Dipakai semua fitur berbasis korpus (plagiarisme, sitasi, publikasi) agar
    melaporkan jumlah dokumen yang sebenarnya dibandingkan secara konsisten.
    """
    import time

    now = time.time()
    if now - _corpus_cache["ts"] < 300 and _corpus_cache["size"] > 0:
        return int(_corpus_cache["size"])
    try:
        with engine.connect() as conn:
            n = conn.execute(text("SELECT count(*) FROM corpus_documents")).scalar() or 0
    except Exception:  # noqa: BLE001
        n = int(_corpus_cache["size"])
    _corpus_cache["size"] = float(n)
    _corpus_cache["ts"] = now
    return int(n)


def embedded_corpus_size() -> int:
    """Jumlah dokumen korpus yang punya embedding semantik (cache 5 menit).

    Hanya dokumen ber-embedding yang bisa ditelusuri untuk deteksi PARAFRASE
    (pencarian vektor). Dipakai laporan agar jujur: cakupan semantik bisa lebih
    kecil dari total korpus, sehingga `paraphrase_similarity` punya konteks.
    """
    import time

    now = time.time()
    if now - _embedded_cache["ts"] < 300 and _embedded_cache["size"] > 0:
        return int(_embedded_cache["size"])
    try:
        with engine.connect() as conn:
            n = conn.execute(text("SELECT count(*) FROM corpus_embeddings")).scalar() or 0
    except Exception:  # noqa: BLE001
        n = int(_embedded_cache["size"])
    _embedded_cache["size"] = float(n)
    _embedded_cache["ts"] = now
    return int(n)


def s3_client():
    return boto3.client(
        "s3",
        endpoint_url=settings.s3_endpoint,
        aws_access_key_id=settings.s3_access_key,
        aws_secret_access_key=settings.s3_secret_key,
        region_name=settings.s3_region,
        config=BotoConfig(signature_version="s3v4"),
    )


def check_postgres() -> dict:
    with engine.connect() as conn:
        version = conn.execute(text("SELECT version()")).scalar()
        has_vector = conn.execute(
            text("SELECT EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'vector')")
        ).scalar()
    return {"ok": True, "version": version, "pgvector": bool(has_vector)}


def check_redis() -> dict:
    client = redis_client()
    try:
        pong = client.ping()
        return {"ok": bool(pong)}
    finally:
        client.close()


def check_s3() -> dict:
    client = s3_client()
    buckets = [b["Name"] for b in client.list_buckets().get("Buckets", [])]
    return {"ok": True, "buckets": buckets}


def check_llm() -> dict:
    import httpx

    base = settings.ollama_base_url.rstrip("/")
    with httpx.Client(timeout=10) as client:
        resp = client.get(f"{base}/api/tags")
        resp.raise_for_status()
        models = [m["name"] for m in resp.json().get("models", [])]
    return {
        "ok": True,
        "provider": settings.llm_provider,
        "model": settings.ollama_model,
        "model_available": settings.ollama_model in models,
    }
