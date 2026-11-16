import app.services.llm.tasks as tasks
from app.services.citation import _citation_entry
from app.services.llm.tasks import (
    _grammar_chunks,
    _llm_transform_long,
    paraphrase,
)
from app.services.report.reports import (
    _diff_html,
    _word_tokens,
    toc_report_html,
    transform_report_html,
)


class _EchoLLM:
    """LLM palsu: kembalikan konten user yang dikapitalkan agar hasil berbeda."""

    def __init__(self, transform=None):
        self._t = transform or (lambda s: s.upper())

    def chat(self, messages, temperature=0.0, **kwargs):
        user = messages[-1]["content"]
        return self._t(user)


def _patch(monkeypatch, llm):
    monkeypatch.setattr(tasks, "get_llm", lambda: llm)


def test_transform_long_merges_all_chunks_no_loss(monkeypatch):
    _patch(monkeypatch, _EchoLLM())
    # Dokumen panjang -> banyak chunk; pastikan semua bagian diproses & digabung.
    para = ("kalimat uji nomor satu. " * 40).strip()
    text = "\n\n".join(f"{para} bagian{i}" for i in range(8))
    assert len(_grammar_chunks(text, limit=2000)) > 1
    out = _llm_transform_long("sys", text, temperature=0.5)
    # Setiap penanda bagian harus muncul (tidak ada chunk yang hilang).
    for i in range(8):
        assert f"BAGIAN{i}".upper() in out.upper()


def test_transform_short_text_single_call(monkeypatch):
    _patch(monkeypatch, _EchoLLM())
    out = _llm_transform_long("sys", "halo dunia", temperature=0.5)
    assert out == "HALO DUNIA"


def test_paraphrase_uses_transform(monkeypatch):
    _patch(monkeypatch, _EchoLLM())
    res = paraphrase("teks pendek", "formal")
    assert res["style"] == "formal"
    assert res["result"] == "TEKS PENDEK"


def test_word_tokens_roundtrip_no_loss():
    s = "Saya  pergi ke\nsekolah."
    assert "".join(_word_tokens(s)) == s


def test_diff_html_marks_changes():
    html, changed, result_words = _diff_html(
        "saya pergi ke sekola", "saya pergi ke sekolah kemarin"
    )
    assert "line-through" in html  # bagian dihapus/diganti disorot merah
    assert "#dcfce7" in html  # bagian ditambah disorot hijau
    assert changed >= 1
    assert result_words == 5


def test_transform_report_html_has_sections():
    html = transform_report_html(
        "kalimat asli", "kalimat hasil baru", {"tool_label": "Parafrase", "title": "X"}
    )
    assert "Parafrase" in html
    assert "Perubahan" in html
    assert "Teks Hasil Lengkap" in html


def test_toc_report_html_renders_entries():
    res = {
        "entries": [
            {"level": 1, "number": "1", "title": "Pendahuluan"},
            {"level": 2, "number": "1.1", "title": "Latar Belakang"},
        ],
        "markdown": "- 1 Pendahuluan",
    }
    html = toc_report_html(res, {"title": "Dok"})
    assert "Pendahuluan" in html
    assert "Latar Belakang" in html


def test_citation_entry_shape():
    e = _citation_entry(
        doc_id=1, source="crossref", external_id="10.x/y", title="Judul Uji",
        pub_year=2020, doi="10.x/y", relevance=None, online=True,
    )
    assert e["online"] is True
    assert e["url"] == "https://doi.org/10.x/y"
    assert "apa" in e and "bibtex" in e and "ris" in e
    assert "2020" in e["apa"]


def test_async_transform_endpoints_are_coroutines():
    """Regresi: endpoint *-async memanggil _spawn (asyncio.create_task) sehingga
    WAJIB `async def`; bila sync, FastAPI menjalankannya di threadpool tanpa event
    loop -> RuntimeError 'no running event loop' saat submit."""
    import inspect

    from app.api import tools

    for name in (
        "paraphrase_async_ep", "humanize_async_ep", "rewrite_async_ep",
        "improve_async_ep", "toc_async_ep",
    ):
        fn = getattr(tools, name)
        assert inspect.iscoroutinefunction(fn), f"{name} harus 'async def'"
