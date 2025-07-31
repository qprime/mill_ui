"""
context_manager.py

Unified context management for CLIFF AI.

Handles:
- Context routing/classification (via LLM or explicit context list)
- Context loading/assembly (for persona, chat, project, codebase, sidecar)
- Project metadata and memory loading
- Sidecar and status block retrieval

"""

from pathlib import Path
import os
import json
from typing import List, Dict, Optional, Tuple

import openai
from ai_core.personas.personas_manager import get_persona, legacy_persona_registry
from memory.memory_manager import get_known_contexts, get_chat_log_paths
from continuum.code_context import generate_context

# --------- Model/Router Config ---------
OPENAI_MODEL = "gpt-4.1-mini"  # Or update as needed
KNOWN_CONTEXTS = get_known_contexts()

# --------- Context Routing ---------
def route_context(prompt: str, active_persona: str | None = None, active_context: List[str] | None = None) -> dict:
    """
    Suggests relevant context paths for a prompt/persona using LLM (or explicit context override).
    Returns: {
        persona, suggested_context, confidence, clarify
    }
    """
    persona = active_persona or "cliff_core"
    if active_context:
        return {
            "persona": persona,
            "suggested_context": [c for c in active_context if c in KNOWN_CONTEXTS],
            "confidence": 1.0,
            "clarify": False
        }
    system_prompt = (
        "You are a context classification assistant for CLIFF AI.\n"
        "Your task is to choose the most relevant CONTEXT path(s) from the list below\n"
        "based on the user's prompt. These paths are folders where related memory is stored.\n\n"
        f"Valid CONTEXT paths: {', '.join(KNOWN_CONTEXTS)}\n\n"
        "Return only valid paths. Respond in the format:\n"
        "CONTEXT: <comma-separated list of valid CONTEXT paths>\n"
        "CONFIDENCE: <float between 0.0 and 1.0>\n"
        "CLARIFY: <true or false>\n\n"
        "DO NOT include explanation or commentary."
    )
    try:
        client = openai.OpenAI(api_key=None)  # Uses env variable
        completion = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ],
            temperature=0.0,
            max_tokens=128,
        )
        content = completion.choices[0].message.content.strip()
        result = parse_tag_output(content)
    except Exception as e:
        print("[context_manager.py][route_context] OpenAI call failed:", e)
        result = {
            "persona": persona,
            "suggested_context": ["development"],
            "confidence": 0.0,
            "clarify": True
        }
    result["persona"] = persona
    if persona != "assistant":
        result["suggested_context"] = [c for c in result["suggested_context"] if not c.startswith("personal/")]
    if not result["suggested_context"]:
        result["suggested_context"] = ["development"]
    result.setdefault("confidence", 0.0)
    result.setdefault("clarify", False)
    return result

def parse_tag_output(text: str) -> dict:
    """
    Parses context classification LLM output.
    Expects lines like:
      CONTEXT: context_a, context_b
      CONFIDENCE: 0.95
      CLARIFY: false
    """
    result = {
        "persona": "unknown",
        "suggested_context": [],
        "confidence": 0.0,
        "clarify": False
    }
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("PERSONA:"):
            result["persona"] = line.split(":", 1)[1].strip()
        elif line.startswith("CONTEXT:"):
            result["suggested_context"] = [x.strip() for x in line.split(":", 1)[1].split(",")]
        elif line.startswith("CONFIDENCE:"):
            try:
                result["confidence"] = float(line.split(":", 1)[1].strip())
            except ValueError:
                pass
        elif line.startswith("CLARIFY:"):
            result["clarify"] = "true" in line.lower()
        elif not line or not ":" in line:
            break
    return result

# --------- Context Loading ---------
def load_json(path: Path) -> dict:
    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def load_sidecar(chat_id: str, persona: str) -> dict:
    paths = get_chat_log_paths(chat_id, persona)
    path = paths["sidecar"]
    if not path.exists():
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def load_module_summaries(md_dir: Path) -> List[str]:
    return [
        f.read_text().strip()
        for f in sorted(md_dir.glob("*.md"))
        if f.read_text().strip()
    ]

def load_base_context() -> Dict[str, any]:
    root = Path(__file__).resolve().parents[2]
    meta_path = root / "memory/metadata"
    return {
        "summary": load_json(meta_path / "project_summary.json"),
        "memory_graph": load_json(meta_path / "memory_graph.json"),
        "project_graph": load_json(meta_path / "project_graph.json"),
        "module_summaries": load_module_summaries(root / "memory/development/module_summaries")
    }

def get_cliff_core_base_context() -> List[str]:
    ctx = load_base_context()
    fragments = [
        f"# Project Summary\n{ctx['summary'].get('long_description', '')}",
        f"# Core Goals\n" + "\n".join(f"- {g}" for g in ctx['summary'].get("core_goals", [])),
        f"# Interfaces\n" + "\n".join(f"- {i}" for i in ctx['summary'].get("primary_interfaces", [])),
        f"# Memory Domains\n" + "\n".join(f"- {d['name']}: {d['purpose']}" for d in ctx['memory_graph'].get("domains", [])),
        f"# Modules\n" + "\n".join(f"- {m['name']}" for m in ctx['project_graph'].get("modules", [])),
        f"# Module Summaries\n" + "\n\n".join(ctx["module_summaries"])
    ]
    return fragments

def get_codebase_context(query: str, paths: Optional[List[str]] = None, top_n: int = 3) -> str:
    root_dir = Path(__file__).resolve().parents[2]
    context_text = generate_context(str(root_dir))
    return context_text

def get_cliff_status() -> dict:
    """
    Stub: Return mock or real-time system status.
    """
    return {
        "uptime": "running",
        "memory_usage": "not tracked",
        "active_contexts": 3,
        "last_distill": "just now"
    }

def load_context_for_persona(prompt: str, persona: str, suggested_contexts: List[str], chat_id: str = None) -> dict:
    """
    Loads all context (sidecar, memory, base/project, etc.) for a given persona/prompt.
    Used to build the context injected into LLM conversations.
    """
    known = get_known_contexts()
    paths = [p for p in suggested_contexts if p in known]
    if not paths:
        fallback = legacy_persona_registry.get(persona, {}).get("default_contexts", [])
        paths = [p for p in fallback if p in known]
        print(f"[context_manager] Using fallback paths for {persona}: {paths}")
    else:
        print(f"[context_manager] Using routed paths for {persona}: {paths}")

    sidecar = ""
    if chat_id:
        sidecar = load_sidecar(chat_id, persona)

    if persona == "cliff_core":
        base = "\n\n".join(get_cliff_core_base_context())
    else:
        base = get_codebase_context(prompt, paths=paths)

    return {
        "sidecar": sidecar,
        "memory": base
    }

# ---- You may add additional helper methods as desired ----

