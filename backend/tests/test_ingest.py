from app.ingest.common import (
    compress_text,
    decompress_text,
    license_allows_fulltext,
    make_minhash,
    minhash_from_bytes,
    reconstruct_abstract,
    text_metrics,
)


def test_reconstruct_abstract():
    inv = {"Hello": [0], "world": [1], "again": [2]}
    assert reconstruct_abstract(inv) == "Hello world again"
    assert reconstruct_abstract(None) == ""


def test_compress_roundtrip():
    s = "Teks abstrak contoh untuk kompresi zstd. " * 10
    assert decompress_text(compress_text(s)) == s


def test_text_metrics():
    wc, cc = text_metrics("satu dua tiga")
    assert wc == 3
    assert cc == len("satu dua tiga")


def test_license_allows_fulltext():
    # permisif → boleh
    for ok in ["CC0", "CC BY", "cc-by", "CC-BY 4.0", "CC BY-SA", "pd", "public domain"]:
        assert license_allows_fulltext(ok) is True, ok
    # non-komersial / tanpa-turunan / tidak diketahui → tidak boleh
    for bad in ["CC BY-NC", "CC BY-NC-ND", "CC BY-ND", "cc-by-nc-sa", None, "", "OTHER"]:
        assert license_allows_fulltext(bad) is False, bad


def test_minhash_similarity():
    a = "machine learning methods for natural language processing and analysis"
    b = "machine learning methods for natural language processing and study"
    ma = minhash_from_bytes(make_minhash(a))
    mb = minhash_from_bytes(make_minhash(b))
    mc = minhash_from_bytes(make_minhash("completely different topic about marine biology"))
    assert ma.jaccard(mb) > ma.jaccard(mc)
