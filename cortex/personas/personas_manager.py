# path: cortex/personas/personas_manager.py
# type: persona_management
# tags: persona, json, loading, management
# owner: cliff
# depends_on: json, pathlib
# description: Manages loading and accessing persona data from JSON files.

import json
from pathlib import Path

PERSONA_DIR = Path("cortex/personas")


def load_json_personas(category=""):
    personas = {}
    # Set the search directory based on category or default
    search_dir = PERSONA_DIR / category if category else PERSONA_DIR
    print(f"DEBUG: Searching in {search_dir.resolve()}")

    # Use rglob to search recursively for all .json files
    for file in search_dir.rglob("*.json"):
        with open(file, "r", encoding="utf-8") as f:
            try:
                data = json.load(f)
            except Exception as e:
                print(f"ERROR: Could not parse JSON in file {file}: {e}")
                continue
            # Support for multi-persona files (optional)

            print(f"DEBUG: Found persona '{data.get('name')}' in {file}")

            if (
                isinstance(data, dict)
                and "personas" in data
                and isinstance(data["personas"], list)
            ):
                for persona in data["personas"]:
                        
                    if "name" not in persona:
                        print(f"WARNING: Persona in {file} missing 'name': {persona}")
                        continue
                    personas[persona["name"]] = persona
            elif isinstance(data, dict) and "name" in data:
                personas[data["name"]] = data
            else:
                print(
                    f"WARNING: Could not parse persona file (no 'name'): {file}\nData: {data}"
                )
    return personas


def get_persona(persona_name: str, category: str = "") -> dict:
    personas = load_json_personas(category)
    if persona_name in personas:
        return personas[persona_name]
    raise ValueError(f"Unknown persona: {persona_name} (category: '{category}')")


def list_all_personas(category: str = "") -> list[str]:
    return sorted(load_json_personas(category).keys())
