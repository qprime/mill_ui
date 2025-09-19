import importlib
import sys
import types
import pytest


def _with_dummy_client(monkeypatch):
    dummy = types.SimpleNamespace(get_chat_completion=lambda *a, **k: "response", get_embedding=lambda *a, **k: [[1.0, 2.0]])
    monkeypatch.setitem(sys.modules, "cortex.client", dummy)
    import cortex.ai_router as ai_router
    importlib.reload(ai_router)
    return ai_router


def test_get_router_default(monkeypatch):
    ai_router = _with_dummy_client(monkeypatch)
    router = ai_router.get_router()
    assert isinstance(router, ai_router.AIRouter)


def test_get_router_invalid(monkeypatch):
    _ = _with_dummy_client(monkeypatch)
    with pytest.raises(ValueError):
        import cortex.ai_router as ai_router
        ai_router.get_router("invalid_source")


def test_embed_calls_client(monkeypatch):
    called = {}
    def _emb(inputs, model):
        called["args"] = (inputs, model)
        return [[1.0, 2.0]]

    dummy = types.SimpleNamespace(
        get_chat_completion=lambda *a, **k: "response",
        get_embedding=_emb,
    )
    monkeypatch.setitem(sys.modules, "cortex.client", dummy)
    import cortex.ai_router as ai_router
    importlib.reload(ai_router)
    router = ai_router.AIRouter()
    result = router.embed(["foo"], model="m")
    assert result == [[1.0, 2.0]]
    assert called["args"] == (["foo"], "m")


def test_chat_calls_client(monkeypatch):
    called = {}
    def _chat(messages, model):
        called["args"] = (messages, model)
        return "response"

    dummy = types.SimpleNamespace(
        get_chat_completion=_chat,
        get_embedding=lambda *a, **k: [[1.0, 2.0]],
    )
    monkeypatch.setitem(sys.modules, "cortex.client", dummy)
    import cortex.ai_router as ai_router
    importlib.reload(ai_router)
    router = ai_router.AIRouter()
    msgs = [{"role": "user", "content": "hello"}]
    result = router.chat(msgs, model="m")
    assert result == "response"
    assert called["args"] == (msgs, "m")
