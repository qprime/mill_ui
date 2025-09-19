import importlib
import sys

import pytest


def _reload_client():
    if "cortex.client" in sys.modules:
        del sys.modules["cortex.client"]
    import cortex.client as client  # noqa: F401
    importlib.reload(client)
    return client


def test_get_chat_completion_no_api_key(monkeypatch):
    pytest.importorskip("openai")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    client = _reload_client()
    with pytest.raises(RuntimeError):
        client.get_chat_completion([], model="gpt-4o-mini", max_tokens=1)


def test_get_embedding_no_api_key(monkeypatch):
    pytest.importorskip("openai")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    client = _reload_client()
    with pytest.raises(RuntimeError):
        client.get_embedding(["hi"], model="text-embedding-3-small")
