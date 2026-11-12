"""Regresi: penyimpanan hasil ke kolom jsonb harus selalu JSON valid.

Dulu ``record_history`` menyimpan ``json.dumps(result)[:200000]`` yang memotong
*string* JSON di tengah token sehingga ``CAST(... AS jsonb)`` gagal
(InvalidTextRepresentation) dan seluruh pemanggilan tool menjadi "Gagal".
"""

import json

from app.services.auth import _bounded_json


def _valid(s: str) -> bool:
    try:
        json.loads(s)
        return True
    except ValueError:
        return False


def test_small_result_kept_intact():
    data = {"sources": [{"url": "http://x", "matched": '"cited" text'}], "score": 0.5}
    out = _bounded_json(data)
    assert _valid(out)
    assert json.loads(out) == data


def test_huge_result_stays_valid_and_bounded():
    big = {
        "sources": [
            {"url": f"http://site{i}", "matched": "cited " * 5000} for i in range(500)
        ],
        "overall": 92,
    }
    out = _bounded_json(big)
    assert _valid(out)
    assert len(out) <= 1_500_000


def test_quote_near_old_truncation_boundary_not_corrupted():
    # Kasus yang dulu merusak JSON: tanda kutip tepat setelah batas 200k.
    tricky = {"items": ["x" * 199_995 + '"cited"']}
    out = _bounded_json(tricky)
    assert _valid(out)
