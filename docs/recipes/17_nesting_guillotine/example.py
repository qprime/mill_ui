#!/usr/bin/env python3

from __future__ import annotations

import json
import time
from pathlib import Path

from adapters.ast_to_removal import ast_to_removal_intents
from adapters.removal_to_planner import removal_intents_to_planner_input
from cam.config import Config
from cam.model.machine import Machine
from cam.model.stock import Stock
from cam.planner.passes import plan_passes
from cam.post.gcode import write_gcode
from nesting import nest_and_generate, nest_parts
from pml.lifter import lift_layout_ast
from pml.nest_parser import nest_job_to_api_params
from pml.yaml_formatter import format_pml_yaml
from pml.yaml_parser import parse_nest_yaml

try:
    from export.blueprint_svg import render_blueprint_svg

    SVG_AVAILABLE = True
except (ImportError, ModuleNotFoundError):
    SVG_AVAILABLE = False


TOOL_DB = [
    {
        "name": "1_4_endmill",
        "diameter": 6.35,
        "kind": "flat",
        "rpm": 12000,
        "feed_xy": 800,
        "feed_z": 280,
    },
]


def main():
    recipe_dir = Path(__file__).parent
    output_dir = recipe_dir / "output"
    output_dir.mkdir(exist_ok=True)

    print("=" * 60)
    print("Recipe 17: Nesting with Guillotine Algorithm")
    print("=" * 60)

    nest_pml_path = recipe_dir / "cabinet_job.nest.yml"
    print(f"\nReading {nest_pml_path.name}...")

    source = nest_pml_path.read_text()
    job = parse_nest_yaml(source)

    print("\nJob specification:")
    print(f"  Algorithm: {job.algorithm}")
    print(f"  Sheet: {job.sheet_width_mm}mm x {job.sheet_height_mm}mm x {job.sheet_thickness_mm}mm")
    print(f"  Kerf: {job.kerf_mm}mm, Margin: {job.margin_mm}mm")

    print("\nParts to nest:")
    for part in job.parts:
        template_info = f" (template: {part.template})" if part.template else ""
        print(f"  - {part.quantity}x {part.name}: {part.width_mm}mm x {part.height_mm}mm{template_info}")

    print("\n--- Nesting ---")
    nest_start = time.perf_counter()

    api_params = nest_job_to_api_params(job)
    api_params["output_format"] = "ast"

    result = nest_and_generate(**api_params)

    nest_time = time.perf_counter() - nest_start

    print(f"  Total sheets: {result['total_sheets']}")
    print(f"  Utilization: {result['utilization'] * 100:.1f}%")
    print(f"  Nesting time: {nest_time * 1000:.1f}ms")

    validation_params = nest_job_to_api_params(job)
    validation_params["validate"] = True
    validation_result = nest_parts(**validation_params)

    validation = validation_result["validation"]
    if validation["is_valid"]:
        print("  Validation: PASSED")
    else:
        print("  Validation: FAILED")
        for error in validation["errors"]:
            print(f"    ERROR: {error['message']}")

    for warning in validation["warnings"]:
        print(f"    WARNING: {warning['message']}")

    print("\n--- Generated PML Layouts ---")
    asts = result["output"]

    for sheet_idx, ast in enumerate(asts):
        sheet_name = f"sheet_{sheet_idx + 1}"
        pml_path = output_dir / f"{sheet_name}.pml.yml"

        pml_content = format_pml_yaml(lift_layout_ast(ast))

        header = f"# {sheet_name}.pml.yml\n"
        header += "# Generated from cabinet_job.nest.yml\n"
        header += f"# Algorithm: {job.algorithm}\n"
        header += f"# Items: {len(ast.items)}\n"
        header += "\n"

        pml_path.write_text(header + pml_content)
        print(f"  {pml_path.name}: {len(ast.items)} items")

    print("\n--- CAM Processing ---")

    metrics = {
        "source": "cabinet_job.nest.yml",
        "algorithm": job.algorithm,
        "nesting": {
            "total_sheets": result["total_sheets"],
            "utilization": result["utilization"],
            "utilization_percent": f"{result['utilization'] * 100:.1f}%",
            "nesting_time_ms": round(nest_time * 1000, 2),
        },
        "sheets": [],
    }

    for sheet_idx, ast in enumerate(asts):
        sheet_name = f"sheet_{sheet_idx + 1}"
        print(f"\n  Processing {sheet_name}...")

        ir_start = time.perf_counter()
        intents = ast_to_removal_intents(ast)
        ir_time = time.perf_counter() - ir_start

        hints_start = time.perf_counter()
        planner_input = removal_intents_to_planner_input(intents, kerf_width_mm=job.kerf_mm, min_channel_width_mm=12.0)
        hints_time = time.perf_counter() - hints_start

        stock = Stock(
            width=ast.sheet.width_mm,
            height=ast.sheet.height_mm,
            thickness=ast.sheet.thickness_mm,
        )
        machine = Machine(name="default_grbl")

        plan_start = time.perf_counter()
        passes, _ = plan_passes(
            planner_input,
            config=Config(),
            tool_db=TOOL_DB,
            machine=machine,
            stock=stock,
            safe_z=6.0,
        )
        plan_time = time.perf_counter() - plan_start

        gcode_start = time.perf_counter()
        sheet_gcode_files = {}
        total_moves = 0

        for p in passes:
            gcode = write_gcode(
                p.moves,
                safe_z=p.setup.safe_z,
            )

            tool_diameter = p.setup.tool.diameter
            pass_name = f"{p.op}-{tool_diameter:.2f}mm"
            sheet_gcode_files[pass_name] = gcode
            total_moves += len(p.moves)

            gcode_path = output_dir / f"{sheet_name}-{pass_name}.nc"
            with open(gcode_path, "w") as f:
                f.write(gcode)

        gcode_time = time.perf_counter() - gcode_start

        print(f"    Items: {len(ast.items)}")
        print(f"    Intents: {len(intents)}")
        print(f"    Passes: {len(passes)}")
        print(f"    Moves: {total_moves}")

        if SVG_AVAILABLE:
            try:
                svg_string = render_blueprint_svg(ast, theme="dark")
                svg_path = output_dir / f"{sheet_name}.svg"
                with open(svg_path, "w", encoding="utf-8") as f:
                    f.write(svg_string)
                print(f"    SVG: {svg_path.name}")
            except Exception as e:
                print(f"    SVG: failed ({e})")

        sheet_metrics = {
            "name": sheet_name,
            "pml_file": f"{sheet_name}.pml.yml",
            "items": len(ast.items),
            "intents": len(intents),
            "passes": len(passes),
            "moves": total_moves,
            "timing_ms": {
                "ir": round(ir_time * 1000, 2),
                "hints": round(hints_time * 1000, 2),
                "plan": round(plan_time * 1000, 2),
                "gcode": round(gcode_time * 1000, 2),
            },
            "gcode_files": list(sheet_gcode_files.keys()),
        }
        metrics["sheets"].append(sheet_metrics)

    metrics_path = output_dir / "metrics.json"
    with open(metrics_path, "w") as f:
        json.dump(metrics, f, indent=2)

    print("\n--- Output ---")
    print(f"  Directory: {output_dir}")
    print(f"  PML files: {result['total_sheets']}")
    print(f"  G-code files: {sum(len(s['gcode_files']) for s in metrics['sheets'])}")
    print("  Metrics: metrics.json")

    print("\nDone!")


if __name__ == "__main__":
    main()
