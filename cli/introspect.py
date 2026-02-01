
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from layout_ast.layout import LayoutAST
from layout_ast.parsers import parse_layout_json
from layout_ast.emitters import emit_layout_json
from adapters.ast_to_removal import ast_to_removal_intents


def dump_ast(layout_path: str) -> str:
    ast = parse_layout_json(layout_path)
    return emit_layout_json(ast)


def dump_removal_intent(layout_path: str) -> str:
    ast = parse_layout_json(layout_path)
    intents = ast_to_removal_intents(ast)


    result = []
    for intent in intents:
        intent_dict = intent.to_dict()

        intent_dict["depth_mm"] = intent.depth_mm()
        result.append(intent_dict)

    return json.dumps(result, indent=2, sort_keys=True)


__all__ = ["dump_ast", "dump_removal_intent"]
