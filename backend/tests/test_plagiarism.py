from app.ingest.common import compress_text
from app.services.plagiarism import _snippet, _vec_literal


def test_vec_literal():
    assert _vec_literal([0.0, 1.5, -2.25]) == "[0.000000,1.500000,-2.250000]"


def test_snippet_roundtrip():
    body = "Kalimat pertama. " * 50
    snip = _snippet(compress_text(body), limit=40)
    assert len(snip) <= 40
    assert snip.startswith("Kalimat pertama")
    assert _snippet(None) == ""
