"""Endpoint health & kesiapan infrastruktur."""

from fastapi import APIRouter

from app.core.clients import check_llm, check_postgres, check_redis, check_s3
from app.core.config import get_settings

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "icalora-labs-api"}


def _infra() -> dict:
    results: dict[str, dict] = {}
    for name, fn in (
        ("postgres", check_postgres),
        ("redis", check_redis),
        ("s3", check_s3),
        ("llm", check_llm),
    ):
        try:
            results[name] = fn()
        except Exception as exc:  # noqa: BLE001
            results[name] = {"ok": False, "error": str(exc)}
    overall = all(r.get("ok") for r in results.values())
    return {"status": "ok" if overall else "degraded", "services": results}


@router.get("/health/infra")
def health_infra() -> dict:
    return _infra()


def _websearch() -> dict:
    """Konfigurasi + pemakaian kuota layer web-search (verifikasi daring)."""
    s = get_settings()
    try:
        from app.services.plagiarism.online import websearch_usage

        usage = websearch_usage()
    except Exception as exc:  # noqa: BLE001
        usage = {"used": -1, "cap": s.online_websearch_monthly_cap, "error": str(exc)}
    if s.tavily_api_key:
        provider = "tavily"
    elif s.brave_api_key:
        provider = "brave"
    else:
        provider = None
    used = usage.get("used", -1)
    cap = usage.get("cap", s.online_websearch_monthly_cap)
    remaining = (cap - used) if (isinstance(used, int) and used >= 0 and cap > 0) else None
    return {
        "enabled": s.online_websearch_enabled,
        "provider": provider,
        "providers_configured": {
            "tavily": bool(s.tavily_api_key),
            "brave": bool(s.brave_api_key),
        },
        "sentences_per_paper": s.online_websearch_sentences,
        "results_per_sentence": s.online_websearch_per_sentence,
        "month": usage.get("month"),
        "used": used,
        "cap": cap,
        "remaining": remaining,
        "ok": bool(s.online_websearch_enabled and provider and used != -1),
    }


@router.get("/health/providers")
def health_providers() -> dict:
    return _websearch()


@router.get("/health/status")
def health_status() -> dict:
    """Ringkasan kesehatan menyeluruh untuk pemantauan (bot/admin).

    Menggabungkan: health API, infrastruktur (DB/Redis/S3/LLM), layer
    web-search (kuota + penyedia), dan ringkasan korpus/ingest.
    """
    infra = _infra()
    websearch = _websearch()

    corpus: dict = {}
    try:
        from app.api.ingest import status as ingest_status

        corpus = ingest_status()
    except Exception as exc:  # noqa: BLE001
        corpus = {"error": str(exc)}

    infra_ok = infra.get("status") == "ok"
    overall = "ok" if infra_ok else "degraded"
    return {
        "status": overall,
        "service": "icalora-labs-api",
        "infra": infra,
        "websearch": websearch,
        "corpus": corpus,
    }
