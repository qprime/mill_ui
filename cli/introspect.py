from __future__ import annotations

import json
from pathlib import Path

from adapters.ast_to_removal import ast_to_removal_intents
from cam.compilation import load_pml_asts


def dump_removal_intent(source_path: str) -> str:
    asts, _ = load_pml_asts(Path(source_path))
    return json.dumps(
        [
            [{**intent.to_dict(), "depth_mm": intent.depth_mm()} for intent in ast_to_removal_intents(ast)]
            for ast in asts
        ],
        indent=2,
        sort_keys=True,
    )


__all__ = ["dump_removal_intent"]
