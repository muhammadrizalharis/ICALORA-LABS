from app.services.llm.tasks import _extract_json, _select_context


def test_select_context_returns_full_when_short():
    doc = "hello world this is short"
    assert _select_context(doc, "anything") == doc


def test_select_context_retrieves_relevant_tail():
    # Jawaban hanya muncul di bagian AKHIR dokumen panjang; retrieval harus
    # memilih potongan itu, bukan sekadar 12k char pertama.
    doc = ("alpha beta gamma delta. " * 600) + " ZEBRAFISH migration discovered. " + (
        "filler text more. " * 600
    )
    sel = _select_context(doc, "tell me about zebrafish migration", budget=4000)
    assert "ZEBRAFISH" in sel
    assert len(sel) <= 4500


def test_select_context_no_terms_keeps_head_and_tail():
    doc = ("start " * 1000) + ("end " * 1000)
    sel = _select_context(doc, "", budget=2000)
    assert sel.startswith("start")
    assert "end" in sel


def test_extract_json_from_prose_and_fences():
    assert _extract_json('result: {"a": 1, "b": [2, 3]} trailing') == {"a": 1, "b": [2, 3]}
    assert _extract_json('```json\n{"x": 10}\n```') == {"x": 10}
    assert _extract_json('prose {"first": 1} then {"second": 2}') == {"first": 1}
