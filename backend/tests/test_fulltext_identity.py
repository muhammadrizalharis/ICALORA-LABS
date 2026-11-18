"""Identitas paper terbit via pencarian TEKS PENUH (dokumen tanpa judul/abstrak)."""

import asyncio

from app.services.plagiarism import online

_SENTS = [
    "Penataan pedagang kaki lima di pusat kota memerlukan kebijakan yang berpihak pada "
    "kelompok masyarakat berpenghasilan rendah dan keberlanjutan ruang publik.",
    "Relokasi pedagang ke lokasi baru sering menurunkan pendapatan harian apabila tidak "
    "disertai dukungan akses pelanggan serta promosi yang memadai bagi pedagang.",
    "Implementasi kebijakan yang tidak melibatkan pedagang dalam perencanaan cenderung "
    "menimbulkan resistensi serta konflik berkepanjangan antara aparat dan masyarakat.",
    "Dampak sosial ekonomi penataan ruang terlihat pada perubahan pola belanja konsumen "
    "dan jaringan sosial yang selama ini terbentuk di sekitar lokasi berdagang.",
]
_DOC = "Pendahuluan\n" + " ".join(_SENTS) + "\nDaftar Pustaka\n[1] Penulis, A. (2020) Judul.\n"


def test_fulltext_phrases_are_nine_words_spread_and_skip_references():
    ph = online._fulltext_phrases(_DOC, n=3)
    assert 1 <= len(ph) <= 3
    assert all(len(p.split()) == 9 for p in ph)
    assert not any("Penulis" in p for p in ph)
    assert online._fulltext_phrases("") == []
    assert online._fulltext_phrases("terlalu pendek.") == []


def test_fulltext_phrases_skip_urls_and_numeric_noise():
    noisy = (
        "Lihat https://contoh.org/abc untuk data lengkap tentang penataan ruang kota "
        "yang luas. "
    ) * 3
    assert online._fulltext_phrases(noisy) == []


def test_fulltext_candidates_need_two_distinct_phrase_hits(monkeypatch):
    target = {"title": "Paper Sasaran", "doi": "10.1/sasaran", "_fulltext": "abs"}
    other = {"title": "Paper Lain", "doi": "10.1/lain", "_fulltext": "abs"}
    answers = iter([[target, other], [dict(target)], [dict(target), dict(other)], []])

    async def fake(client, phrase):
        return next(answers, [])

    monkeypatch.setattr(online, "_q_openalex_fulltext", fake)
    monkeypatch.setattr(online, "_fulltext_phrases", lambda doc, n=6: ["a b", "c d", "e f", "g h"])
    out = asyncio.run(online._q_fulltext_phrases(None, "dokumen"))
    dois = {c["doi"]: c["_ft_hits"] for c in out}
    assert dois == {"10.1/sasaran": 3, "10.1/lain": 2}


def test_single_phrase_hit_is_not_enough(monkeypatch):
    only = {"title": "Kebetulan", "doi": "10.1/x", "_fulltext": "abs"}
    calls = iter([[only], [], []])

    async def fake(client, phrase):
        return next(calls, [])

    monkeypatch.setattr(online, "_q_openalex_fulltext", fake)
    monkeypatch.setattr(online, "_fulltext_phrases", lambda doc, n=6: ["a b", "c d", "e f"])
    assert asyncio.run(online._q_fulltext_phrases(None, "dokumen")) == []


def test_merge_dup_keeps_longest_text_and_max_hits():
    seen: dict[str, dict] = {}
    online._merge_dup(seen, "k", {"_fulltext": "pendek", "_ft_hits": 3, "_oa_url": "u"})
    online._merge_dup(seen, "k", {"_fulltext": "teks yang jauh lebih panjang", "_ft_hits": 1})
    assert seen["k"]["_fulltext"].startswith("teks yang jauh")
    assert seen["k"]["_ft_hits"] == 3 and seen["k"]["_oa_url"] == "u"
