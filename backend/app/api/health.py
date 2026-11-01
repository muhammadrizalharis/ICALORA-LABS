"""Endpoint health & kesiapan infrastruktur."""

from fastapi import APIRouter

from app.core.clients import check_postgres, check_redis, check_s3

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "icalora-labs-api"}


@router.get("/health/infra")
def health_infra() -> dict:
    results: dict[str, dict] = {}
    for name, fn in (("postgres", check_postgres), ("redis", check_redis), ("s3", check_s3)):
        try:
            results[name] = fn()
        except Exception as exc:  # noqa: BLE001
            results[name] = {"ok": False, "error": str(exc)}
    overall = all(r.get("ok") for r in results.values())
    return {"status": "ok" if overall else "degraded", "services": results}
