from app.services.llm.provider import OllamaProvider


def _provider(**kw) -> OllamaProvider:
    return OllamaProvider(
        base_url="http://chat", model="m", embed_model="bge-m3", timeout=5, **kw
    )


def test_embed_keep_alive_defaults_to_chat_keep_alive():
    p = _provider(keep_alive="5m")
    assert p._embed_payload(input=["x"])["keep_alive"] == "5m"


def test_embed_keep_alive_override():
    p = _provider(keep_alive="5m", embed_keep_alive="-1")
    assert p._embed_payload(prompt="x")["keep_alive"] == "-1"


def test_embed_keep_alive_server_omits_field():
    p = _provider(keep_alive="5m", embed_keep_alive="server")
    payload = p._embed_payload(input=["x"])
    assert "keep_alive" not in payload
    assert payload == {"model": "bge-m3", "input": ["x"]}


class _FakeResp:
    def __init__(self, content: str):
        self._content = content

    def json(self) -> dict:
        return {"message": {"content": self._content}}

    def raise_for_status(self) -> None:
        pass


def _capture_chat(monkeypatch, provider, **chat_kw) -> dict:
    captured: dict = {}

    def fake_post(client, url, payload):  # noqa: ANN001
        captured.update(payload)
        return _FakeResp('{"ai_probability": 50, "ai_sentences": []}')

    import app.services.llm.provider as mod

    monkeypatch.setattr(mod, "_post_with_retry", fake_post)
    provider.chat([{"role": "user", "content": "hi"}], **chat_kw)
    return captured


def test_chat_think_false_override(monkeypatch):
    p = _provider()  # self.think defaults to None
    payload = _capture_chat(monkeypatch, p, think=False)
    assert payload["think"] is False


def test_chat_think_default_omitted(monkeypatch):
    p = _provider()
    payload = _capture_chat(monkeypatch, p)
    assert "think" not in payload


def test_chat_think_param_overrides_provider_default(monkeypatch):
    p = _provider(think=True)
    payload = _capture_chat(monkeypatch, p, think=False)
    assert payload["think"] is False
