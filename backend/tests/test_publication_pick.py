"""Pemilihan bukti 'paper terbit': judul saja tidak cukup (regresi salah-tuduh Springer)."""

from app.services.plagiarism import (
    _TITLE_ZONE_CHARS,
    _front_matter,
    _pick_publication,
    _shingles,
    _title_in_front_matter,
)

TITLE = (
    "unarXive 2022: All arXiv Publications Pre-Processed for NLP, Including Structured Full-Text"
)


def _title_pub(**kw):
    base = {"title": TITLE, "doi": "10.1109/x", "by_doi": False, "by_title": True,
            "containment": 0.0, "_overlap": 1.0, "_fulltext_oa": False}
    return {**base, **kw}


def test_title_only_without_corroboration_is_rejected():
    # Kasus nyata: paper yang hanya DIKUTIP; kecocokan teks 0%, containment 0%, bukan teks penuh.
    assert _pick_publication(None, _title_pub(), None, {"10.1109/x": 0.0}) is None


def test_title_with_text_coverage_is_accepted_and_private_keys_removed():
    pm = _pick_publication(None, _title_pub(), None, {"10.1109/x": 12.0})
    assert pm and pm["by_title"] and "_overlap" not in pm and "_fulltext_oa" not in pm


def test_title_with_containment_or_fulltext_oa_is_accepted():
    assert _pick_publication(None, _title_pub(containment=45.0), None, {})
    assert _pick_publication(None, _title_pub(_fulltext_oa=True), None, {})


def test_coverage_below_threshold_is_rejected():
    assert _pick_publication(None, _title_pub(), None, {"10.1109/x": 4.9}) is None


def test_priority_doi_then_title_then_containment():
    doi, cont = {"doi": "d", "by_doi": True}, {"doi": "c", "by_title": False}
    assert _pick_publication(doi, _title_pub(containment=50.0), cont, {}) is doi
    assert _pick_publication(None, _title_pub(containment=50.0), cont, {})["doi"] == "10.1109/x"
    # judul tak terbukti -> jatuh ke containment (bukan None)
    assert _pick_publication(None, _title_pub(), cont, {}) is cont
    assert _pick_publication(None, None, None, {}) is None


def test_title_in_reference_entry_beyond_title_zone_is_ignored():
    # Naskah tanpa judul bab 'References': entri pustaka muncul setelah ±2800 karakter.
    filler = "Kalimat pengisi tentang metode penelitian dan hasil percobaan di lapangan. " * 40
    doc = filler + "Saier T, Krause J. " + TITLE + ". In: Proceedings of the conference."
    assert len(filler) > _TITLE_ZONE_CHARS
    zone = _front_matter(doc)[:_TITLE_ZONE_CHARS]
    words = [w.lower() for w in __import__("re").findall(r"[A-Za-z\u00C0-\u024F]+", zone)]
    assert _title_in_front_matter(TITLE, _shingles(words, 3)) == 0.0
    # judul sungguhan di awal dokumen tetap terdeteksi
    head = TITLE + "\nAuthor One, Author Two\nAbstract. " + filler
    zone2 = _front_matter(head)[:_TITLE_ZONE_CHARS]
    words2 = [w.lower() for w in __import__("re").findall(r"[A-Za-z\u00C0-\u024F]+", zone2)]
    assert _title_in_front_matter(TITLE, _shingles(words2, 3)) >= 0.7
