from app.services.hidden_text import check_hidden_text


def test_clean_text_has_no_findings():
    res = check_hidden_text("Teks biasa tanpa karakter tersembunyi.", check_typos=False)
    assert res["risk"] == "bersih"
    assert res["total_hidden"] == 0


def test_detects_zero_width_and_homoglyph():
    # ZWSP (U+200B) + homoglyph Cyrillic 'a' (U+0430) + bidi override (U+202E)
    text = "halo\u200bdunia \u0430pple \u202eoverride"
    res = check_hidden_text(text, check_typos=False)
    assert res["risk"] == "tinggi"
    assert res["counts"]["invisible"] >= 1
    assert res["counts"]["homoglyph"] >= 1
    assert res["counts"]["bidi_control"] >= 1


def test_cleaned_text_strips_hidden():
    text = "data\u200bbaru"
    res = check_hidden_text(text, check_typos=False)
    assert "\u200b" not in res["cleaned_text"]
    assert res["cleaned_text"] == "databaru"


def test_odd_space_is_medium_risk():
    res = check_hidden_text("satu\u00a0dua", check_typos=False)
    assert res["risk"] == "sedang"
    assert res["counts"]["odd_space"] == 1
    assert res["cleaned_text"] == "satu dua"
