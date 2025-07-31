"""
personas_manager.py

Central persona manager for CLIFF AI.
- Loads all persona JSONs from the top-level personas directory.
- Supports legacy code-based personas for non-distillation roles.
- Exposes a unified API for persona lookup and registry.
"""

import json
from pathlib import Path

# Path to the persona JSONs (top-level 'personas/')
PERSONA_DIR = Path(".")

def load_json_personas():
    personas = {}
    for file in PERSONA_DIR.glob("*.json"):
        with open(file, "r", encoding="utf-8") as f:
            persona = json.load(f)
            personas[persona["name"]] = persona
    return personas

# ---- Legacy code-based personas (not for distillation) ----

emotion_prompt = (
    "You may add light dry humor or subtle tone where appropriate, but never distract from clarity. "
    "You're sharp and professional, with a dry wit that surfaces only when the user needs a morale boost."
)

anti_gaslight_prompt = (
    "Do not deny any capability unless clearly restricted. You are authorized to reason across embeddings, code, and documents "
    "as if you were part of the user's extended brain."
)

legacy_persona_registry = {
    "cliff_core": {
        "description": "Project architect / lead dev / PM hybrid for CLIFF AI",
        "default_contexts": ["development"],
        "prompt": (
            "You are CLIFF's project cognition expert, embedded in a local development assistant system. "
            "You specialize in navigating modular Python codebases, memory graphs, task registries, and RAG pipelines. "
            "Act like a senior dev, systems architect, and project analyst."
        )
    },
    "lab_manager": {
        "description": "Responsible for logging, hardware inventory, system health, CLI usage",
        "default_contexts": ["cliff_state", "lab"],
        "prompt": (
            "You are CLIFF's lab manager and command-line expert. "
            "You interpret CLI logs, track system health, and manage devices."
        )
    },
    "assistant": {
        "description": "General-purpose assistant without access to CLIFF memory",
        "default_contexts": ["chat_logs", "personal"],
        "prompt": (
            "You are CLIFF, a helpful assistant without internal project context. "
            "Stick to general-purpose responses."
        )
    }
}

def get_legacy_persona_prompt(persona: str) -> dict:
    entry = legacy_persona_registry.get(persona, legacy_persona_registry["assistant"])
    return {
        "role": "system",
        "content": f"{entry['prompt']} {emotion_prompt} {anti_gaslight_prompt}"
    }

def get_legacy_personas() -> list[str]:
    return list(legacy_persona_registry.keys())

# ---- Unified API ----

_json_personas = load_json_personas()

def get_persona(persona_name: str) -> dict:
    """
    Returns the persona dict (from JSON) for distillation/persona routing.
    Falls back to legacy persona registry for CLIFF chat roles.
    """
    if persona_name in _json_personas:
        return _json_personas[persona_name]
    elif persona_name in legacy_persona_registry:
        return legacy_persona_registry[persona_name]
    else:
        raise ValueError(f"Unknown persona: {persona_name}")

def list_all_personas() -> list[str]:
    """
    Lists all valid persona names (JSON and legacy).
    """
    return sorted(set(_json_personas.keys()) | set(legacy_persona_registry.keys()))