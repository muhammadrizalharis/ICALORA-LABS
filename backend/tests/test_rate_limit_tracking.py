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


def test_daily_budget_429_trips_breaker_and_stops_calls(monkeypatch):
    fake = _FakeRedis()
    fake.set = lambda k, v, ex=None: fake.d.__setitem__(k, 1)
    monkeypatch.setattr(online, "redis_client", lambda: fake)
    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        return httpx.Response(
            429, json={"reason": "daily_budget", "retryAfter": 27553, "dailyRemainingUsd": 0}
        )

    async def run():
        counter = online.begin_rate_limit_tracking()
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            a = await online._get_json(client, "https://api.openalex.org/works", {})
            b = await online._get_json(client, "https://api.openalex.org/works", {})
            c = await online._get_json(client, "https://api.crossref.org/works", {})
        return counter, a, b, c

    counter, a, b, c = asyncio.run(run())
    assert a is None and b is None and c is None
    # OpenAlex 1x (lalu diputus) + Crossref 1x; panggilan ke-2 OpenAlex tak dikirim.
    assert calls["n"] == 2
    assert counter.get(online.BUDGET_FLAG) is True
    assert online.rate_limit_usage()["openalex_budget_exhausted"] is True


def test_plain_429_does_not_trip_breaker(monkeypatch):
    fake = _FakeRedis()
    fake.set = lambda k, v, ex=None: fake.d.__setitem__(k, 1)
    monkeypatch.setattr(online, "redis_client", lambda: fake)

    def handler(request):
        return httpx.Response(429, json={"reason": "burst"}, headers={"Retry-After": "600"})

    async def run():
        online.begin_rate_limit_tracking()
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await online._get_json(client, "https://api.openalex.org/works", {})

    assert asyncio.run(run()) is None
    assert online.rate_limit_usage()["openalex_budget_exhausted"] is False
