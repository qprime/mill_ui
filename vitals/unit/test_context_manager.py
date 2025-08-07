# path: tests/unit/test_context_manager.py
# type: unit_tests
# tags: testing, context_manager, context_selection, pytest
# owner: cliff
# depends_on: cortex.context_manager, cortex.client
# description: Validates context manager functionality in various scenarios for LLM.

import pytest


def test_route_context_returns_known_contexts(monkeypatch):
    # Monkeypatch LLM to always return a specific context
    def mock_get_chat_completion(messages, model, temperature, max_tokens):
        return "['development', 'chat_logs']"

    # Patch the correct function BEFORE import
    import cortex.client

    monkeypatch.setattr(cortex.client, "get_chat_completion", mock_get_chat_completion)

    # Now import after patch
    from cortex.context_manager import route_context

    prompt = "Show me developer logs."
    persona = "cliff_core"
    result = route_context(prompt, persona)
    assert isinstance(result, list)
    assert "development" in result
    assert "chat_logs" in result


from cortex.context_manager import (
    load_persona_context,
    get_cliff_status,
    ContextBundle,
)


def test_load_persona_context_default():
    prompt = "Summarize the project."
    persona = "cliff_core"
    bundle = load_persona_context(prompt, persona)
    assert isinstance(bundle, ContextBundle)
    assert bundle.persona == persona
    assert isinstance(bundle.context_paths, list)
    assert isinstance(bundle.memory, str)
    assert bundle.sidecar is None or isinstance(bundle.sidecar, dict)


def test_load_persona_context_with_context():
    prompt = "Show lab data."
    persona = "lab_manager"
    suggested_context = ["lab", "development"]
    bundle = load_persona_context(prompt, persona, suggested_context)
    assert isinstance(bundle, ContextBundle)
    assert set(bundle.context_paths) & set(suggested_context)
    assert isinstance(bundle.memory, str)


def test_get_cliff_status():
    status = get_cliff_status()
    assert isinstance(status, dict)
    assert "status" in status


def test_fallback_context(monkeypatch):
    # Simulate unknown suggested contexts
    prompt = "Unknown context test"
    persona = "cliff_core"
    bundle = load_persona_context(prompt, persona, suggested_context=["foo", "bar"])
    assert isinstance(bundle.context_paths, list)
    # Should fallback to at least one known context
    assert any(
        ctx in ["development", "chat_logs", "personal", "cliff_state", "lab"]
        for ctx in bundle.context_paths
    )
