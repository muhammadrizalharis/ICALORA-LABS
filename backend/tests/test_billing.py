"""Sidik jari dokumen untuk diskon cek ulang revisi + sanitasi aturan paket."""

from app.services import billing

_BASE = " ".join(
    f"kalimat nomor {i} membahas metode penelitian kualitatif pada sekolah dasar negeri"
    for i in range(80)
)


def test_identical_document_is_fully_similar():
    fp = billing.fingerprint(_BASE)
    assert billing.similarity(fp, billing.fingerprint(_BASE)) == 1.0


def test_revised_document_still_matches():
    words = _BASE.split()
    # Revisi ~15%: ganti setiap kata ke-7.
    revised = " ".join("diperbaiki" if i % 7 == 0 else w for i, w in enumerate(words))
    sim = billing.similarity(billing.fingerprint(_BASE), billing.fingerprint(revised))
    assert sim >= 0.15  # shingle 5-kata sensitif, tapi revisi ringan tetap terdeteksi


def test_light_revision_passes_default_threshold():
    words = _BASE.split()
    revised = " ".join(words[:-40] + ["bab", "penutup", "baru"] * 5)
    sim = billing.similarity(billing.fingerprint(_BASE), billing.fingerprint(revised))
    assert sim >= billing.PACKAGE_DEFAULTS["revision_min_similarity"]


def test_different_document_does_not_match():
    other = " ".join(
        f"analisis ekonomi makro {i} terhadap inflasi dan suku bunga bank sentral"
        for i in range(80)
    )
    sim = billing.similarity(billing.fingerprint(_BASE), billing.fingerprint(other))
    assert sim < 0.1


def test_fingerprint_is_normalized_and_bounded():
    a = billing.fingerprint("Ｍetode  PENELITIAN, kualitatif! " * 50)
    b = billing.fingerprint("metode penelitian kualitatif " * 50)
    assert a == b
    assert len(billing.fingerprint(_BASE)) <= 256
    assert billing.fingerprint("") == []


def test_clean_packages_clamps_values():
    cfg = billing.clean_packages(
        {**billing.PACKAGE_DEFAULTS, "revision_discount_pct": 250, "subscription_days": 0}
    )
    assert cfg["revision_discount_pct"] == 100
    assert cfg["subscription_days"] == 1
    assert billing.clean_packages({"revision_tools": "x"})["revision_tools"] == [
        "plagiarism-checker",
        "ai-detector",
    ]
