#!/usr/bin/env python3
"""CLI tool for dumping AST and RemovalIntent IR to JSON.

Usage:
    python -m skills.mill_ui.v2.cli.introspect dump-ast <layout.json>
    python -m skills.mill_ui.v2.cli.introspect dump-removal-intent <layout.json>

Outputs deterministic, machine-readable JSON for inspection and validation.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from skills.mill_ui.v2.ast.layout import LayoutAST
from skills.mill_ui.v2.adapters.hints_to_removal import (
    profile_hint_to_removal_intent,
    pocket_hint_to_removal_intent,
    hole_hint_to_removal_intent,
    engrave_hint_to_removal_intent,
)


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
        This requires building hints from the layout first.
        For template-based layouts, templates must be resolved.
    """
    # Parse layout
    ast = LayoutAST.from_json(layout_path)

    # For now, only handle shape-based items directly
    # Template expansion would require resolve_templates()
    removal_intents = []

    for item in ast.items:
        if item.kind != "shape":
            # Skip templates - would need template resolution
            continue

        if item.feature is None or item.geometry is None or item.placement is None:
            continue

        # Build hint dict from item
        # Geometry object has a 'data' field containing the actual geometry dict
        geometry_data = item.geometry.data if hasattr(item.geometry, "data") else {}

        hint: dict[str, Any] = {
            "id": item.shape_id or "",
            "shape": item.type,
            "geometry": geometry_data,
            "center_xy_mm": item.placement.center_xy_mm if item.placement else (0.0, 0.0),
            "depth_mm": 0.0,
        }

        # Extract depth from feature
        if item.feature.depth == "through":
            hint["depth_mm"] = ast.sheet.thickness_mm
        elif item.feature.depth_mm is not None:
            hint["depth_mm"] = item.feature.depth_mm
        else:
            hint["depth_mm"] = ast.sheet.thickness_mm

        # Extract feature-specific fields
        if item.feature.type == "profile":
            if item.feature.side:
                hint["side"] = item.feature.side
            if hasattr(item.feature, "tabs") and item.feature.tabs:
                hint["tabs"] = item.feature.tabs.__dict__ if hasattr(item.feature.tabs, "__dict__") else item.feature.tabs

            intent = profile_hint_to_removal_intent(hint, sheet_thickness_mm=ast.sheet.thickness_mm)

        elif item.feature.type == "pocket":
            if hasattr(item.feature, "start_depth_mm") and item.feature.start_depth_mm is not None:
                hint["start_depth_mm"] = item.feature.start_depth_mm

            intent = pocket_hint_to_removal_intent(hint)

        elif item.feature.type == "hole":
            intent = hole_hint_to_removal_intent(hint)

        elif item.feature.type == "engrave":
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
