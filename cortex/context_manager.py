# path: cortex/context_manager.py
# type: context assembly
# tags: context, persona, graph, memory, loader
# owner: cliff
# depends_on: memory.sidecar_manager, continuum.code_context, continuum.project_graph, cortex.personas.personas_manager
# description: Assembles various context elements for LLM, including persona, sidecar, project graph, and source code.

from typing import Optional, List, Dict, Any
import os

# Import your actual sidecar and persona loaders
from memories.sidecar_manager import load_sidecar
from continuum.code_context import generate_context
from continuum.project_graph import build_project_graph
from cortex.personas.personas_manager import get_persona


from typing import Optional


def load_source_code_context(headers_only: bool = False, root_dir: str = ".") -> str:
    """
    Loads concatenated code context for the entire source tree.
    If headers_only is True, only Python top-level docstrings are included.
    """
    return generate_context(
        root_dir=root_dir,
        scrub=True,
        docstrings_only=headers_only,
        function_signatures=True,
    )


def load_project_graph_context(root_dir: str = ".") -> str:
    """
    Loads and formats the project graph context for LLM ingestion.
    """
    graph = build_project_graph(root_dir)
    lines = ["# PROJECT GRAPH"]
    for module in graph.get("modules", []):
        lines.append(f"\n## Module: {module['name']}")
        lines.append(
            "Files:\n" + "\n".join(f"  - {f}" for f in module.get("files", []))
        )
        if module.get("links_to"):
            lines.append(f"Links to: {', '.join(module['links_to'])}")
        else:
            lines.append("Links to: (none)")
    return "\n".join(lines)


def load_persona_context(persona_name: str, category: str = "") -> str:
    """
    Loads the system prompt or persona context string.
    """
    persona = get_persona(persona_name, category)
    return persona.get("system_prompt", "")


def load_generic_memory() -> str:
    """
    Loads generic memory or knowledge not covered by other domains (stub).
    """
    return ""


def context(
    prompt: str,
    persona: str,
    chat_id: Optional[str] = None,
    headers_only: bool = False,
    root_dir: str = ".",
    persona_category: str = "",
) -> str:
    """
    Returns a fully assembled context string for LLM injection:
    Persona (system prompt), Sidecar, Project Graph, Source Code (in that order).
    """
    context_blocks = []

    # --- Load Persona Context (system prompt/role) ---
    persona_context = load_persona_context(persona, persona_category)
    if persona_context:
        context_blocks.append(persona_context)

    # --- Load Sidecar (session/persona memory) ---
    if chat_id:
        from memories.sidecar_manager import load_sidecar

        sidecar_context = load_sidecar(chat_id, persona)
        if sidecar_context:
            context_blocks.append(sidecar_context)

    # --- Load Project Graph Context ---
    project_graph_context = load_project_graph_context(root_dir=root_dir)
    if project_graph_context:
        context_blocks.append(project_graph_context)

    # --- Load Source Code Context ---
    code_context = load_source_code_context(
        headers_only=headers_only, root_dir=root_dir
    )
    if code_context:
        context_blocks.append(code_context)

    # --- Load Generic Memory Context (stub) ---
    generic_memory_context = load_generic_memory()
    if generic_memory_context:
        context_blocks.append(generic_memory_context)

    # Assemble final context string in the correct order
    full_context = "\n\n".join([str(block) for block in context_blocks if block])
    return full_context
