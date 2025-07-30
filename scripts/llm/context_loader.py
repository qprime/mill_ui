"""Context loader and retriever for CLIFF-AI memory and persona management.

Provides functions for loading, filtering, and assembling project context
fragments, module summaries, and persona-specific memory for retrieval-augmented generation.
"""

from pathlib import Path
import os
import sys
import json
from typing import List, Dict, Optional, Tuple
from difflib import SequenceMatcher
from scripts.llm.personas_manager import get_persona, legacy_persona_registry
from scripts.memory.memory_manager import get_known_contexts
from scripts.memory.memory_manager import get_chat_log_paths

sys.path.append(str(Path(__file__).resolve().parents[2]))

from context.code_context import generate_context


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


def load_context_for_persona(prompt: str, persona: str, suggested_contexts: list[str], chat_id: str = None) -> dict:
    known = get_known_contexts()
    paths = [p for p in suggested_contexts if p in known]

    if not paths:
        fallback = legacy_persona_registry.get(persona, {}).get("default_contexts", [])
        paths = [p for p in fallback if p in known]
        print(f"[context_loader] Using fallback paths for {persona}: {paths}")
    else:
        print(f"[context_loader] Using routed paths for {persona}: {paths}")

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

