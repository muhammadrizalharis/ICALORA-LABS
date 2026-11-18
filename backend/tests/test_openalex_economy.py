"""Mode hemat kuota OpenAlex: jalur penting saja, tanpa duplikasi."""

import asyncio

import httpx

from app.services.plagiarism import online

_DOC = (
    "Pendahuluan\n"
    "Penataan pedagang kaki lima di pusat kota memerlukan kebijakan yang berpihak pada "
    "kelompok masyarakat berpenghasilan rendah dan keberlanjutan ruang publik secara "
    "menyeluruh bagi seluruh warga kota yang terdampak langsung oleh kebijakan tersebut.\n"
)


def test_sentence_search_for_openalex_is_off_by_default():
    fns = [fn for fn, _c, _s in online._provider_plan(120)]
    assert online._q_openalex not in fns
    assert online._q_crossref in fns  # penyedia lain tetap aktif


def test_sentence_search_can_be_enabled(monkeypatch):
    monkeypatch.setattr(online.settings, "openalex_sentence_search", True)
    assert online._q_openalex in [fn for fn, _c, _s in online._provider_plan(120)]
    monkeypatch.setattr(online.settings, "openalex_enabled", False)
    assert online._q_openalex not in [fn for fn, _c, _s in online._provider_plan(120)]


def test_global_switch_makes_no_http_call(monkeypatch):
    monkeypatch.setattr(online.settings, "openalex_enabled", False)
    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        return httpx.Response(200, json={})

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as c:
            return await online._get_json(c, "https://api.openalex.org/works", {})

    assert asyncio.run(run()) is None and calls["n"] == 0


def test_openalex_calls_are_counted_per_job(monkeypatch):
    monkeypatch.setattr(online, "_openalex_budget_exhausted", lambda: False)

    def handler(request):
        return httpx.Response(200, json={"results": []})

    async def run():
        counter = online.begin_rate_limit_tracking()
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as c:
            await online._get_json(c, "https://api.openalex.org/works", {})
            await online._get_json(c, "https://api.openalex.org/works", {})
            await online._get_json(c, "https://api.crossref.org/works", {})
        return counter

    assert asyncio.run(run())["_oa_calls"] == 2  # Crossref tidak dihitung


def _stub_stage1(monkeypatch, found: bool):
    queried: list[str] = []

    async def fake_title(client, q):
        queried.append(q)
        return [{"title": "Paper", "doi": "10.1/x", "_fulltext": "abs"}]

    async def fake_ft(client, doc):
        return [{"title": "Paper", "doi": "10.1/x", "_ft_hits": 3 if found else 0}]

    monkeypatch.setattr(online, "_q_title_throttled", fake_title)
    monkeypatch.setattr(online, "_q_fulltext_phrases", fake_ft)
    monkeypatch.setattr(online, "_distinct_term_queries", lambda d: ["istilah satu", "istilah dua"])
    monkeypatch.setattr(online, "_abstract_queries", lambda d: ["abstrak satu"])
    monkeypatch.setattr(online, "_extract_title", lambda d: "")
    return queried


def test_term_queries_skipped_when_identity_already_found(monkeypatch):
    queried = _stub_stage1(monkeypatch, found=True)
    asyncio.run(online._resolve_publication(None, _DOC))
    assert "istilah satu" not in queried and "abstrak satu" in queried


def test_term_queries_run_only_when_identity_not_found(monkeypatch):
    queried = _stub_stage1(monkeypatch, found=False)
    asyncio.run(online._resolve_publication(None, _DOC))
    assert {"istilah satu", "istilah dua", "abstrak satu"} <= set(queried)


def test_has_identity_hit_signals():
    assert online._has_identity_hit([{"title": "x", "_ft_hits": 2}], _DOC)
    assert not online._has_identity_hit([{"title": "Lain sama sekali", "_ft_hits": 1}], _DOC)
    assert not online._has_identity_hit([], _DOC)


def test_title_retry_only_after_429(monkeypatch):
    n = {"calls": 0}

    async def empty(client, title):
        n["calls"] += 1
        return []

    monkeypatch.setattr(online, "_q_title", empty)
    online.begin_rate_limit_tracking()
    asyncio.run(online._q_title_throttled(None, "judul"))
    assert n["calls"] == 1  # kosong sah -> tidak diulang

    n["calls"] = 0

    async def empty_429(client, title):
        n["calls"] += 1
        online._record_rate_limit("https://api.openalex.org/works")
        return []

    monkeypatch.setattr(online, "_q_title", empty_429)
    monkeypatch.setattr(online, "redis_client", lambda: (_ for _ in ()).throw(RuntimeError()))
    online.begin_rate_limit_tracking()
    asyncio.run(online._q_title_throttled(None, "judul"))
    assert n["calls"] == 2  # kosong karena 429 -> diulang sekali


def test_skip_identity_does_not_resolve(monkeypatch):
    called = {"n": 0}

    async def boom(*a, **k):
        called["n"] += 1
        return []

    monkeypatch.setattr(online, "_resolve_publication", boom)
    monkeypatch.setattr(online, "_provider_plan", lambda budget=0: [])
    monkeypatch.setattr(online, "_websearch_provider", lambda: None)
    monkeypatch.setattr(online.settings, "online_fulltext_enabled", False)
    asyncio.run(online._gather_candidates(_DOC, "", skip_identity=True))
    assert called["n"] == 0
    asyncio.run(online._gather_candidates(_DOC, "", skip_identity=False))
    assert called["n"] == 1
