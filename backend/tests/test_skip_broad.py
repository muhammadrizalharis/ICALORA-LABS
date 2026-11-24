"""Lewati pencarian luas hanya bila SATU paper teks-penuh OA memuat hampir seluruh dokumen."""

import random

from app.services.plagiarism import online as on

_RNG = random.Random(7)
_VOCAB = [f"kata{i}" for i in range(4000)]


def _words(n):
    return " ".join(_RNG.choice(_VOCAB) for _ in range(n))


SRC_TEXT = _words(3000)


def _cand(text=SRC_TEXT, oa=True, title="Paper Sumber"):
    return {"title": title, "_fulltext": text, "fulltext_oa": oa}


def test_document_copied_from_source_is_fully_covered():
    doc = " ".join(SRC_TEXT.split()[200:1200])
    cov, best = on.single_source_coverage(doc, [_cand()])
    assert cov >= 99 and best["title"] == "Paper Sumber"


def test_half_original_document_is_below_threshold():
    words = SRC_TEXT.split()
    doc = " ".join(words[100:600]) + " " + _words(500)
    cov, _ = on.single_source_coverage(doc, [_cand()])
    assert 40 <= cov <= 60  # jauh di bawah ambang 90 -> pencarian luas tetap jalan


def test_unrelated_document_and_non_oa_or_short_sources_do_not_count():
    doc = _words(800)
    assert on.single_source_coverage(doc, [_cand()])[0] < 5
    copied = " ".join(SRC_TEXT.split()[:800])
    assert on.single_source_coverage(copied, [_cand(oa=False)]) == (0.0, None)
    assert on.single_source_coverage(copied, [_cand(text="pendek " * 50)]) == (0.0, None)


def test_short_documents_never_skip():
    short = " ".join(SRC_TEXT.split()[:120])
    assert on.single_source_coverage(short, [_cand()]) == (0.0, None)


def test_best_of_several_candidates_is_chosen():
    doc = " ".join(SRC_TEXT.split()[:900])
    other = _cand(text=_words(3000), title="Lain")
    cov, best = on.single_source_coverage(doc, [other, _cand()])
    assert best["title"] == "Paper Sumber" and cov >= 99
