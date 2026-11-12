import app.services.llm.tasks as tasks
from app.services.llm.tasks import _is_academic, chat


class _FakeLLM:
    def __init__(self):
        self.last_system = None

    def chat(self, messages, temperature=0.0, max_tokens=1024):
        self.last_system = messages[0]["content"]
        return "ok"


def _patch(monkeypatch):
    fake = _FakeLLM()
    monkeypatch.setattr(tasks, "get_llm", lambda: fake)
    return fake


def test_is_academic_detects_research_topics():
    assert _is_academic("Tolong perbaiki rumusan masalah dan novelty penelitian saya")
    assert _is_academic("Review the methodology and abstract of my manuscript")
    assert _is_academic("jelaskan hipotesis dan hasil eksperimen")


def test_is_academic_ignores_casual():
    assert not _is_academic("Bantu aku bikin caption instagram yang lucu")
    assert not _is_academic("halo apa kabar")
    assert not _is_academic("apa resep nasi goreng enak")


def test_chat_uses_professor_role_for_academic(monkeypatch):
    fake = _patch(monkeypatch)
    chat([{"role": "user", "content": "Bagaimana metodologi dan novelty penelitian saya?"}])
    assert "profesor" in fake.last_system.lower()
    assert "evaluator" in fake.last_system.lower()


def test_chat_uses_general_assistant_for_casual(monkeypatch):
    fake = _patch(monkeypatch)
    chat([{"role": "user", "content": "halo, apa kabar hari ini?"}])
    assert "profesor" not in fake.last_system.lower()
    assert "asisten penulisan akademik ICALORA-LABS" in fake.last_system


def test_chat_explicit_system_overrides_detection(monkeypatch):
    fake = _patch(monkeypatch)
    chat(
        [{"role": "user", "content": "metodologi penelitian"}],
        system="SYSTEM CUSTOM",
    )
    assert fake.last_system == "SYSTEM CUSTOM"
