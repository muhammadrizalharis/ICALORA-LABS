"""Endpoint status ingest korpus."""

from fastapi import APIRouter
from sqlalchemy import text

from app.core.clients import engine

router = APIRouter(prefix="/ingest", tags=["ingest"])


@router.get("/status")
def status() -> dict:
    with engine.connect() as conn:
        jobs = (
            conn.execute(
                text(
                    "SELECT id, source, status, docs_ingested, docs_target, last_error, "
                    "started_at, updated_at FROM ingest_jobs ORDER BY id DESC LIMIT 20"
                )
            )
            .mappings()
            .all()
        )
        total_docs = conn.execute(text("SELECT count(*) FROM corpus_documents")).scalar()
        by_source = (
            conn.execute(text("SELECT source, count(*) AS n FROM corpus_documents GROUP BY source"))
            .mappings()
            .all()
        )
    return {
        "total_documents": total_docs,
        "by_source": {r["source"]: r["n"] for r in by_source},
        "jobs": [dict(j) for j in jobs],
    }
