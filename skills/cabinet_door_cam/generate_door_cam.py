# path: cliff_ai/skills/cabinet_door_cam/generate_door_cam.py
# desc: Single public entrypoint: load packs+order, compute geometry, plan moves, post G-code, write artifacts.
# api: generate_door_cam(order_path: str | None = None, packs_dir: str | None = None) -> dict[str, str]
# tags: entrypoint, cabinet, deterministic, api

from __future__ import annotations
from pathlib import Path
from typing import Dict, Optional
import glob, argparse
from skills.cabinet_door_cam.settings import DEFAULT_ORDER_DIR, DEFAULT_PACKS_DIR
from skills.cabinet_door_cam.resolve_config import resolve_config
from skills.cabinet_door_cam.compute_geometry import compute_geometry
from skills.cabinet_door_cam.plan_toolpaths import plan_toolpaths
from skills.cabinet_door_cam.write_run_artifacts import write_run_artifacts
from skills.cabinet_door_cam.debug_svg import render_debug_svg

def _discover_order(path: Optional[str]) -> Path:
    if path:
        p = Path(path).expanduser().resolve()
        if not p.exists():
            raise FileNotFoundError(f"--order not found: {p}")
        return p
    # default: first *.json in DEFAULT_ORDER_DIR
    candidates = sorted(glob.glob(str(DEFAULT_ORDER_DIR / "*.json")))
    if not candidates:
        raise FileNotFoundError(f"No orders found in: {DEFAULT_ORDER_DIR}")
    return Path(candidates[0]).resolve()

def generate_door_cam(
    order_path: str | None = None,
    packs_dir: str | None = None,
    debug_svg: str | None = None,
) -> Dict[str, str]:
    """Run the full pipeline and return a dict of artifact paths."""
    order_p = _discover_order(order_path)
    packs_p = Path(packs_dir).resolve() if packs_dir else DEFAULT_PACKS_DIR

    cfg = resolve_config(order_p, packs_p)
    geo = compute_geometry(cfg)

    artifacts: Dict[str, str] = {}
    if debug_svg:
        svg_path = render_debug_svg(cfg, geo, debug_svg)
        artifacts["debug_svg"] = svg_path

    jobs = plan_toolpaths(cfg, geo)

    fingerprint = {
        "skill": "cabinet_door_cam",
        "style": cfg.style.style_id,
        "style_version": getattr(cfg.style, "version", None),
        "width_mm": cfg.order.width_mm,
        "height_mm": cfg.order.height_mm,
        "thickness_mm": cfg.order.thickness_mm,
        "tool_strategy": getattr(cfg.order, "tool_strategy", None),
    }

    written = write_run_artifacts(cfg, geo, jobs, fingerprint)
    artifacts.update(written)
    return artifacts

def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="cabinet_door_cam",
        description="Generate cabinet door CAM + optional debug SVG."
    )
    p.add_argument("--order", type=str, default=None,
                   help="Path to order JSON (default: first JSON in orders/).")
    p.add_argument("--packs", type=str, default=None,
                   help="Path to packs dir (default: ./packs).")
    p.add_argument("--debug-svg", type=str, default=None,
                   help="If set, write a geometry SVG to this path.")
    return p

def main() -> None:
    args = _build_parser().parse_args()
    paths = generate_door_cam(order_path=args.order, packs_dir=args.packs, debug_svg=args.debug_svg)
    for k, v in sorted(paths.items()):
        print(f"{k}: {v}")

if __name__ == "__main__":
    main()