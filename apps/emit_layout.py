# path: skills/mill_ui/apps/emit_layout.py
from __future__ import annotations

import sys, json, argparse
from pathlib import Path
from typing import Any, Dict, List, Optional


from skills.mill_ui.io.layout_utils import skeleton_layout, write_layout


def _save_json(path: Path, obj: Any) -> None:
    write_layout(path, obj)


def _merge(dst: Dict[str, Any], src: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(dst)
    for k, v in src.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _merge(out[k], v)
        else:
            out[k] = v
    return out


def _parse_args(argv: List[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="emit_layout", description="Emit layout.json skeletons or infer them from STEP")
    sub = p.add_subparsers(dest="cmd", required=True)

    p_sk = sub.add_parser("skeleton", help="Write a generic layout.json skeleton")
    p_sk.add_argument("--out", type=str, help="Output file (default: print to stdout)")

    p_st = sub.add_parser("from-step", help="Build layout.json from a STEP file (2.5D)")
    p_st.add_argument("step", type=str, help="Path to STEP file")
    p_st.add_argument("--units", choices=["mm", "inch"], default="mm", help="Units of the STEP geometry")
    p_st.add_argument("--margin-mm", type=float, default=5.0, help="Border margin added around inferred XY bounds")
    p_st.add_argument("--sheet-width-mm", type=float, help="Override sheet width")
    p_st.add_argument("--sheet-height-mm", type=float, help="Override sheet height")
    p_st.add_argument("--sheet-thickness-mm", type=float, help="Override sheet thickness")
    p_st.add_argument("--kerf-width-mm", type=float, help="Kerf width to record (optional)")
    p_st.add_argument("--out", type=str, help="Output file (default: <step_dir>/input/layout.json)")

    return p.parse_args(argv)


def _emit_skeleton(out_path: Optional[Path]) -> int:
    data = skeleton_layout()
    if out_path:
        _save_json(out_path, data)
    else:
        sys.stdout.write(json.dumps(data, indent=2))
        sys.stdout.write("\n")
    return 0


def _emit_from_step(args: argparse.Namespace) -> int:
    try:
        from skills.mill_ui.cad.importers.step_to_items import infer_layout_from_step
    except Exception as exc:
        print(f"Unable to import STEP importer: {exc}", file=sys.stderr)
        return 2

    step_path = Path(args.step)
    if not step_path.exists():
        print(f"STEP not found: {step_path}", file=sys.stderr)
        return 2

    units = str(args.units)
    margin = float(args.margin_mm or 0.0)

    sheet_over = {}
    if args.sheet_width_mm is not None:
        sheet_over["width_mm"] = float(args.sheet_width_mm)
    if args.sheet_height_mm is not None:
        sheet_over["height_mm"] = float(args.sheet_height_mm)
    if args.sheet_thickness_mm is not None:
        sheet_over["thickness_mm"] = float(args.sheet_thickness_mm)

    base = skeleton_layout()
    inferred = infer_layout_from_step(step_path, units=units, margin_mm=margin, sheet_overrides=sheet_over or None)
    if args.kerf_width_mm is not None:
        inferred["kerf_width_mm"] = float(args.kerf_width_mm)

    data = _merge(base, inferred)

    if args.out:
        out_path = Path(args.out)
    else:
        out_path = step_path.parent / "input" / "layout.json"
    _save_json(out_path, data)
    print(out_path)
    return 0


def main(argv: List[str]) -> int:
    args = _parse_args(argv)
    if args.cmd == "skeleton":
        return _emit_skeleton(Path(args.out) if args.out else None)
    if args.cmd == "from-step":
        return _emit_from_step(args)
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
