"""Deteksi parafrase semantik terhadap teks penuh kandidat (embedding dipalsukan)."""

import numpy as np
import pytest

from app.services.plagiarism import semantic as sem


class FakeLLM:
    """Embedding deterministik: tiap konsep (kata kunci) = satu sumbu; makna sama = vektor sama."""

    CONCEPTS = ["vortex", "sediment", "porous", "network", "harvest", "budget", "pasar", "cuaca"]

    def embed_batch(self, texts):
        out = []
        for t in texts:
            v = np.zeros(len(self.CONCEPTS) + 1, dtype=np.float32)
            low = t.lower()
            hit = False
            for i, c in enumerate(self.CONCEPTS):
                if c in low:
                    v[i] = 1.0
                    hit = True
            if not hit:
                v[-1] = 1.0
            out.append(v.tolist())
        return out


def _text(topic_words, n=40):
    # Kalimat panjang berbeda-beda agar lolos filter panjang; kata kunci menentukan "makna".
    return " ".join(
        f"Kalimat nomor {i} membahas {topic_words[i % len(topic_words)]} secara mendalam "
        f"pada bagian ini dengan uraian tambahan nomor {i} yang cukup panjang."
        for i in range(n)
    )


SRC = {"title": "Paper Sumber", "doi": "10.1/src", "url": "u", "source": "OpenAlex",
       "fulltext_oa": True, "_fulltext": _text(["vortex", "sediment", "porous"], 120)}
RESULT = {"similarity_index": 5.0, "sources": []}


@pytest.fixture(autouse=True)
def _on(monkeypatch):
    monkeypatch.setattr(sem.settings, "online_semantic_enabled", True)
    monkeypatch.setattr(sem.settings, "semantic_match_cos", 0.80)
    monkeypatch.setattr(sem.settings, "semantic_min_coverage", 35.0)


def test_paraphrase_with_same_meaning_is_flagged():
    # kata berbeda, "konsep" sama (vortex/sediment/porous) -> cosine 1.0
    doc = _text(["vortex", "sediment", "porous"], 30).replace("membahas", "menguraikan")
    out = sem.find_semantic_source(doc, [SRC], RESULT, llm=FakeLLM())
    assert out and out["coverage"] >= 90 and out["doi"] == "10.1/src"
    assert out["matched_windows"] == out["total_windows"] or out["coverage"] > 90


def test_different_topic_is_not_flagged():
    doc = _text(["harvest", "budget", "pasar"], 30)
    assert sem.find_semantic_source(doc, [SRC], RESULT, llm=FakeLLM()) is None


def test_partial_overlap_below_threshold_not_flagged():
    mixed = _text(["vortex"], 6) + " " + _text(["harvest", "budget", "cuaca", "pasar"], 40)
    out = sem.find_semantic_source(mixed, [SRC], RESULT, llm=FakeLLM())
    assert out is None  # ~13% jendela cocok < 35%


def test_skips_when_already_identified_or_lexically_explained():
    doc = _text(["vortex", "sediment"], 30)
    assert sem.find_semantic_source(doc, [SRC], {**RESULT, "publication_match": {"doi": "x"}},
                                    llm=FakeLLM()) is None
    assert sem.find_semantic_source(doc, [SRC], {"similarity_index": 75.0, "sources": []},
                                    llm=FakeLLM()) is None
    explained = {"similarity_index": 10.0,
                 "sources": [{"doi": "10.1/src", "match_percent": 80.0}]}
    assert sem.find_semantic_source(doc, [SRC], explained, llm=FakeLLM()) is None


def test_requires_fulltext_not_abstract_only():
    doc = _text(["vortex", "sediment"], 30)
    abstract_only = {**SRC, "fulltext_oa": False}
    short = {**SRC, "_fulltext": "pendek " * 50}
    assert sem.find_semantic_source(doc, [abstract_only], RESULT, llm=FakeLLM()) is None
    assert sem.find_semantic_source(doc, [short], RESULT, llm=FakeLLM()) is None
    assert sem.find_semantic_source(doc, [], RESULT, llm=FakeLLM()) is None


def test_disabled_switch_and_too_short_document(monkeypatch):
    doc = _text(["vortex", "sediment"], 30)
    monkeypatch.setattr(sem.settings, "online_semantic_enabled", False)
    assert sem.find_semantic_source(doc, [SRC], RESULT, llm=FakeLLM()) is None
    monkeypatch.setattr(sem.settings, "online_semantic_enabled", True)
    assert sem.find_semantic_source(_text(["vortex"], 4), [SRC], RESULT, llm=FakeLLM()) is None


def test_picks_best_candidate_and_limits_candidates():
    other = {**SRC, "title": "Lain", "doi": "10.1/other",
             "_fulltext": _text(["harvest", "budget", "pasar"], 120)}
    doc = _text(["vortex", "sediment", "porous"], 30)
    out = sem.find_semantic_source(doc, [other, SRC], RESULT, llm=FakeLLM())
    assert out["doi"] == "10.1/src"
    many = [{**other, "doi": f"10.1/o{i}"} for i in range(9)] + [SRC]
    out2 = sem.find_semantic_source(doc, many, RESULT, llm=FakeLLM())
    assert out2 and out2["doi"] == "10.1/src"  # saringan topik mempertahankan kandidat relevan


def test_examples_are_real_paraphrases_not_identical_or_same_words():
    doc = _text(["vortex", "sediment", "porous"], 30).replace("membahas", "menguraikan")
    out = sem.find_semantic_source(doc, [SRC], RESULT, llm=FakeLLM())
    for ex in out["examples"]:
        assert ex["cos"] < sem.VERBATIM_COS
        assert sem._word_overlap(ex["doc"], ex["source"]) < sem.EXAMPLE_MAX_WORD_OVERLAP
        assert len(ex["doc"]) <= 260 and len(ex["source"]) <= 260


def test_windows_cap_samples_evenly():
    wins = sem._windows(_text(["vortex"], 200), cap=20)
    assert len(wins) <= 20 and len(wins) >= 15
    assert wins[0].startswith("Kalimat nomor 0")


def test_coverage_math():
    a = np.eye(3, dtype=np.float32)
    b = np.array([[1, 0, 0], [0, 1, 0]], dtype=np.float32)
    cov, mx, arg = sem._coverage(a, b, 0.8)
    assert round(cov, 1) == 66.7 and mx.tolist() == [1.0, 1.0, 0.0] and arg[:2].tolist() == [0, 1]
    assert sem._coverage(np.zeros((0, 0)), b, 0.8)[0] == 0.0


def test_pdf_cover_shows_semantic_banner_escaped():
    from app.services.plagiarism.report_pdf import _cover_html, _semantic_block

    sm = {"title": "Paper <b>X</b>", "doi": "10.1/x", "source": "OpenAlex (teks penuh OA)",
          "coverage": 97.2, "matched_windows": 35, "total_windows": 36}
    html = _cover_html({"semantic_match": sm, "sources": [], "match_groups": []})
    assert "Indikasi parafrase dari paper terbit" in html and "97% bagian dokumen" in html
    assert "35 dari 36" in html and "Paper &lt;b&gt;X&lt;/b&gt;" in html
    assert "tidak memasukkan temuan ini" in html
    assert _semantic_block(None) == ""
    assert "Indikasi parafrase" not in _cover_html({"sources": [], "match_groups": []})
