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
