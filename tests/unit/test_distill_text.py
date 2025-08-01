import pytest

from ai_core.distill_text import extract_distilled_block, distill_text


def test_extract_distilled_block_none():
    assert extract_distilled_block("no markers here") is None


def test_extract_distilled_block_valid():
    text = "<<<DISTILL_START\nfoo bar baz\nDISTILL_END>>>"
    assert extract_distilled_block(text) == "foo bar baz"


def test_distill_text_fallback(monkeypatch, capsys):
    # Simulate extract returning None by returning no markers
    def fake_chat(messages, model, **kwargs):
        return "no markers"

    monkeypatch.setattr('ai_core.distill_text.get_chat_completion', fake_chat)
    result = distill_text('input text', guidance={}, strict_mode=True)
    assert result['distilled_text'] == 'input text'
    assert result['metadata']['bypassed'] is True
