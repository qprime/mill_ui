# path: tests/unit/test_client.py
# type: unit_tests
# tags: testing, client, api, mock, error_handling
# owner: cliff
# depends_on: ai_core/client.py
# description: Validates client API error handling in absence of API keys.

import os
import pytest

from ai_core.client import get_chat_completion, get_embedding


def test_get_chat_completion_no_api_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(RuntimeError):
        get_chat_completion([], model="test-model")


def test_get_embedding_no_api_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(RuntimeError):
        get_embedding("test input", model="test-model")
