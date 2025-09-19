import json
from pathlib import Path

import pytest

import importlib
import cortex.personas.personas_manager as pm


def test_get_persona_and_list_all_personas(tmp_path, monkeypatch):
    # Prepare a temporary personas directory with a simple persona JSON
    persona_dir = tmp_path / "personas"
    persona_dir.mkdir()
    (persona_dir / "assistant.json").write_text(
        json.dumps(
            {
                "name": "assistant",
                "system_prompt": "You are helpful.",
                "default_contexts": ["development"],
            }
        ),
        encoding="utf-8",
    )

    # Point loader to the temp dir and reload the module to pick it up
    monkeypatch.setattr(pm, "PERSONA_DIR", Path(persona_dir))
    importlib.reload(pm)

    # list_all_personas
    names = pm.list_all_personas()
    assert "assistant" in names

    # get_persona -> returns the full dict
    persona = pm.get_persona("assistant")
    assert persona["name"] == "assistant"
    assert persona["system_prompt"].startswith("You are")


def test_get_persona_unknown_raises(tmp_path, monkeypatch):
    monkeypatch.setattr(pm, "PERSONA_DIR", Path(tmp_path))
    importlib.reload(pm)
    with pytest.raises(ValueError):
        pm.get_persona("no_such_persona")

