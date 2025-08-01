import pytest

from ai_core.ai_router import AIRouter, get_router


def test_get_router_default():
    router = get_router()
    assert isinstance(router, AIRouter)


def test_get_router_invalid():
    with pytest.raises(ValueError):
        get_router("invalid_source")


def test_embed_calls_client(monkeypatch):
    called = {}

    def fake_embed(inputs, model):
        called['args'] = (inputs, model)
        return [[1.0, 2.0]]

    # Patch the import as seen in ai_router.py, not the client module directly
    monkeypatch.setattr('ai_core.ai_router.get_embedding', fake_embed)
    router = AIRouter()
    result = router.embed(['foo'], model='m')
    assert result == [[1.0, 2.0]]
    assert called['args'] == (['foo'], 'm')


def test_chat_calls_client(monkeypatch):
    called = {}

    def fake_chat(messages, model):
        called['args'] = (messages, model)
        return "response"

    # Patch the import as seen in ai_router.py, not the client module directly
    monkeypatch.setattr('ai_core.ai_router.get_chat_completion', fake_chat)
    router = AIRouter()
    msgs = [{'role': 'user', 'content': 'hello'}]
    result = router.chat(msgs, model='m')
    assert result == "response"
    assert called['args'] == (msgs, 'm')
