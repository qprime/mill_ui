from pathlib import Path
import os
import json
from typing import List, Dict, Optional, Tuple
from difflib import SequenceMatcher
from .personas import persona_registry
from scripts.memory.memory_manager import get_known_contexts



def load_json(path: Path) -> dict:
    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

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


def build_context_prompt_fragments(paths: list, prompt: str = "") -> list:
    import glob
    from difflib import SequenceMatcher

    context_chunks = []

    for path in paths:
        abs_path = os.path.join("memory", path)
        if not os.path.exists(abs_path):
            continue

        files = glob.glob(f"{abs_path}/**/*.*", recursive=True)
        for f in files:
            if not f.endswith((".md", ".jsonl", ".json")):
                continue
            try:
                with open(f, "r", encoding="utf-8") as infile:
                    text = infile.read()
                    score = SequenceMatcher(None, prompt.lower(), text[:500].lower()).ratio()
                    context_chunks.append((score, text.strip()))
            except Exception as e:
                print(f"[build_context_prompt_fragments] Failed to read {f}: {e}")

    # Sort by similarity and return top 5–10
    context_chunks.sort(key=lambda x: x[0], reverse=True)
    top_chunks = [chunk for _, chunk in context_chunks[:8]]
    return top_chunks



def get_project_context(query: str, paths: Optional[List[str]] = None, top_n: int = 3) -> str:
    """
    Retrieve the top-N most relevant context fragments based on string similarity to the query.
    Future version may use vector-based retrieval.
    """
    all_chunks = build_context_prompt_fragments(paths)
    scored: List[Tuple[str, float]] = [
        (chunk, SequenceMatcher(None, query.lower(), chunk.lower()).ratio())
        for chunk in all_chunks
    ]
    top_chunks = sorted(scored, key=lambda x: x[1], reverse=True)[:top_n]

    # print(f"[get_project_context] Searching RAG in: {paths}")
    # print(f"[get_project_context] Using distilled prompt: {prompt}")
    # print(f"[get_project_context] Found RAG length: {len(context)} chars")

    return "\n\n".join(chunk for chunk, _ in top_chunks)


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



def load_context_for_persona(prompt: str, persona: str, suggested_contexts: list[str]) -> str:
    """
    Load memory context (RAG) for the given prompt, persona, and suggested contexts.
    Falls back to the persona's default contexts if the suggested list is empty or unknown.
    """
    known = get_known_contexts()
    paths = [p for p in suggested_contexts if p in known]

    if not paths:
        fallback = persona_registry.get(persona, {}).get("default_contexts", [])
        paths = [p for p in fallback if p in known]
        print(f"[context_loader] Using fallback paths for {persona}: {paths}")
    else:
        print(f"[context_loader] Using routed paths for {persona}: {paths}")

    if persona == "cliff_core":
        return "\n\n".join(get_cliff_core_base_context())

    return get_project_context(prompt, paths=paths)

