from app.services.file_extract import _dehyphenate


def test_dehyphenate_joins_linebreak_hyphenation():
    # Pemenggalan kata khas PDF 2-kolom/justified harus disatukan.
    assert _dehyphenate("reduc- ing") == "reducing"
    assert _dehyphenate("effi-\ncient") == "efficient"
    assert _dehyphenate("inter- cluster separation") == "intercluster separation"


def test_dehyphenate_preserves_real_compounds_and_numbers():
    # Tanda hubung majemuk sah (tanpa spasi) tidak boleh berubah.
    assert _dehyphenate("inter-cluster") == "inter-cluster"
    assert _dehyphenate("state-of-the-art") == "state-of-the-art"
    # Diikuti huruf KAPITAL (mis. rentang/nama) tidak disatukan.
    assert _dehyphenate("PCA- FCM") == "PCA- FCM"


def test_sanitize_text_strips_nul_and_control_chars():
    from app.services.file_extract import sanitize_text

    # NUL & kontrol C0 non-cetak (sampah ekstraksi PDF) dibuang; teks/
    # tab/baris-baru yang sah dipertahankan.
    assert sanitize_text("a\x00b") == "ab"
    assert sanitize_text("x\x07y\x1fz") == "xyz"
    assert sanitize_text("baris1\nbaris2\tkolom\r\n") == "baris1\nbaris2\tkolom\r\n"


def test_sanitize_text_expands_typographic_ligatures():
    from app.services.file_extract import sanitize_text

    assert sanitize_text("classi\ufb01cation e\ufb03cient o\ufb00 \ufb02ow su\ufb04e") == (
        "classification efficient off flow suffle"
    )


def test_sanitize_text_leaves_scientific_and_indonesian_text_untouched():
    from app.services.file_extract import sanitize_text

    # Sengaja bukan NFKC: superskrip, satuan, pecahan, elipsis, dan diakritik harus tetap.
    s = "Luas 25 m² dan 10⁻³ mol, ½ bagian… α≥0,05 café Pengaruh model pembelajaran ™"
    assert sanitize_text(s) == s
