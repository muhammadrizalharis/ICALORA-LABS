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
