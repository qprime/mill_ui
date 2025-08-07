# path: tests/unit/test_personas_manager.py
# type: unit_test_module
# tags: personas, testing, unit, manager
# owner: cliff
# depends_on: cortex/personas/personas_manager.py
# description: Validates personas management functionality in unit tests.

import json
import pytest

from cortex.personas.personas_manager import (
    get_legacy_persona_prompt,
    get_legacy_personas,
    get_persona,
)


def test_get_legacy_persona_prompt():
    prompt = get_legacy_persona_prompt("assistant")
    assert isinstance(prompt, dict)
    assert "role" in prompt and "content" in prompt


def test_get_legacy_personas_contains_assistant():
    personas = get_legacy_personas()
    assert "assistant" in personas


def test_get_persona_legacy_and_unknown():
    # Known legacy
    persona = get_persona("assistant")
    assert "description" in persona
    # Unknown persona raises
    with pytest.raises(ValueError):
        get_persona("no_such_persona")
