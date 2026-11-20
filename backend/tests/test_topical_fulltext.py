"""Jalur cadangan topikal: paper asli naskah tanpa judul/abstrak tetap diunduh teks penuhnya."""

import asyncio

from app.services.plagiarism import online as om

_TOPIC = (
    "students cognitive offloading generative assistants reliance critical thinking "
    "learning outcomes academic performance dependence reasoning memory creativity "
    "metacognition engagement motivation assessment feedback literacy"
)
# Naskah memakai kata-kata topik itu di isinya, tetapi TANPA abstrak dan tanpa judul paper.
DOC = (
    "Prior work on cognitive offloading shows students reliance on generative assistants "
    "reduces critical thinking and reasoning, affecting learning outcomes, memory, creativity, "
    "metacognition, engagement, motivation, assessment, feedback and literacy in academic "
    "performance and dependence. "
) * 12


def _cand(title, abstract, doi):
    return {"title": title, "doi": doi, "source": "OpenAlex", "url": f"https://x/{doi}",
            "_oa_url": f"https://x/{doi}.pdf", "_fulltext": abstract}


def _setup(monkeypatch, fetched):
    async def fake_fetch(_c, url):
        fetched.append(url)
        return "isi teks penuh paper yang sangat panjang. " * 400

    async def no_unpaywall(_c, _d):
        return None

    monkeypatch.setattr(om, "_fetch_fulltext", fake_fetch)
    monkeypatch.setattr(om, "_unpaywall_oa_pdf", no_unpaywall)
    monkeypatch.setattr(om.online_cache, "get", lambda k: None)
    monkeypatch.setattr(om.online_cache, "put", lambda k, v: None)


def test_content_words_and_topic_score():
    cw = om._content_words(DOC)
    assert "students" in cw and "the" not in cw and "of" not in cw
    on = _cand("Relevan", _TOPIC, "10.1/a")
    off = _cand("Lain", "harvest market budget farming rainfall irrigation " * 6, "10.1/b")
    assert om._topic_score(on, cw) >= om._TOPIC_MIN_SCORE
    assert om._topic_score(off, cw) < om._TOPIC_MIN_SCORE
    # abstrak terlalu pendek -> 0 (tak layak dinilai)
    assert om._topic_score(_cand("Pendek", "students reliance", "10.1/c"), cw) == 0.0


def test_topical_candidate_gets_fulltext_even_without_abstract_in_doc(monkeypatch):
    fetched: list[str] = []
    _setup(monkeypatch, fetched)
    target = _cand("Paper Sasaran Tanpa Kata Judul Sama", _TOPIC, "10.1/target")
    farm = "harvest market budget farming rainfall irrigation " * 6
    other = _cand("Paper Pertanian", farm, "10.1/o")
    cands = [other, target]
    asyncio.run(om._enrich_fulltext(None, cands, DOC, title_hint=""))
    assert target.get("fulltext_oa") is True and len(target["_fulltext"]) > 10_000
    assert not other.get("fulltext_oa")  # tak sepokok -> tak diunduh
    assert any("10.1/target" in u for u in fetched)
    assert not any("10.1/o" in u for u in fetched)


def test_topical_pool_is_capped(monkeypatch):
    fetched: list[str] = []
    _setup(monkeypatch, fetched)
    monkeypatch.setattr(om.settings, "online_fulltext_topical_docs", 3)
    cands = [_cand(f"Paper {i}", _TOPIC, f"10.1/p{i}") for i in range(10)]
    asyncio.run(om._enrich_fulltext(None, cands, DOC, title_hint=""))
    assert len({u for u in fetched if u.endswith(".pdf")}) <= 3
    assert sum(1 for c in cands if c.get("fulltext_oa")) <= 3


def test_topical_disabled_when_cap_zero(monkeypatch):
    fetched: list[str] = []
    _setup(monkeypatch, fetched)
    monkeypatch.setattr(om.settings, "online_fulltext_topical_docs", 0)
    cands = [_cand("Paper A", _TOPIC, "10.1/a")]
    asyncio.run(om._enrich_fulltext(None, cands, DOC, title_hint=""))
    assert fetched == [] and not cands[0].get("fulltext_oa")
