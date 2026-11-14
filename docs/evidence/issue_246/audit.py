from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

from shapely import from_wkb, to_wkb
from shapely.affinity import translate
from shapely.geometry import LineString, Point, Polygon, box
from shapely.ops import unary_union
from shapely.strtree import STRtree

PROOF_RECIPES = {
    "base_cabinet",
    "bookcase",
    "box_bottoms_and_lids",
    "cubby_organizer",
    "finger_jointed_box",
    "long_spliced_rail",
    "side_table_frame",
    "joinery_test_coupons",
}


def digest(data):
    return hashlib.sha256(data).hexdigest()


def region(item):
    data = item.geometry.data
    cx, cy = item.placement.center_xy_mm
    if item.type == "Rect":
        return box(cx - data["w_mm"] / 2, cy - data["h_mm"] / 2, cx + data["w_mm"] / 2, cy + data["h_mm"] / 2)
    if item.type == "Circle":
        return Point(cx, cy).buffer(data.get("diameter_mm", 2 * data.get("radius_mm", 0)) / 2, quad_segs=128)
    if item.type == "Polygon":
        return Polygon([(cx + x, cy + y) for x, y in data["points"]])
    raise ValueError(f"Unsupported proof profile: {item.type}")


def nc_segments(path, diameter):
    from validation.metrics.gcode_metrics import _parse_moves

    segments = []
    previous = None
    content = path.read_text()
    if re.search(r"^G[23](?:\s|$)", content, flags=re.MULTILINE):
        raise ValueError(f"Arc sweep reconstruction required: {path}")
    for move in _parse_moves(content.splitlines()):
        if previous is not None and move["type"] == "feed" and min(move["z"], previous["z"]) < 0:
            segments.append(
                (
                    LineString([(previous["x"], previous["y"]), (move["x"], move["y"])]),
                    diameter / 2,
                    previous["z"],
                    move["z"],
                )
            )
        previous = move
    return segments


def section_sweep(segment, depth):
    line, radius, z0, z1 = segment
    target = -depth
    if min(z0, z1) > target:
        return None
    if max(z0, z1) > target:
        fraction = (target - z0) / (z1 - z0)
        start, end = line.coords[0], line.coords[-1]
        crossing = (start[0] + fraction * (end[0] - start[0]), start[1] + fraction * (end[1] - start[1]))
        line = LineString((crossing, end) if z0 > target else (start, crossing))
    return line.buffer(radius, quad_segs=32)


def audit_programs(recipe, asts, sheet_summaries):
    from validation.core import Verdict
    from validation.invariants.gcode_invariants import check_gcode_invariants_from_content

    result = {
        "programs": 0,
        "cutting_segments": 0,
        "margin_violations": [],
        "fixture_violations": [],
        "invariant_failures": [],
        "max_material_stepdown_mm": 0.0,
        "authorized_surface_programs": [],
    }
    for ast, sheet in zip(asts, sheet_summaries, strict=True):
        keepouts = [
            translate(region(item), xoff=ast.sheet.margin_mm, yoff=ast.sheet.margin_mm)
            for item in ast.items
            if item.kind == "keepout"
        ]
        for entry in sheet["files"]:
            path = recipe.path / "output" / entry["filename"]
            surface = entry["operation"] == "surface"
            if surface:
                result["authorized_surface_programs"].append(path.name)
            checks = check_gcode_invariants_from_content(
                path.read_text(),
                safe_z_mm=ast.sheet.safe_z_mm or 6,
                sheet_width_mm=ast.sheet.width_mm,
                sheet_height_mm=ast.sheet.height_mm,
                margin_mm=entry["tool_diameter_mm"] if surface else 0,
            )
            result["invariant_failures"].extend(
                {"file": path.name, "check": check.id, "failures": check.failures}
                for check in checks
                if check.status == Verdict.FAIL
            )
            segments = nc_segments(path, entry["tool_diameter_mm"])
            result["programs"] += 1
            result["cutting_segments"] += len(segments)
            for line, radius, z0, z1 in segments:
                penetration = max(0.0, -z1) - max(0.0, -z0)
                result["max_material_stepdown_mm"] = max(result["max_material_stepdown_mm"], penetration)
                x0, y0, x1, y1 = line.bounds
                overrun = max(
                    ast.sheet.margin_mm + radius - x0,
                    ast.sheet.margin_mm + radius - y0,
                    x1 + radius - ast.sheet.width_mm + ast.sheet.margin_mm,
                    y1 + radius - ast.sheet.height_mm + ast.sheet.margin_mm,
                )
                if not surface and overrun > 0.001:
                    result["margin_violations"].append({"file": path.name, "overrun_mm": overrun})
                    break
                if not path.name.startswith("back-") and any(
                    line.distance(keepout) < radius - 0.001 for keepout in keepouts
                ):
                    result["fixture_violations"].append({"file": path.name})
                    break
    return result


def source_snapshot(recipe):
    from cli.mill import _load_recipe_source

    summary = json.loads((recipe.path / "output/machining_summary.json").read_text())
    sheet_summaries = summary.get("sheets", [summary])
    asts = []
    for source in recipe.pml_sources + recipe.nest_sources:
        resolved, _ = _load_recipe_source(source, None)
        asts.extend(resolved)
    result = {
        "sheets": len(asts),
        "runtime_min": summary.get("total_runtime_min", 0),
        "shared_length_mm": 0,
        "parts": [],
        "seam_traversals": [],
        "packing": [],
    }
    result["program_audit"] = audit_programs(recipe, asts, sheet_summaries)
    if recipe.name not in PROOF_RECIPES:
        return result
    nominal_area = 0
    sheet_area = 0
    for sheet_index, (ast, sheet_summary) in enumerate(zip(asts, sheet_summaries, strict=True), 1):
        files = sheet_summary["files"]
        segments = [
            segment
            for entry in files
            for segment in nc_segments(recipe.path / "output" / entry["filename"], entry["tool_diameter_mm"])
        ]
        tree = STRtree([segment[0] for segment in segments])
        max_radius = max((segment[1] for segment in segments), default=0)
        profiles = [
            item
            for item in ast.items
            if item.feature is not None and item.feature.type == "profile" and item.feature.side == "outside"
        ]
        result["packing"].append(ast.config.get("packing_preflight", []))
        sheet_area += ast.sheet.working_width_mm * ast.sheet.working_height_mm
        for item in profiles:
            shape = region(item)
            nominal_area += shape.area
            cx, cy = item.placement.center_xy_mm
            local = translate(shape, xoff=-cx, yoff=-cy)
            material = translate(shape, xoff=ast.sheet.margin_mm, yoff=ast.sheet.margin_mm)
            candidates = [segments[int(i)] for i in tree.query(material.buffer(max_radius))]
            sections = []
            for depth in (1.0, ast.sheet.thickness_mm / 2 + 0.01, ast.sheet.thickness_mm - 0.01):
                sweeps = [sweep for segment in candidates if (sweep := section_sweep(segment, depth)) is not None]
                finished = material.difference(unary_union(sweeps))
                finished = translate(finished, xoff=-cx - ast.sheet.margin_mm, yoff=-cy - ast.sheet.margin_mm)
                sections.append(
                    {
                        "depth_mm": depth,
                        "area_mm2": finished.area,
                        "bounds": finished.bounds,
                        "wkb": to_wkb(finished, hex=True),
                    }
                )
            result["parts"].append(
                {"name": item.label or item.shape_id, "nominal": to_wkb(local, hex=True), "sections": sections}
            )
        try:
            from adapters.ast_to_removal import ast_to_removal_intents
            from adapters.removal_to_planner import removal_intents_to_planner_input
            from cam.config import Config
            from cam.planner.passes.merge_shared_edges import merge_profiles
        except ImportError:
            continue
        profile_entries = removal_intents_to_planner_input(ast_to_removal_intents(ast)).profiles
        diameter = ast.machining_clearance.profile_diameter_mm if ast.machining_clearance else 3.175
        groups = merge_profiles(profile_entries, tool_diameter_mm=diameter, config=Config())
        seams = [
            translate(LineString([(p.x, p.y) for p in seam.points]), xoff=ast.sheet.margin_mm, yoff=ast.sheet.margin_mm)
            for group in groups
            for seam in group.seams
        ]
        result["shared_length_mm"] += unary_union(seams).length
        profile_segments = [
            segment
            for entry in files
            if entry["operation"] == "profile"
            for segment in nc_segments(recipe.path / "output" / entry["filename"], entry["tool_diameter_mm"])
        ]
        for seam_index, seam in enumerate(seams):
            traversals = {}
            ramp_length = 0.0
            for line, _, z0, z1 in profile_segments:
                if line.length <= 0:
                    continue
                parallel = line.distance(seam) <= 0.001
                if not parallel:
                    continue
                overlap = line.intersection(seam.buffer(0.0006, cap_style="flat")).length
                if overlap <= 0.003:
                    continue
                if abs(z0 - z1) <= 1e-8:
                    key = str(round(z1, 3))
                    traversals[key] = traversals.get(key, 0.0) + overlap
                else:
                    ramp_length += overlap
            result["seam_traversals"].append(
                {
                    "sheet": sheet_index,
                    "seam": seam_index,
                    "length_mm": seam.length,
                    "level_travel_mm": traversals,
                    "ramp_travel_mm": ramp_length,
                }
            )
    result["utilization"] = nominal_area / sheet_area if sheet_area else 0
    return result


def snapshot(repo, output):
    sys.path.insert(0, str(repo))
    from validation.recipes import find_recipes

    recipes = find_recipes(repo / "docs/recipes")
    result = {
        "head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo, text=True).strip(),
        "hashes": {},
        "recipes": {},
    }
    for recipe in recipes:
        for path in sorted(recipe.path.rglob("*")):
            if path.is_file() and (path.name.endswith((".pml.yml", ".nest.yml", ".nc"))):
                result["hashes"][str(path.relative_to(repo))] = digest(path.read_bytes())
        print(recipe.name, flush=True)
        result["recipes"][recipe.name] = source_snapshot(recipe)
    output.write_text(json.dumps(result, indent=2) + "\n")


def compare(before_path, after_path, output):
    before, after = (json.loads(path.read_text()) for path in (before_path, after_path))
    report = {
        "baseline": before["head"],
        "hashes": {"before": before["hashes"], "after": after["hashes"]},
        "recipes": {},
    }
    for name, current in after["recipes"].items():
        previous = before["recipes"][name]
        row = {
            key: {"before": previous.get(key), "after": current.get(key)}
            for key in ("sheets", "runtime_min", "utilization", "shared_length_mm")
        }
        row["program_audit"] = current["program_audit"]
        audit = current["program_audit"]
        if audit["margin_violations"] or audit["fixture_violations"]:
            raise ValueError(f"Emitted cutter clearance failed: {name}")
        if audit["max_material_stepdown_mm"] > 26:
            raise ValueError(f"Emitted material stepdown exceeds 26mm: {name}")
        limitations = []
        for failure in audit["invariant_failures"]:
            matches = [
                path
                for path in after["hashes"]
                if path.endswith("/" + failure["file"]) and "/" + name + "/output/" in path
            ]
            if (
                failure["check"] != "GCODE_MAX_STEPDOWN"
                or not matches
                or any(before["hashes"].get(path) != after["hashes"][path] for path in matches)
            ):
                raise ValueError(f"New emitted-program invariant failure: {name}: {failure}")
            limitations.append(failure)
        row["baseline_checker_limitations"] = limitations
        for seam in current["seam_traversals"]:
            if not seam["level_travel_mm"]:
                raise ValueError(f"Shared seam has no emitted travel: {name}")
            if any(abs(travel - seam["length_mm"]) > 0.01 for travel in seam["level_travel_mm"].values()):
                raise ValueError(f"Shared seam has duplicate or incomplete travel: {name}")
        row["seam_traversals"] = [{**seam, "extra_full_traversals": 0} for seam in current["seam_traversals"]]
        row["packing"] = current["packing"]
        row["parts"] = []
        if current["parts"]:
            old_parts = sorted(previous["parts"], key=lambda p: p["name"])
            new_parts = sorted(current["parts"], key=lambda p: p["name"])
            if len(old_parts) != len(new_parts):
                raise ValueError(f"Part count changed: {name}")
            for old, new in zip(old_parts, new_parts, strict=True):
                a, b = from_wkb(old["nominal"]), from_wkb(new["nominal"])
                nominal_difference = a.symmetric_difference(b).area
                if nominal_difference > 1e-6:
                    raise ValueError(f"Nominal part changed: {name} / {new['name']}: {nominal_difference}")
                sections = []
                for old_section, new_section in zip(old["sections"], new["sections"], strict=True):
                    a, b = from_wkb(old_section["wkb"]), from_wkb(new_section["wkb"])
                    difference = a.symmetric_difference(b).area
                    raw_bound_difference = max(abs(x - y) for x, y in zip(a.bounds, b.bounds, strict=True))
                    clean_a = a.buffer(-0.001).buffer(0.001)
                    clean_b = b.buffer(-0.001).buffer(0.001)
                    bound_difference = max(abs(x - y) for x, y in zip(clean_a.bounds, clean_b.bounds, strict=True))
                    tolerance = max(a.length, b.length) * 0.002
                    if difference > tolerance or bound_difference > 0.002:
                        raise ValueError(
                            f"Finished material changed: {name} / {new['name']}: {difference} / {bound_difference}"
                        )
                    sections.append(
                        {
                            "depth_mm": new_section["depth_mm"],
                            "before_area_mm2": a.area,
                            "after_area_mm2": b.area,
                            "symmetric_difference_mm2": difference,
                            "max_span_difference_mm": bound_difference,
                            "raw_bound_difference_mm": raw_bound_difference,
                        }
                    )
                row["parts"].append(
                    {"name": new["name"], "nominal_difference_mm2": nominal_difference, "sections": sections}
                )
        report["recipes"][name] = row
    output.write_text(json.dumps(report, indent=2) + "\n")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path)
    parser.add_argument("--snapshot", type=Path)
    parser.add_argument("--before", type=Path)
    parser.add_argument("--after", type=Path)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    if args.snapshot:
        snapshot(args.repo.resolve(), args.snapshot)
    else:
        compare(args.before, args.after, args.report)


if __name__ == "__main__":
    main()
