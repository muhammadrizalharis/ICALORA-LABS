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
