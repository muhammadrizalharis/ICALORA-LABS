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


def test_fetch_fulltext_resilient_retries_on_transient_failure(monkeypatch):
    """Unduhan teks-penuh yang gagal transient (kosong) harus diulang hingga
    berhasil, agar kandidat identitas tidak jatuh ke abstrak saja (55%→23%).
    """
    full_body = "published full body sentence. " * 60
    calls = {"n": 0}

    async def flaky_fetch(_client, _url):
        calls["n"] += 1
        return full_body if calls["n"] >= 3 else ""

    monkeypatch.setattr(online_mod, "_fetch_fulltext", flaky_fetch)
    monkeypatch.setattr(online_mod.settings, "online_fulltext_fetch_attempts", 3)

    out = asyncio.run(
        online_mod._fetch_fulltext_resilient(None, "https://ojs.example.com/a/1")
    )

    assert out == full_body
    assert calls["n"] == 3


def test_fetch_fulltext_resilient_gives_up_when_all_fail(monkeypatch):
    """Bila semua percobaan gagal, kembalikan string kosong (tanpa galat)."""

    async def always_empty(_client, _url):
        return ""

    monkeypatch.setattr(online_mod, "_fetch_fulltext", always_empty)
    monkeypatch.setattr(online_mod.settings, "online_fulltext_fetch_attempts", 3)

    out = asyncio.run(online_mod._fetch_fulltext_resilient(None, "https://x/y"))

    assert out == ""


def test_clean_preserves_math_notation():
    """`_clean` tak boleh membuang notasi matematis PDF (`p < 0.05`, `x > 3`).

    Pola tag HTML lama (`<[^>]+>`) rakus: pada teks PDF, `<` dari sebuah
    pertidaksamaan hingga `>` berikutnya yang jauh ikut terhapus, membuang
    puluhan persen isi sehingga sumber IDENTIK pun tak pernah 100%. `_clean`
    kini hanya membuang TAG HTML asli dan mempertahankan teks matematis.
    """
    pdf_text = (
        "Hasil menunjukkan korelasi signifikan dengan p < 0.05 pada kluster "
        "pertama, sementara komponen kedua memberi skor < -0.7 yang menandai "
        "deviasi prosodik, dan ambang x > 3 dipakai untuk seleksi fitur."
    )
    out = online_mod._clean(pdf_text)
    assert "p < 0.05" in out
    assert "< -0.7" in out
    assert "x > 3" in out
    # Panjang isi tetap utuh (tak ada rentang antar `<...>` yang terhapus).
    assert len(out) >= len(pdf_text) - 2


def test_clean_still_strips_html_tags():
    """Tag HTML/XML asli tetap dibuang (abstrak JATS, halaman penerbit)."""
    html = "<jats:p>Kami mengkaji <b>PCA</b> dan <i>FCM</i>.</jats:p><br/>"
    out = online_mod._clean(html)
    assert "<jats:p>" not in out and "</jats:p>" not in out
    assert "<b>" not in out and "<i>" not in out and "<br/>" not in out
    assert "Kami mengkaji" in out and "PCA" in out and "FCM" in out
