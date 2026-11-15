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


def test_normalize_issue_drops_hallucinated_original():
    from app.services.llm.tasks import _norm_for_match, _normalize_issue

    text = "Penelitian ini menggunakan metode kualitatif untuk menganalisis data."
    tn = _norm_for_match(text)
    # Issue nyata (potongan ada di teks) -> dipertahankan
    real = {"original": "menggunakan metode kualitatif", "suggestion": "menerapkan",
            "severity": "advanced", "category": "Kejelasan"}
    assert _normalize_issue(real, tn) is not None
    # Issue halusinasi (potongan TIDAK ada di teks) -> dibuang
    halu = {"original": "pengaruh variabel independen", "suggestion": "x",
            "severity": "critical", "category": "Ketepatan"}
    assert _normalize_issue(halu, tn) is None
    # Tanpa text_norm -> backward compatible (tidak memfilter)
    assert _normalize_issue(halu) is not None


def test_normalize_issue_tolerant_whitespace_and_quotes():
    from app.services.llm.tasks import _norm_for_match, _normalize_issue

    text = 'Dia bilang "halo dunia" kepada    semua orang.'
    tn = _norm_for_match(text)
    issue = {"original": "halo dunia  kepada semua", "suggestion": "y",
             "severity": "advanced", "category": "Ketepatan"}
    assert _normalize_issue(issue, tn) is not None
