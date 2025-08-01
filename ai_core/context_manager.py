from dataclasses import dataclass
from typing import Any, Dict, List, Optional

# Example import; update to match your real project paths
from ai_core.personas.personas_manager import legacy_persona_registry

@dataclass
class ContextBundle:
    persona: str
    context_paths: List[str]
    memory: str
    sidecar: Optional[dict] = None

def route_context(
    prompt: str, 
    persona: str = "cliff_core", 
    model: str = "gpt-4.1-mini"
) -> List[str]:
    """
    Uses the LLM to classify the user's prompt and suggest the most relevant context(s).
    Returns a list of context path names (strings).
    """
    from ai_core.client import get_chat_completion

    tag_instruction = (
        "You are a context routing engine for CLIFF AI.\n"
        "Given a user prompt and available memory/context domains, "
        "output ONLY the names of the most relevant context(s) as a Python list of strings."
    )
    known_contexts = get_known_contexts()
    messages = [
        {"role": "system", "content": tag_instruction + "\n\n" + str(known_contexts)},
        {"role": "user", "content": f"Prompt: {prompt}\n\nOutput: "}
    ]
    try:
        resp = get_chat_completion(
            messages, model=model, temperature=0.0, max_tokens=256
        )
        return _parse_tag_output(resp)
    except Exception:
        # If the LLM fails, fallback to all known contexts
        return list(known_contexts)

def load_persona_context(
    prompt: str,
    persona: str = "cliff_core",
    suggested_context: Optional[List[str]] = None,
    chat_id: Optional[str] = None
) -> ContextBundle:
    """
    Main entrypoint: Assembles a ContextBundle for the given persona and prompt.
    """
    known_contexts = get_known_contexts()
    context_paths = _filter_context_paths(persona, suggested_context or [], known_contexts)
    sidecar = _load_sidecar(chat_id, persona) if chat_id else None

    if persona == "cliff_core":
        memory = _get_cliff_core_base_context()
    else:
        memory = _get_codebase_context(prompt, paths=context_paths)

    return ContextBundle(
        persona=persona,
        context_paths=context_paths,
        memory=memory,
        sidecar=sidecar
    )

def get_cliff_status() -> Dict[str, Any]:
    """
    Stub for CLIFF AI health/status (expand as needed).
    """
    return {"status": "OK", "uptime": "n/a"}

# ---- Internal helpers below ----

def _parse_tag_output(output: str) -> List[str]:
    """
    Expects LLM output to be a Python list of strings, e.g. "['development', 'chat_logs']".
    """
    import ast
    try:
        val = ast.literal_eval(output.strip())
        if isinstance(val, list) and all(isinstance(x, str) for x in val):
            return val
    except Exception:
        pass
    return []

def _load_sidecar(chat_id: str, persona: str) -> Optional[dict]:
    """
    Loads any session/persona-specific sidecar memory. (Stub, expand as needed.)
    """
    # Stub: Sidecars not implemented in this version
    return None

def _load_json(path: str) -> dict:
    import json
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def _load_module_summaries(paths: List[str]) -> List[str]:
    """
    Loads all .md summaries for the given context paths.
    """
    frags = []
    for p in paths:
        try:
            frag = _load_json(f"{p}/summary.md")
            frags.append(frag)
        except Exception:
            continue
    return frags

def _load_base_context() -> List[str]:
    """
    Loads the baseline context from memory/development/context_base.md.
    """
    try:
        with open("memory/development/context_base.md", "r", encoding="utf-8") as f:
            return [f.read()]
    except Exception:
        return []

def _get_cliff_core_base_context() -> str:
    """
    Loads and joins base context for cliff_core.
    """
    return "\n\n".join(_load_base_context())

def _get_codebase_context(prompt: str, paths: List[str]) -> str:
    """
    Loads and joins codebase context from selected memory paths and summaries.
    """
    frags = _load_base_context()
    frags += _load_module_summaries(paths)
    return "\n\n".join([frag for frag in frags if frag])

def _filter_context_paths(persona: str, suggested: List[str], known: List[str]) -> List[str]:
    """
    Returns the suggested context paths that are known, or falls back to persona defaults.
    """
    if suggested:
        paths = [p for p in suggested if p in known]
        if paths:
            return paths
    # Fallback: use legacy persona defaults
    fallback = legacy_persona_registry.get(persona, {}).get("default_contexts", [])
    return [p for p in fallback if p in known] or known

def get_known_contexts() -> List[str]:
    """
    Returns the list of known context domains for routing.
    """
    # Update with your project logic for valid context domains
    return [
        "development", "chat_logs", "personal", "cliff_state", "lab",
        # Add more as your project expands
    ]

