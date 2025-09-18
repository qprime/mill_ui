from typing import Optional, List, Dict, Any
import os
import json

from memories.sidecar_manager import load_sidecar
from continuum.metadata import fetch_metadata
from continuum.project_graph import build_project_graph
from cortex.personas.personas_manager import get_persona

# --- Always-injected file logic unchanged ---
_ALWAYS_INCLUDE_FILES = """
{
    "memories/living_truths/cliff.mind.md": false,
    "README.md": false,
    "SOME_OTHER_FILE.md": false
}
"""
def get_always_injected_file_paths() -> Dict[str, bool]:
    return json.loads(_ALWAYS_INCLUDE_FILES)

def load_always_injected_files() -> str:
    injected = []
    for file_path, enabled in get_always_injected_file_paths().items():
        if enabled:
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read()
                injected.append(f"\n# {file_path}\n{content}")
            except Exception as e:
                injected.append(f"\n# {file_path}\n[Could not read: {e}]")
    return "\n\n".join(injected)

# --- Persona helpers ---
def get_persona_context_filters(persona_name, persona_category=""):
    persona = get_persona(persona_name, persona_category)
    return persona.get("default_contexts", [])

def load_persona_context(persona_name: str, category: str = "") -> str:
    persona = get_persona(persona_name, category)
    return persona.get("system_prompt", "")

def load_generic_memory() -> str:
    return ""

# --- Context builders for each context tag/persona ---
def context_for_development(persona, chat_id, headers_only, root_dir, persona_category):
    """Everything needed for 'development' context."""
    blocks = []
    # Sidecar memory (if any)
    if chat_id:
        sidecar_context = load_sidecar(chat_id, persona)
        if sidecar_context:
            blocks.append(sidecar_context)
    # Metadata
    metadata_context, stats = fetch_metadata(root_dir=root_dir)
    if metadata_context:
        blocks.append(metadata_context)
    
    return "\n\n".join(str(b) for b in blocks if b)

def context_for_distiller_intent(persona, chat_id, headers_only, root_dir, persona_category):
    """Slimmed context for intent distillation. Add blocks as needed."""
    blocks = []
    # Project graph
    project_graph_context = build_project_graph(root_dir)
    if project_graph_context:
        # Formatting, see original for details
        blocks.append(json.dumps(project_graph_context, indent=2))
    # Source code
    code_context = fetch_metadata(root_dir=root_dir)
    if code_context:
        blocks.append(code_context)
    return "\n\n".join(str(b) for b in blocks if b)

def context_for_distiller_context(persona, chat_id, headers_only, root_dir, persona_category):
    """Slimmed context for context-block distiller."""
    return ""  # Replace with actual logic when needed

# --- DISPATCH TABLE ---
CONTEXT_BUILDERS = {
    "development": context_for_development,
    "distiller_intent": context_for_distiller_intent,
    "distiller_context": context_for_distiller_context,
    # Add new context tags and functions as needed
}

# --- Main context function ---
def context(
    prompt: str,
    persona: str,
    chat_id: Optional[str] = None,
    headers_only: bool = False,
    root_dir: str = ".",
    persona_category: str = "",
) -> str:
    context_blocks = []

    # 1. Persona prompt/system role
    persona_context = load_persona_context(persona, persona_category)
    if persona_context:
        context_blocks.append(persona_context)

    # 2. Always-injected files
    always_injected = load_always_injected_files()
    if always_injected:
        context_blocks.append(always_injected)

    # 3. Persona-based context blocks (using dispatch table)
    context_filters = get_persona_context_filters(persona, persona_category)
    if not context_filters:
        # fallback: default to 'development'
        context_filters = ["development"]

    for ctx_tag in context_filters:
        builder = CONTEXT_BUILDERS.get(ctx_tag)
        if builder:
            block = builder(persona, chat_id, headers_only, root_dir, persona_category)
            if block:
                context_blocks.append(block)
        else:
            # Optionally: log or warn unknown context type
            pass

    # 4. Generic memory context (if you ever use it)
    # generic_memory_context = load_generic_memory()
    # if generic_memory_context:
    #     context_blocks.append(generic_memory_context)

    # Compose final prompt context
    full_context = "\n\n".join([str(block) for block in context_blocks if block])
    return full_context
