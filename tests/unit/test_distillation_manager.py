import pytest

from ai_core.distillation_manager import distill


def test_distill_with_openai(monkeypatch):
    # Prepare fake persona and chat completion
    monkeypatch.setattr(
        'ai_core.distillation_manager.get_persona',
        lambda name: {'system_prompt': 'sys', 'default_model': 'gpt-test', 'strict_mode': True}
    )
    monkeypatch.setattr(
        'ai_core.distillation_manager.get_chat_completion',
        lambda messages, model, temperature, max_tokens: ' result '
    )
    out = distill('hello', persona_name='p', model=None, strict_mode=None)
    assert out.strip() == 'result'


def test_distill_not_implemented(monkeypatch):
    monkeypatch.setattr(
        'ai_core.distillation_manager.get_persona',
        lambda name: {'system_prompt': '', 'default_model': 'other-model', 'strict_mode': False}
    )
    with pytest.raises(NotImplementedError):
        distill('text', persona_name='p')
