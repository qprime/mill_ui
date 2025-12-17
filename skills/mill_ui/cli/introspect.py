#!/usr/bin/env python3
"""CLI tool for dumping AST and RemovalIntent IR to JSON.

Usage:
    python -m skills.mill_ui.cli.introspect dump-ast <layout.json>
    python -m skills.mill_ui.cli.introspect dump-removal-intent <layout.json>

Outputs deterministic, machine-readable JSON for inspection and validation.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from skills.mill_ui.layout_ast.layout import LayoutAST
from skills.mill_ui.adapters.hints_to_removal import (
    profile_hint_to_removal_intent,
    pocket_hint_to_removal_intent,
    hole_hint_to_removal_intent,
    engrave_hint_to_removal_intent,
)
from skills.mill_ui.compositions import resolve_templates


def dump_ast(layout_path: str) -> str:
    """Dump LayoutAST as canonical JSON.

    Args:
        layout_path: Path to layout.json file

    Returns:
        Canonical JSON string of LayoutAST
    """
    ast = LayoutAST.from_json(layout_path)
    return ast.to_json()


def dump_removal_intent(layout_path: str) -> str:
    """Dump RemovalIntent IR as JSON.

    Args:
        layout_path: Path to layout.json file

    Returns:
        JSON array of RemovalIntent records

    Note:
        Templates are automatically expanded via resolve_templates().
    """
    # Parse layout
    ast = LayoutAST.from_json(layout_path)

    # Convert AST items to dict format for resolve_templates
    items_as_dicts = []
    for item in ast.items:
        item_dict: dict[str, Any] = {
            "kind": item.kind,
            "type": item.type,
        }
        if item.kind == "template":
            if item.params:
                item_dict["params"] = item.params
            if item.id:
                item_dict["id"] = item.id
            if item.placement:
                item_dict["placement"] = {"center_xy_mm": item.placement.center_xy_mm}
        else:  # shape
            if item.geometry:
                item_dict["geometry"] = item.geometry.data
            if item.placement:
                item_dict["placement"] = {"center_xy_mm": item.placement.center_xy_mm}
            if item.feature:
                feature_dict: dict[str, Any] = {
                    "type": item.feature.type,
                    "depth": item.feature.depth,
                }
                if item.feature.side:
                    feature_dict["side"] = item.feature.side
                if item.feature.depth_mm is not None:
                    feature_dict["depth_mm"] = item.feature.depth_mm
                item_dict["feature"] = feature_dict
            if item.shape_id:
                item_dict["id"] = item.shape_id

        items_as_dicts.append(item_dict)

    # Resolve templates to concrete shapes
    resolved_items = resolve_templates(items_as_dicts, sheet_thickness_mm=ast.sheet.thickness_mm)

    removal_intents = []

    # resolved_items are now dicts (from resolve_templates)
    for item in resolved_items:
        if item.get("kind") != "shape":
            continue

        feature = item.get("feature")
        geometry = item.get("geometry")
        placement = item.get("placement")

        if not feature or not geometry or not placement:
            continue

        # Build hint dict from resolved item
        hint: dict[str, Any] = {
            "id": item.get("id", ""),
            "shape": item.get("type", ""),
            "geometry": geometry,
            "center_xy_mm": placement.get("center_xy_mm", (0.0, 0.0)),
            "depth_mm": 0.0,
        }

        # Extract depth from feature
        depth = feature.get("depth")
        if depth == "through":
            hint["depth_mm"] = ast.sheet.thickness_mm
        elif feature.get("depth_mm") is not None:
            hint["depth_mm"] = feature["depth_mm"]
        elif isinstance(depth, (int, float)):
            hint["depth_mm"] = float(depth)
        else:
            hint["depth_mm"] = ast.sheet.thickness_mm

        # Extract feature-specific fields
        feature_type = feature.get("type", "profile")

        if feature_type == "profile":
            if feature.get("side"):
                hint["side"] = feature["side"]
            if feature.get("tabs"):
                hint["tabs"] = feature["tabs"]

            intent = profile_hint_to_removal_intent(hint, sheet_thickness_mm=ast.sheet.thickness_mm)

        elif feature_type == "pocket":
            if feature.get("start_depth_mm") is not None:
                hint["start_depth_mm"] = feature["start_depth_mm"]

            intent = pocket_hint_to_removal_intent(hint)

        elif feature_type == "hole":
            intent = hole_hint_to_removal_intent(hint)

        elif feature_type == "engrave":
            intent = engrave_hint_to_removal_intent(hint)

        else:
            # Unknown feature type, skip
            continue

        # Serialize RemovalIntent to dict
        removal_intents.append(_removal_intent_to_dict(intent))

    # Return as JSON array
    return json.dumps(removal_intents, indent=2, sort_keys=True, ensure_ascii=False)


def _removal_intent_to_dict(intent: Any) -> dict[str, Any]:
    """Convert RemovalIntent to JSON-serializable dict."""
    return {
        "region_id": intent.region_id,
        "bounds": {
            "x_min": intent.bounds.x_min,
            "x_max": intent.bounds.x_max,
            "y_min": intent.bounds.y_min,
            "y_max": intent.bounds.y_max,
        },
        "z_top": intent.z_top,
        "z_bottom": intent.z_bottom,
        "depth_mm": intent.depth_mm(),
        "allowance": {
            "inside": intent.allowance.inside,
            "outside": intent.allowance.outside,
            "on": intent.allowance.on,
            "kerf_compensation": intent.allowance.kerf_compensation,
        },
        "constraints": {
            "tabs": {
                "count": intent.constraints.tabs.count,
                "height_mm": intent.constraints.tabs.height_mm,
                "width_mm": intent.constraints.tabs.width_mm,
            } if intent.constraints.tabs else None,
            "keepouts": intent.constraints.keepouts,
            "islands": intent.constraints.islands,
            "tolerance_mm": intent.constraints.tolerance_mm,
            "safe_z_mm": intent.constraints.safe_z_mm,
        },
        "metadata": intent.metadata,
    }


def main() -> int:
    """CLI entrypoint."""
    parser = argparse.ArgumentParser(
        description="Dump AST and RemovalIntent IR to JSON for inspection",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    # dump-ast command
    dump_ast_parser = subparsers.add_parser(
        "dump-ast",
        help="Dump LayoutAST as canonical JSON",
    )
    dump_ast_parser.add_argument(
        "layout",
        type=str,
        help="Path to layout.json file",
    )

    # dump-removal-intent command
    dump_removal_parser = subparsers.add_parser(
        "dump-removal-intent",
        help="Dump RemovalIntent IR as JSON",
    )
    dump_removal_parser.add_argument(
        "layout",
        type=str,
        help="Path to layout.json file",
    )

    args = parser.parse_args()

    try:
        if args.command == "dump-ast":
            output = dump_ast(args.layout)
            print(output)
            return 0

        elif args.command == "dump-removal-intent":
            output = dump_removal_intent(args.layout)
            print(output)
            return 0

        else:
            print(f"Unknown command: {args.command}", file=sys.stderr)
            return 1

    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except json.JSONDecodeError as e:
        print(f"Error parsing JSON: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
