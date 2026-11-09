"""Antrean pekerjaan sisi-server untuk tugas berat (mis. cek plagiarisme).

Berbeda dari "job" sisi-klien (yang tetap menahan satu koneksi HTTP terbuka
selama proses, sehingga rawan kena batas waktu proxy ~100 dtk), modul ini
menjalankan pekerjaan di latar belakang proses backend: klien mengirim tugas,
langsung menerima `job_id`, lalu menanyai (polling) status sampai selesai.

State job disimpan di Postgres yang sama dengan riwayat agar dapat ditanyai
lintas-permintaan. Hasil akhir ditautkan ke `tool_history` lewat `history_id`.
"""

from __future__ import annotations

import json
import uuid

from sqlalchemy import text

from app.core.clients import engine

_JOB_SCHEMA_READY = False


def ensure_job_schema() -> None:
    global _JOB_SCHEMA_READY
    if _JOB_SCHEMA_READY:
        return
    with engine.begin() as c:
        c.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS tool_job (
                    id          text PRIMARY KEY,
                    user_id     bigint,
                    tool        text NOT NULL,
                    title       text,
                    status      text NOT NULL DEFAULT 'processing',
                    history_id  bigint,
                    error       text,
                    created_at  timestamptz NOT NULL DEFAULT now(),
                    updated_at  timestamptz NOT NULL DEFAULT now()
                )
                """
            )
        )
        c.execute(text("CREATE INDEX IF NOT EXISTS idx_tool_job_user ON tool_job(user_id)"))
    _JOB_SCHEMA_READY = True


def create_job(user_id: int | None, tool: str, title: str | None) -> str:
    ensure_job_schema()
    job_id = uuid.uuid4().hex
    with engine.begin() as c:
        c.execute(
            text(
                """
                INSERT INTO tool_job (id, user_id, tool, title, status)
                VALUES (:id, :uid, :tool, :title, 'processing')
                """
            ),
            {"id": job_id, "uid": user_id, "tool": tool, "title": (title or "")[:200]},
        )
    return job_id


def complete_job(job_id: str, history_id: int | None) -> None:
    ensure_job_schema()
    with engine.begin() as c:
        c.execute(
            text(
                """
                UPDATE tool_job
                SET status='done', history_id=:hid, updated_at=now()
                WHERE id=:id
                """
            ),
            {"id": job_id, "hid": history_id},
        )


def fail_job(job_id: str, message: str) -> None:
    ensure_job_schema()
    with engine.begin() as c:
        c.execute(
            text(
                """
                UPDATE tool_job
                SET status='error', error=:err, updated_at=now()
                WHERE id=:id
                """
            ),
            {"id": job_id, "err": (message or "Terjadi kesalahan.")[:500]},
        )


def get_job(job_id: str, user_id: int | None) -> dict | None:
    ensure_job_schema()
    with engine.begin() as c:
        row = c.execute(
            text(
                """
                SELECT id, user_id, tool, title, status, history_id, error
                FROM tool_job WHERE id=:id
                """
            ),
            {"id": job_id},
        ).first()
    if not row:
        return None
    # Job milik pengguna lain tidak boleh terbaca (job anonim boleh dibaca siapa pun).
    if row.user_id is not None and user_id is not None and row.user_id != user_id:
        return None
    return {
        "id": row.id,
        "tool": row.tool,
        "title": row.title,
        "status": row.status,
        "history_id": row.history_id,
        "error": row.error,
    }


def purge_expired_jobs(hours: int = 24) -> int:
    ensure_job_schema()
    with engine.begin() as c:
        res = c.execute(
            text(
                "DELETE FROM tool_job "
                "WHERE created_at < now() - make_interval(hours => :h)"
            ),
            {"h": max(1, int(hours))},
        )
    return res.rowcount or 0
