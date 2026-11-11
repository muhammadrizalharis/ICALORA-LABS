import asyncio

from app.services.plagiarism import online as online_mod


def test_enrich_fulltext_falls_back_to_url(monkeypatch):
    """Kandidat identitas-publikasi dengan `_oa_url` mati tetapi `url` penerbit
    berisi teks penuh harus tetap diperkaya memakai `url` (ambil terpanjang).
    """
    paper_title = "Leveraging a Hybrid Fuzzy C-Means-PCA Model for Identifying Speech"
    doc = (paper_title + " in Children. ") * 30  # judul termuat → lolos gate

    dead_oa = "https://pdfs.semanticscholar.org/deadlink"
    good_url = "https://ojs.example.com/article/download/1/2"
    full_body = (paper_title + " full published body sentence. ") * 60

    async def fake_fetch(_client, url):
        return full_body if url == good_url else ""

    monkeypatch.setattr(online_mod, "_fetch_fulltext", fake_fetch)

    cands = [
        {
            "title": paper_title,
            "doi": None,
            "source": "Web",
            "_oa_url": dead_oa,
            "url": good_url,
            "_fulltext": "abstrak pendek " * 25,
        }
    ]

    asyncio.run(online_mod._enrich_fulltext(None, cands, doc, title_hint=paper_title))

    assert cands[0]["fulltext_oa"] is True
    assert cands[0]["_fulltext"] == full_body
    assert "teks penuh OA" in cands[0]["source"]


def test_q_searxng_parses_results(monkeypatch):
    """SearXNG mengembalikan judul/URL/snippet → kandidat terstruktur, dan URL
    .pdf ditandai sebagai _oa_url untuk diambil teks penuhnya."""

    class FakeResp:
        def json(self):
            return {
                "results": [
                    {
                        "title": "Fuzzy C-Means Clustering Study",
                        "url": "https://example.org/paper",
                        "content": "A study on fuzzy clustering and PCA.",
                    },
                    {
                        "title": "Direct PDF Source",
                        "url": "https://example.org/file.pdf",
                        "content": "snippet",
                    },
                    {"title": "", "url": None, "content": ""},  # dibuang
                ]
            }

    async def fake_get_json(_client, _url, _params):
        return FakeResp()

    monkeypatch.setattr(online_mod, "_get_json", fake_get_json)
    monkeypatch.setattr(online_mod.settings, "searxng_enabled", True)
    monkeypatch.setattr(online_mod.settings, "online_websearch_enabled", True)

    out = asyncio.run(online_mod._q_searxng(None, "fuzzy c-means pca"))
    assert len(out) == 2
    assert out[0]["source"] == "SearXNG"
    assert out[0]["_oa_url"] is None
    assert out[1]["_oa_url"] == "https://example.org/file.pdf"


def test_q_searxng_disabled_returns_empty(monkeypatch):
    monkeypatch.setattr(online_mod.settings, "searxng_enabled", False)
    out = asyncio.run(online_mod._q_searxng(None, "x"))
    assert out == []


def test_websearch_provider_prefers_searxng(monkeypatch):
    monkeypatch.setattr(online_mod.settings, "online_websearch_enabled", True)
    monkeypatch.setattr(online_mod.settings, "searxng_enabled", True)
    monkeypatch.setattr(online_mod.settings, "searxng_url", "http://127.0.0.1:1003")
    assert online_mod._websearch_provider() is online_mod._q_searxng
