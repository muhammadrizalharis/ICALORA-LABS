"""Worker ingest OpenAlex — streaming SNAPSHOT S3 (anonim, tanpa API key).

Membaca s3://openalex/data/jsonl/works/updated_date=*/part_*.gz secara streaming
(unduh-saat-baca, tanpa menyimpan file ke disk), mengekstrak abstrak + metadata,
menghitung MinHash, lalu menyimpan versi ringkas terkompresi ke Postgres.

Resumable: menyimpan 'key part terakhir yang selesai' di ingest_jobs.cursor.

Jalankan:
    python -m app.ingest.openalex --target 1000000
"""

from __future__ import annotations

import argparse
import gzip
import json
import signal
import sys

import boto3
from botocore import UNSIGNED
from botocore.config import Config as BotoConfig
from sqlalchemy import text

from app.core.clients import engine
from app.ingest.common import (
    NUM_PERM,
    compress_text,
    corpus_cap,
    corpus_cap_reached,
    ensure_schema,
    make_minhash,
    reconstruct_abstract,
    text_metrics,
)

BUCKET = "openalex"
WORKS_PREFIX = "data/jsonl/works/updated_date="
BATCH = 500
MIN_ABSTRACT_CHARS = 50

_STOP = False


def _handle_stop(signum, frame):  # noqa: ARG001
    global _STOP
    _STOP = True
    print(f"\n[ingest] sinyal {signum} diterima — menyimpan progres lalu berhenti…", flush=True)


signal.signal(signal.SIGTERM, _handle_stop)
signal.signal(signal.SIGINT, _handle_stop)


def _s3():
    return boto3.client("s3", config=BotoConfig(signature_version=UNSIGNED))


_INSERT_DOC = text(
    """
    INSERT INTO corpus_documents
        (source, external_id, doi, title, license, pub_year, lang, fields,
         word_count, char_count, text_zstd)
    VALUES
        (:source, :external_id, :doi, :title, :license, :pub_year, :lang, :fields,
         :word_count, :char_count, :text_zstd)
    ON CONFLICT (source, external_id) DO NOTHING
    """
)
_SELECT_IDS = text(
    "SELECT external_id, id FROM corpus_documents "
    "WHERE source = :source AND external_id = ANY(:ids)"
)
_INSERT_FP = text(
    "INSERT INTO corpus_fingerprints (doc_id, num_perm, minhash) "
    "VALUES (:doc_id, :num_perm, :minhash) ON CONFLICT (doc_id) DO NOTHING"
)


def _short_id(openalex_id: str) -> str:
    return openalex_id.rsplit("/", 1)[-1] if openalex_id else openalex_id


def _license_of(work: dict) -> str | None:
    for key in ("best_oa_location", "primary_location"):
        loc = work.get(key) or {}
        if loc.get("license"):
            return loc["license"]
    return None


def _fields_of(work: dict) -> list[str]:
    topic = work.get("primary_topic") or {}
    field = (topic.get("field") or {}).get("display_name")
    return [field] if field else []


def _parse_work(work: dict) -> dict | None:
    if work.get("is_paratext") or work.get("is_retracted"):
        return None
    abstract = reconstruct_abstract(work.get("abstract_inverted_index"))
    if not abstract or len(abstract) < MIN_ABSTRACT_CHARS:
        return None
    mh = make_minhash(abstract)
    if mh is None:
        return None
    wc, cc = text_metrics(abstract)
    doi = work.get("doi")
    if doi and doi.startswith("https://doi.org/"):
        doi = doi[len("https://doi.org/") :]
    title = work.get("title") or work.get("display_name")
    return {
        "source": "openalex",
        "external_id": _short_id(work.get("id", "")),
        "doi": doi,
        "title": (title or "")[:1000] or None,
        "license": _license_of(work),
        "pub_year": work.get("publication_year"),
        "lang": work.get("language"),
        "fields": _fields_of(work),
        "word_count": wc,
        "char_count": cc,
        "text_zstd": compress_text(abstract),
        "_minhash": mh,
    }


def _persist(parsed: list[dict]) -> int:
    if not parsed:
        return 0
    docs = [{k: v for k, v in p.items() if k != "_minhash"} for p in parsed]
    ext_ids = [p["external_id"] for p in parsed]
    mh_by_ext = {p["external_id"]: p["_minhash"] for p in parsed}
    with engine.begin() as conn:
        conn.execute(_INSERT_DOC, docs)
        rows = conn.execute(_SELECT_IDS, {"source": "openalex", "ids": ext_ids}).all()
        fps = [
            {"doc_id": rid, "num_perm": NUM_PERM, "minhash": mh_by_ext[ext]}
            for ext, rid in rows
            if ext in mh_by_ext
        ]
        if fps:
            conn.execute(_INSERT_FP, fps)
    return len(docs)


def _list_parts(s3) -> list[str]:
    """Semua key part works, diurut terbaru dulu (abstrak lebih lengkap)."""
    keys: list[str] = []
    paginator = s3.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=BUCKET, Prefix=WORKS_PREFIX):
        for obj in page.get("Contents", []):
            k = obj["Key"]
            if "/part_" in k and k.endswith(".gz"):
                keys.append(k)
    keys.sort(reverse=True)
    return keys


def _get_or_create_job(target: int) -> tuple[int, str | None, int]:
    with engine.begin() as conn:
        row = conn.execute(
            text(
                "SELECT id, cursor, docs_ingested FROM ingest_jobs "
                "WHERE source='openalex' AND status IN ('running','paused') "
                "ORDER BY id DESC LIMIT 1"
            )
        ).first()
        if row:
            conn.execute(
                text("UPDATE ingest_jobs SET status='running', updated_at=now() WHERE id=:id"),
                {"id": row[0]},
            )
            print(
                f"[ingest] melanjutkan job #{row[0]} (sudah {row[2]} dok, part terakhir={row[1]})"
            )
            return row[0], row[1], row[2]
        jid = conn.execute(
            text(
                "INSERT INTO ingest_jobs (source, status, docs_target, params) "
                "VALUES ('openalex','running',:t,:p) RETURNING id"
            ),
            {"t": target, "p": json.dumps({"method": "s3-snapshot", "bucket": BUCKET})},
        ).scalar()
        # Lanjutkan dari part terakhir job sebelumnya (jika ada) agar ingest MAJU
        # ke dokumen baru, bukan mengulang parts yang sama & menghasilkan duplikat.
        prev_cursor = conn.execute(
            text(
                "SELECT cursor FROM ingest_jobs "
                "WHERE source='openalex' AND id<>:id AND cursor IS NOT NULL "
                "ORDER BY id DESC LIMIT 1"
            ),
            {"id": jid},
        ).scalar()
        if prev_cursor:
            conn.execute(
                text("UPDATE ingest_jobs SET cursor=:c WHERE id=:id"),
                {"c": prev_cursor, "id": jid},
            )
            print(f"[ingest] job baru #{jid} target={target}, lanjut dari part={prev_cursor}")
        else:
            print(f"[ingest] job baru #{jid} target={target} (snapshot S3)")
        return jid, prev_cursor, 0


def _update_job(job_id: int, last_part: str | None, total: int, status: str) -> None:
    with engine.begin() as conn:
        conn.execute(
            text(
                "UPDATE ingest_jobs SET cursor=:c, docs_ingested=:n, status=:s, updated_at=now() "
                "WHERE id=:id"
            ),
            {"c": last_part, "n": total, "s": status, "id": job_id},
        )


def _stream_part(s3, key: str, target: int, total: int, buf: list[dict]) -> int:
    """Stream satu part; flush batch; kembalikan total terbaru."""
    body = s3.get_object(Bucket=BUCKET, Key=key)["Body"]
    gz = gzip.GzipFile(fileobj=body)
    for line in gz:
        if _STOP or total >= target:
            break
        try:
            work = json.loads(line)
        except json.JSONDecodeError:
            continue
        p = _parse_work(work)
        if p is None:
            continue
        buf.append(p)
        if len(buf) >= BATCH:
            total += _persist(buf)
            buf.clear()
    body.close()
    return total


def run(target: int) -> None:
    ensure_schema()
    job_id, last_part, total = _get_or_create_job(target)

    cap = corpus_cap()
    if corpus_cap_reached(exact=True):
        print(
            f"[ingest] korpus sudah mencapai plafon {cap} dokumen — "
            f"tidak menambah (set ICALORA_CORPUS_MAX_DOCS utk ubah).",
            flush=True,
        )
        _update_job(job_id, last_part, total, "paused")
        return

    s3 = _s3()
    parts = _list_parts(s3)
    print(f"[ingest] {len(parts)} part file ditemukan.")

    if last_part and last_part in parts:
        start = parts.index(last_part) + 1
        parts = parts[start:]
        print(f"[ingest] resume: lewati {start} part yang sudah selesai.")

    buf: list[dict] = []
    for key in parts:
        if _STOP or total >= target or corpus_cap_reached(exact=False):
            break
        try:
            total = _stream_part(s3, key, target, total, buf)
        except Exception as exc:  # noqa: BLE001
            if buf:
                total += _persist(buf)
                buf.clear()
            print(f"[ingest] gagal part {key}: {exc} — akan diulang saat resume.")
            _update_job(job_id, last_part, total, "running")
            continue
        if buf:
            total += _persist(buf)
            buf.clear()
        last_part = key
        _update_job(job_id, last_part, total, "running")
        print(f"[ingest] selesai part (total {total}/{target}) {key}", flush=True)

    if corpus_cap_reached(exact=False):
        status = "paused"
        print(f"[ingest] plafon korpus {cap} tercapai — berhenti menambah.", flush=True)
    else:
        status = "done" if total >= target else "paused"
    _update_job(job_id, last_part, total, status)
    print(f"[ingest] berhenti ({status}) pada {total} dokumen.")


def main() -> None:
    ap = argparse.ArgumentParser(description="Ingest OpenAlex snapshot ke korpus ICALORA-LABS")
    ap.add_argument("--target", type=int, default=1_000_000)
    args = ap.parse_args()
    try:
        run(args.target)
    except Exception as exc:  # noqa: BLE001
        print(f"[ingest] FATAL: {exc}", file=sys.stderr)
        with engine.begin() as conn:
            conn.execute(
                text(
                    "UPDATE ingest_jobs SET status='error', last_error=:e, updated_at=now() "
                    "WHERE source='openalex' AND status='running'"
                ),
                {"e": str(exc)[:2000]},
            )
        sys.exit(1)


if __name__ == "__main__":
    main()
