from pathlib import Path
import json
from typing import List, Dict, Optional, Tuple
from difflib import SequenceMatcher


def load_json(path: Path) -> dict:
    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


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


def build_context_prompt_fragments(paths: Optional[List[str]] = None) -> List[str]:
    """
    Return context fragments for LLM prompts. If `paths` is provided, only return matching fragments.
    Otherwise, return the full default high-level context.
    """
    ctx = load_base_context()

    if paths:
        fragments = []
        if "summary" in paths:
            fragments.append(f"# Project Summary\n{ctx['summary'].get('long_description', '')}")
        if "core_goals" in paths:
            fragments.append(f"# Core Goals\n" + "\n".join(f"- {g}" for g in ctx['summary'].get("core_goals", [])))
        if "interfaces" in paths:
            fragments.append(f"# Interfaces\n" + "\n".join(f"- {i}" for i in ctx['summary'].get("primary_interfaces", [])))
        if "memory_domains" in paths:
            fragments.append(f"# Memory Domains\n" + "\n".join(f"- {d['name']}: {d['purpose']}" for d in ctx['memory_graph'].get("domains", [])))
        if "modules" in paths:
            fragments.append(f"# Modules\n" + "\n".join(f"- {m['name']}" for m in ctx['project_graph'].get("modules", [])))
        if "module_summaries" in paths:
            fragments.append(f"# Module Summaries\n" + "\n\n".join(ctx["module_summaries"]))
        return fragments

    return [
        f"# Project Summary\n{ctx['summary'].get('long_description', '')}",
        f"# Core Goals\n" + "\n".join(f"- {g}" for g in ctx['summary'].get("core_goals", [])),
        f"# Interfaces\n" + "\n".join(f"- {i}" for i in ctx['summary'].get("primary_interfaces", [])),
        f"# Memory Domains\n" + "\n".join(f"- {d['name']}: {d['purpose']}" for d in ctx['memory_graph'].get("domains", [])),
        f"# Modules\n" + "\n".join(f"- {m['name']}" for m in ctx['project_graph'].get("modules", [])),
        f"# Module Summaries\n" + "\n\n".join(ctx["module_summaries"])
    ]


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
