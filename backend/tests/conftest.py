import pytest


@pytest.fixture(autouse=True)
def _no_history_writes(monkeypatch):
    """Uji endpoint tidak boleh menulis riwayat ke database sungguhan."""
    from app.api import tools

    monkeypatch.setattr(tools, "_log", lambda *a, **k: None)
