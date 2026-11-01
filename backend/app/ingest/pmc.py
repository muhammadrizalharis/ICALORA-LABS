"""Worker ingest PMC Open Access — FULL-TEXT (keyless, anonim).

Sumber: s3://pmc-oa-opendata/<PMCID.VER>/<PMCID.VER>.{json,txt}
Menyimpan teks penuh terkompresi + MinHash (penting untuk similarity valid).

Resumable: ingest_jobs.cursor = prefix artikel terakhir yang selesai (StartAfter).

Jalankan:
    python -m app.ingest.pmc --target 500000
"""

from __future__ import annotations

import argparse
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
    ensure_schema,
    license_allows_fulltext,
    make_minhash,
    text_metrics,
)

BUCKET = "pmc-oa-opendata"
BATCH = 200
MIN_TEXT_CHARS = 200
MAX_TEXT_CHARS = 300_000  # batasi outlier sangat panjang

_STOP = False


def _handle_stop(signum, frame):  # noqa: ARG001
    global _STOP
    _STOP = True
    print(f"\n[pmc] sinyal {signum} diterima — menyimpan progres lalu berhenti…", flush=True)


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


def _persist(parsed: list[dict]) -> int:
    if not parsed:
        return 0
    docs = [{k: v for k, v in p.items() if k != "_minhash"} for p in parsed]
    ext_ids = [p["external_id"] for p in parsed]
    mh_by_ext = {p["external_id"]: p["_minhash"] for p in parsed}
    with engine.begin() as conn:
        conn.execute(_INSERT_DOC, docs)
        rows = conn.execute(_SELECT_IDS, {"source": "pmc", "ids": ext_ids}).all()
        fps = [
            {"doc_id": rid, "num_perm": NUM_PERM, "minhash": mh_by_ext[ext]}
            for ext, rid in rows
            if ext in mh_by_ext
        ]
        if fps:
            conn.execute(_INSERT_FP, fps)
    return len(docs)


def _year_from_citation(cit: str | None) -> int | None:
    if not cit:
        return None
    import re

    m = re.search(r"\b(1[6-9]\d\d|20\d\d)\b", cit)
    return int(m.group(1)) if m else None


def _fetch_article(s3, prefix: str) -> dict | None:
    base = prefix[:-1]  # buang '/'
    try:
        meta_raw = s3.get_object(Bucket=BUCKET, Key=f"{prefix}{base}.json")["Body"].read()
        meta = json.loads(meta_raw)
    except Exception:
        return None
    if meta.get("is_retracted") or not meta.get("is_pmc_openaccess", True):
        return None
    # Filter lisensi: hanya simpan full-text bila lisensi permisif (CC0/CC-BY/CC-BY-SA/PD).
    if not license_allows_fulltext(meta.get("license_code")):
        return None
    try:
        body = s3.get_object(Bucket=BUCKET, Key=f"{prefix}{base}.txt")["Body"].read()
        txt = body.decode("utf-8", "ignore").strip()
    except Exception:
        return None
    if len(txt) < MIN_TEXT_CHARS:
        return None
    txt = txt[:MAX_TEXT_CHARS]
    mh = make_minhash(txt)
    if mh is None:
        return None
    wc, cc = text_metrics(txt)
    return {
        "source": "pmc",
        "external_id": meta.get("pmcid") or base,
        "doi": meta.get("doi"),
        "title": (meta.get("title") or "")[:1000] or None,
        "license": meta.get("license_code"),
        "pub_year": _year_from_citation(meta.get("citation")),
        "lang": "en",
        "fields": [],
        "word_count": wc,
        "char_count": cc,
        "text_zstd": compress_text(txt),
        "_minhash": mh,
    }


def _get_or_create_job(target: int) -> tuple[int, str | None, int]:
    with engine.begin() as conn:
        row = conn.execute(
            text(
                "SELECT id, cursor, docs_ingested FROM ingest_jobs "
                "WHERE source='pmc' AND status IN ('running','paused') ORDER BY id DESC LIMIT 1"
            )
        ).first()
        if row:
            conn.execute(
                text("UPDATE ingest_jobs SET status='running', updated_at=now() WHERE id=:id"),
                {"id": row[0]},
            )
            print(f"[pmc] melanjutkan job #{row[0]} (sudah {row[2]} dok, start_after={row[1]})")
            return row[0], row[1], row[2]
        jid = conn.execute(
            text(
                "INSERT INTO ingest_jobs (source, status, docs_target, params) "
                "VALUES ('pmc','running',:t,:p) RETURNING id"
            ),
            {"t": target, "p": json.dumps({"method": "s3-per-article", "bucket": BUCKET})},
        ).scalar()
        print(f"[pmc] job baru #{jid} target={target}")
        return jid, None, 0


def _update_job(job_id: int, last_prefix: str | None, total: int, status: str) -> None:
    with engine.begin() as conn:
        conn.execute(
            text(
                "UPDATE ingest_jobs SET cursor=:c, docs_ingested=:n, status=:s, updated_at=now() "
                "WHERE id=:id"
            ),
            {"c": last_prefix, "n": total, "s": status, "id": job_id},
        )


def run(target: int) -> None:
    ensure_schema()
    job_id, start_after, total = _get_or_create_job(target)
    s3 = _s3()

    kwargs = {"Bucket": BUCKET, "Delimiter": "/"}
    if start_after:
        kwargs["StartAfter"] = start_after
    paginator = s3.get_paginator("list_objects_v2")

    buf: list[dict] = []
    last_prefix = start_after
    for page in paginator.paginate(**kwargs):
        if _STOP or total >= target:
            break
        for cp in page.get("CommonPrefixes", []):
            if _STOP or total >= target:
                break
            prefix = cp["Prefix"]
            if not prefix.startswith("PMC"):
                continue
            art = _fetch_article(s3, prefix)
            last_prefix = prefix
            if art:
                buf.append(art)
            if len(buf) >= BATCH:
                total += _persist(buf)
                buf.clear()
                _update_job(job_id, last_prefix, total, "running")
                print(f"[pmc] total {total}/{target} (…{last_prefix})", flush=True)

    if buf:
        total += _persist(buf)
        buf.clear()
    status = "done" if total >= target else "paused"
    _update_job(job_id, last_prefix, total, status)
    print(f"[pmc] berhenti ({status}) pada {total} dokumen.")


def main() -> None:
    ap = argparse.ArgumentParser(description="Ingest PMC Open Access full-text")
    ap.add_argument("--target", type=int, default=500_000)
    args = ap.parse_args()
    try:
        run(args.target)
    except Exception as exc:  # noqa: BLE001
        print(f"[pmc] FATAL: {exc}", file=sys.stderr)
        with engine.begin() as conn:
            conn.execute(
                text(
                    "UPDATE ingest_jobs SET status='error', last_error=:e, updated_at=now() "
                    "WHERE source='pmc' AND status='running'"
                ),
                {"e": str(exc)[:2000]},
            )
        sys.exit(1)


if __name__ == "__main__":
    main()
