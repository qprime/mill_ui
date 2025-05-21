from pathlib import Path
import json
from typing import List, Dict

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

from typing import List, Optional
from scripts.llm.context_loader import load_base_context

def build_context_prompt_fragments(paths: Optional[List[str]] = None) -> List[str]:
    """
    Return context fragments for LLM prompts. If `paths` is provided, only return matching fragments.
    Otherwise, return the full default high-level context.
    """
    ctx = load_base_context()

    if paths:
        # You could expand this logic with partial matching or tag-mapping later
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

    # Default: return the full set
    return [
        f"# Project Summary\n{ctx['summary'].get('long_description', '')}",
        f"# Core Goals\n" + "\n".join(f"- {g}" for g in ctx['summary'].get("core_goals", [])),
        f"# Interfaces\n" + "\n".join(f"- {i}" for i in ctx['summary'].get("primary_interfaces", [])),
        f"# Memory Domains\n" + "\n".join(f"- {d['name']}: {d['purpose']}" for d in ctx['memory_graph'].get("domains", [])),
        f"# Modules\n" + "\n".join(f"- {m['name']}" for m in ctx['project_graph'].get("modules", [])),
        f"# Module Summaries\n" + "\n\n".join(ctx["module_summaries"])
    ]


