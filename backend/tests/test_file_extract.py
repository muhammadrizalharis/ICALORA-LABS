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
