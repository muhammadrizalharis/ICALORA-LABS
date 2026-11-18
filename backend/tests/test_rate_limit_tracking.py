"""Pemantauan HTTP 429 dari penyedia sumber daring."""

import asyncio

import httpx

from app.services.plagiarism import online


class _FakeRedis:
    def __init__(self):
        self.d: dict[str, int] = {}

    def incr(self, k):
        self.d[k] = self.d.get(k, 0) + 1
        return self.d[k]

    def expire(self, k, s):
        return True

    def get(self, k):
        return self.d.get(k)


def test_provider_name_maps_hosts():
    assert online._provider_name("https://api.openalex.org/works") == "openalex"
    assert online._provider_name("https://api.crossref.org/works") == "crossref"
    assert online._provider_name("https://api.unpaywall.org/v2/x") == "unpaywall"
    assert online._provider_name("https://contoh.example/x") == "other"


def test_429_counted_per_job_and_per_day(monkeypatch):
    fake = _FakeRedis()
    monkeypatch.setattr(online, "redis_client", lambda: fake)

    def handler(request):
        return httpx.Response(429, headers={"Retry-After": "600"})

    async def run():
        counter = online.begin_rate_limit_tracking()
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            r1 = await online._get_json(client, "https://api.openalex.org/works", {})
            r2 = await online._get_json(client, "https://api.crossref.org/works", {})
        return counter, r1, r2

    counter, r1, r2 = asyncio.run(run())
    assert r1 is None and r2 is None
    assert counter == {"openalex": 1, "crossref": 1}
    usage = online.rate_limit_usage()
    assert usage["hits"] == {"openalex": 1, "crossref": 1}


def test_no_tracking_context_does_not_break(monkeypatch):
    monkeypatch.setattr(online, "redis_client", lambda: _FakeRedis())
    online._RL_JOB.set(None)
    online._record_rate_limit("https://api.openalex.org/works")  # tidak boleh melempar


def test_redis_down_is_failsafe(monkeypatch):
    def boom():
        raise RuntimeError("redis mati")

    monkeypatch.setattr(online, "redis_client", boom)
    online._record_rate_limit("https://api.openalex.org/works")
    assert "error" in online.rate_limit_usage()
