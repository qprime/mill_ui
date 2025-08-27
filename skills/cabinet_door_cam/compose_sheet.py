# path: skills/cabinet_door_cam/compose_sheet.py
# desc: Place multiple doors on a sheet by injecting per-part origin offsets into temporary orders.
# api: main() CLI; or call compose_sheet(layout_path: str) -> list[dict[str,str]]
# tags: layout, sheet, composer

from __future__ import annotations
import json, shutil
from pathlib import Path
from typing import List, Dict, Any
import argparse, uuid

from skills.cabinet_door_cam.generate_door_cam import generate_door_cam  # reuse your runner

def _read_json(p: Path) -> dict:
    return json.loads(Path(p).read_text(encoding="utf-8"))

def _write_json(p: Path, obj: dict) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, separators=(",", ":"), sort_keys=True), encoding="utf-8")

def _inject_offset(order_obj: dict, dx: float, dy: float, gutter: float | None) -> dict:
    jover = dict(order_obj.get("job_overrides", {}))
    oofs  = dict(jover.get("origin_offset_mm", {}))
    oofs["dx"] = float(dx)
    oofs["dy"] = float(dy)
    jover["origin_offset_mm"] = oofs
    if gutter is not None:
        jover["gutter_mm"] = float(gutter)
    order_obj["job_overrides"] = jover
    return order_obj

def _rot_bbox(w: float, h: float, deg: int) -> tuple[float, float, float, float]:
    """BBox of a W×H rect with corners (0,0),(W,0),(W,H),(0,H) rotated about (0,0)."""
    d = deg % 360
    if d == 0:
        xs, ys = [0, w, w, 0], [0, 0, h, h]
    elif d == 90:
        xs, ys = [0, 0, -h, -h], [0, w, w, 0]
    elif d == 180:
        xs, ys = [0, -w, -w, 0], [0, 0, -h, -h]
    elif d == 270:
        xs, ys = [0, 0, h, h], [0, -w, -w, 0]
    else:
        raise ValueError("rotation_deg must be 0/90/180/270")
    return min(xs), min(ys), max(xs), max(ys)

def compose_sheet(layout_path: str, packs_dir: str | None = None, debug_svg: bool = False) -> List[Dict[str, str]]:
    sheet = _read_json(Path(layout_path))
    parts = sheet.get("parts", [])
    if not parts:
        raise ValueError("layout has no parts[]")

    tmp_dir = Path("skills/cabinet_door_cam/orders/_composed")
    if tmp_dir.exists():
        shutil.rmtree(tmp_dir)
    tmp_dir.mkdir(parents=True, exist_ok=True)

    artifacts: List[Dict[str, str]] = []
    default_gutter = float(sheet.get("gutter_mm", 0.0))

    for idx, part in enumerate(parts, start=1):
        order_ref = part["order"]
        x = float(part.get("x", 0.0))
        y = float(part.get("y", 0.0))
        gutter = float(part.get("gutter_mm", default_gutter))
        rotation = int(part.get("rotation_deg", 0))

        order_obj = _read_json(Path(order_ref))
        W = float(order_obj["width_mm"])
        H = float(order_obj["height_mm"])

        # 1) bbox of rotated local rect (about 0,0)
        minx, miny, maxx, maxy = _rot_bbox(W, H, rotation)

        # 2) translate so rotated bbox lower-left snaps to target (x,y)
        dx = x - minx
        dy = y - miny

        # 3) inject both origin offset and rotation into a temp order
        order_obj = _inject_offset(order_obj, dx, dy, gutter)
        jover = dict(order_obj.get("job_overrides", {}))
        jover["rotation_deg"] = rotation
        order_obj["job_overrides"] = jover

        out_name = f"composed_{idx:02d}_{uuid.uuid4().hex[:8]}.json"
        tmp_order = tmp_dir / out_name
        _write_json(tmp_order, order_obj)

        artifacts.append(
            generate_door_cam(
                order_path=str(tmp_order),
                packs_dir=packs_dir,
                debug_svg=(str(tmp_order.with_suffix(".svg")) if debug_svg else None),
            )
        )
    return artifacts

def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="compose_sheet",
        description="Place multiple cabinet doors on a sheet by injecting per-part origin offsets."
    )
    p.add_argument("--layout", required=True, help="Path to sheet layout JSON.")
    p.add_argument("--packs", default=None, help="Optional packs dir (default: skills/cabinet_door_cam/packs).")
    p.add_argument("--debug-svg", action="store_true", help="Write per-part geometry SVGs next to temp orders.")
    return p

def main() -> None:
    args = _build_parser().parse_args()
    results = compose_sheet(args.layout, args.packs, debug_svg=args.debug_svg)
    for i, art in enumerate(results, start=1):
        print(f"# Part {i}")
        for k, v in sorted(art.items()):
            print(f"{k}: {v}")

if __name__ == "__main__":
    main()
