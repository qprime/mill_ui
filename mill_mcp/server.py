"""MCP server exposing mill_ui CAM pipeline tools."""

from __future__ import annotations

import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from mill_mcp.config import ensure_output_dir

# Pipeline imports
from pml import parse_pml, PMLParseError
from pml.compositional_parser import parse_compositional_pml
from pml.nest_parser import parse_nest_pml, nest_job_to_api_params, NestParseError
from pml.formatter import format_pml
from resolution.layout_resolver import resolve_layout
from layout_ast.layout import LayoutAST
from adapters.ast_to_removal import ast_to_removal_intents
from adapters.removal_to_planner import removal_intents_to_v1_hints
from adapters.ast_to_cad import items_to_shape_dicts
from validation.removal_checks import check_overlap, check_depth_feasibility
from nesting import nest_and_generate
from cam.config import Config
from cam.model.stock import Stock
from cam.model.material import Material
from cam.model.machine import Machine
from cam.planner.passes import plan_passes
from cam.post.gcode import write_gcode
from cad.export.stl import export_stl
from export.blueprint_svg import render_blueprint_svg


def _sanitize_job_name(name: str) -> str:
    """Sanitize job name to prevent path traversal.

    Only allows alphanumeric, underscore, and hyphen characters.
    """
    sanitized = re.sub(r"[^a-zA-Z0-9_-]", "_", name)
    # Ensure non-empty
    return sanitized or "job"


def _safe_job_dir(output_dir: Path, job_name: str, timestamp: str) -> Path:
    """Create job directory, ensuring it stays under output_dir."""
    safe_name = _sanitize_job_name(job_name)
    job_dir = output_dir / f"{safe_name}_{timestamp}"

    # Verify resolved path is under output_dir
    output_resolved = output_dir.resolve()
    job_resolved = job_dir.resolve()
    if not str(job_resolved).startswith(str(output_resolved)):
        raise ValueError(f"Job directory would escape output directory: {job_name}")

    job_dir.mkdir(parents=True, exist_ok=True)
    return job_dir


# Create the MCP server
mcp = FastMCP("mill_ui")


# Default tool database
DEFAULT_TOOL_DB = [
    {
        "name": "1_4_endmill",
        "diameter": 6.35,
        "kind": "flat",
        "rpm": 12000,
        "feed_xy": 800,
        "feed_z": 280,
    },
    {
        "name": "1_8_endmill",
        "diameter": 3.175,
        "kind": "flat",
        "rpm": 14000,
        "feed_xy": 900,
        "feed_z": 300,
    },
]


def _run_cam_pipeline(
    ast: LayoutAST,
    job_name: str,
    output_dir: Path,
    kerf_mm: float = 6.35,
) -> dict[str, Any]:
    """Run the full CAM pipeline on a LayoutAST.

    Returns dict with output paths and metrics.
    """
    # Create job subdirectory with timestamp (sanitized)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_name = _sanitize_job_name(job_name)
    job_dir = _safe_job_dir(output_dir, job_name, timestamp)

    results: dict[str, Any] = {
        "job_name": job_name,
        "job_dir": str(job_dir),
        "timestamp": timestamp,
        "sheet": {
            "width_mm": ast.sheet.width_mm,
            "height_mm": ast.sheet.height_mm,
            "thickness_mm": ast.sheet.thickness_mm,
        },
        "items": len(ast.items),
        "outputs": {},
        "errors": [],
        "warnings": [],
    }

    # Save PML record
    pml_path = job_dir / f"{safe_name}.pml"
    pml_content = format_pml(ast)
    pml_path.write_text(pml_content)
    results["outputs"]["pml"] = str(pml_path)

    # Convert to RemovalIntent IR
    intents = ast_to_removal_intents(ast)
    results["intents"] = len(intents)

    # Run validation
    overlap_result = check_overlap(intents)
    if overlap_result.has_issues():
        for error in overlap_result.errors:
            results["errors"].append(error.message)
        for warning in overlap_result.warnings:
            results["warnings"].append(warning.message)

    for intent in intents:
        depth_result = check_depth_feasibility(intent, ast.sheet.thickness_mm)
        if depth_result.has_issues():
            for error in depth_result.errors:
                results["errors"].append(error.message)
            for warning in depth_result.warnings:
                results["warnings"].append(warning.message)

    # Generate SVG blueprint
    try:
        svg_string = render_blueprint_svg(ast, intents, theme="dark")
        svg_path = job_dir / f"{safe_name}.svg"
        svg_path.write_text(svg_string, encoding="utf-8")
        results["outputs"]["svg"] = str(svg_path)
    except Exception as e:
        results["warnings"].append(f"SVG generation failed: {e}")

    # Generate STL
    try:
        shapes = items_to_shape_dicts(ast.items)
        stl_path = job_dir / f"{safe_name}.stl"
        export_stl(
            shapes=shapes,
            sheet_thickness_mm=ast.sheet.thickness_mm,
            output_path=stl_path,
            kerf_mm=kerf_mm,
            quality="medium",
            include_floating_parts=True,
        )
        results["outputs"]["stl"] = str(stl_path)
    except Exception as e:
        results["warnings"].append(f"STL generation failed: {e}")

    # Convert to planner hints
    hints = removal_intents_to_v1_hints(
        intents,
        kerf_width_mm=kerf_mm,
        min_channel_width_mm=12.0,
    )

    # Setup CAM models
    stock = Stock(
        width=ast.sheet.width_mm,
        height=ast.sheet.height_mm,
        thickness=ast.sheet.thickness_mm,
    )
    material = Material(name="MDF")
    machine = Machine(name="default_grbl")

    # Plan passes
    passes, summary = plan_passes(
        hints,
        config=Config(),
        tool_db=DEFAULT_TOOL_DB,
        material=material,
        machine=machine,
        stock=stock,
        safe_z=6.0,
    )

    results["passes"] = len(passes)
    results["outputs"]["gcode"] = []

    # Generate G-code for each pass
    total_moves = 0
    for pass_dict in passes:
        gcode = write_gcode(
            pass_dict["moves"],
            safe_z=pass_dict["setup"].safe_z,
        )

        tool_diameter = pass_dict["setup"].tool.diameter
        pass_name = f"{pass_dict['op']}-{tool_diameter:.2f}mm"
        gcode_path = job_dir / f"{safe_name}-{pass_name}.nc"
        gcode_path.write_text(gcode)

        results["outputs"]["gcode"].append({
            "pass": pass_name,
            "path": str(gcode_path),
            "moves": len(pass_dict["moves"]),
        })
        total_moves += len(pass_dict["moves"])

    results["total_moves"] = total_moves

    # Save metrics
    metrics_path = job_dir / "metrics.json"
    metrics_path.write_text(json.dumps(results, indent=2))

    return results


@mcp.tool()
def compile_pml(pml_text: str, job_name: str = "job", compositional: bool = False) -> str:
    """Compile PML to G-code, SVG blueprint, and STL.

    Args:
        pml_text: Valid PML source text
        job_name: Name for output files (default: "job")
        compositional: If True, parse as compositional PML (frame/inset/grid syntax)

    Returns JSON with output paths for gcode, svg, stl files, and job metrics.
    """
    output_dir = ensure_output_dir()

    try:
        # Parse PML
        if compositional:
            comp_ast = parse_compositional_pml(pml_text)
            ast = resolve_layout(comp_ast)
        else:
            # Try flat first, fall back to compositional
            try:
                ast = parse_pml(pml_text)
            except PMLParseError:
                # Check if it looks compositional
                if any(kw in pml_text for kw in ["component", "frame", "inset", "grid", "split"]):
                    comp_ast = parse_compositional_pml(pml_text)
                    ast = resolve_layout(comp_ast)
                else:
                    raise

        # Run pipeline
        results = _run_cam_pipeline(ast, job_name, output_dir)
        return json.dumps(results, indent=2)

    except PMLParseError as e:
        return json.dumps({"error": f"PML parse error: {e}", "success": False})
    except Exception as e:
        return json.dumps({"error": str(e), "success": False})


@mcp.tool()
def compile_nest(nest_text: str, job_name: str = "job") -> str:
    """Compile .nest file to multi-sheet G-code, SVG, and STL.

    Args:
        nest_text: Valid .nest source text defining parts and nesting parameters
        job_name: Base name for output files (default: "job")

    Returns JSON with output paths per sheet, nesting metrics, and job summary.
    """
    output_dir = ensure_output_dir()

    try:
        # Parse nest file
        nest_job = parse_nest_pml(nest_text)

        # Run nesting
        api_params = nest_job_to_api_params(nest_job)
        api_params["output_format"] = "ast"
        result = nest_and_generate(**api_params)

        asts = result["output"]

        # Create job directory
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        job_dir = output_dir / f"{job_name}_{timestamp}"
        job_dir.mkdir(parents=True, exist_ok=True)

        # Results structure
        results: dict[str, Any] = {
            "job_name": job_name,
            "job_dir": str(job_dir),
            "timestamp": timestamp,
            "nesting": {
                "algorithm": nest_job.algorithm,
                "total_sheets": result["total_sheets"],
                "utilization": result["utilization"],
                "utilization_percent": f"{result['utilization'] * 100:.1f}%",
            },
            "sheets": [],
            "errors": [],
            "warnings": [],
        }

        # Process each sheet
        for sheet_idx, ast in enumerate(asts):
            sheet_name = f"sheet_{sheet_idx + 1}"
            sheet_results = _run_cam_pipeline(
                ast,
                sheet_name,
                job_dir,
                kerf_mm=nest_job.kerf_mm,
            )
            results["sheets"].append(sheet_results)

        # Save overall metrics
        metrics_path = job_dir / "job_metrics.json"
        metrics_path.write_text(json.dumps(results, indent=2))

        return json.dumps(results, indent=2)

    except NestParseError as e:
        return json.dumps({"error": f"Nest parse error: {e}", "success": False})
    except Exception as e:
        return json.dumps({"error": str(e), "success": False})


@mcp.tool()
def list_templates() -> str:
    """List available templates and their parameters.

    Returns JSON with template names and their required/optional parameters.
    """
    templates = {
        "Shaker": {
            "description": "Shaker-style cabinet door with frame and recessed panel",
            "required_params": {
                "outer_w": "Overall door width in mm",
                "outer_h": "Overall door height in mm",
                "stile_w": "Stile (vertical frame) width in mm",
                "rail_h": "Rail (horizontal frame) height in mm",
                "panel_recess": "Panel pocket depth in mm",
            },
            "optional_params": {
                "anchor_recess": {
                    "description": "Corner anchor holes for mounting",
                    "sub_params": {
                        "enabled": "Boolean to enable anchor holes",
                        "diameter_mm": "Hole diameter in mm",
                        "extra_depth_mm": "Additional depth beyond panel recess",
                        "offsets_mm": {
                            "left": "Distance from left edge",
                            "right": "Distance from right edge",
                            "top": "Distance from top edge",
                            "bottom": "Distance from bottom edge",
                        },
                    },
                },
            },
            "example": {
                "outer_w": 400.0,
                "outer_h": 600.0,
                "stile_w": 50.0,
                "rail_h": 50.0,
                "panel_recess": 6.0,
            },
        },
    }

    return json.dumps(templates, indent=2)


@mcp.tool()
def validate_pml(pml_text: str, compositional: bool = False) -> str:
    """Validate PML without generating outputs.

    Args:
        pml_text: PML source text to validate
        compositional: If True, parse as compositional PML

    Returns JSON with validation results (errors, warnings, parsed structure info).
    """
    results: dict[str, Any] = {
        "valid": True,
        "errors": [],
        "warnings": [],
        "info": {},
    }

    try:
        # Parse PML
        if compositional:
            comp_ast = parse_compositional_pml(pml_text)
            ast = resolve_layout(comp_ast)
        else:
            try:
                ast = parse_pml(pml_text)
            except PMLParseError:
                if any(kw in pml_text for kw in ["component", "frame", "inset", "grid", "split"]):
                    comp_ast = parse_compositional_pml(pml_text)
                    ast = resolve_layout(comp_ast)
                else:
                    raise

        results["info"] = {
            "sheet": {
                "width_mm": ast.sheet.width_mm,
                "height_mm": ast.sheet.height_mm,
                "thickness_mm": ast.sheet.thickness_mm,
            },
            "items": len(ast.items),
            "item_types": [item.type for item in ast.items],
            "feature_types": [item.feature.type if item.feature else None for item in ast.items],
        }

        # Validate via IR
        intents = ast_to_removal_intents(ast)
        results["info"]["intents"] = len(intents)

        # Check overlaps
        overlap_result = check_overlap(intents)
        if overlap_result.has_issues():
            results["valid"] = False
            for error in overlap_result.errors:
                results["errors"].append(error.message)
            for warning in overlap_result.warnings:
                results["warnings"].append(warning.message)

        # Check depth feasibility
        for intent in intents:
            depth_result = check_depth_feasibility(intent, ast.sheet.thickness_mm)
            if depth_result.has_issues():
                for error in depth_result.errors:
                    results["errors"].append(error.message)
                    results["valid"] = False
                for warning in depth_result.warnings:
                    results["warnings"].append(warning.message)

    except PMLParseError as e:
        results["valid"] = False
        results["errors"].append(f"Parse error: {e}")
    except Exception as e:
        results["valid"] = False
        results["errors"].append(f"Validation error: {e}")

    return json.dumps(results, indent=2)


@mcp.tool()
def get_syntax_spec(format: str = "all") -> str:
    """Get PML or .nest syntax specification.

    Args:
        format: "pml", "nest", or "all" (default: "all")

    Returns the syntax specification as markdown text.
    """
    spec_dir = Path(__file__).parent.parent / "pml"

    result_parts = []

    if format in ("pml", "all"):
        pml_spec_path = spec_dir / "syntax_spec.md"
        if pml_spec_path.exists():
            result_parts.append(pml_spec_path.read_text())
        else:
            result_parts.append("# PML Syntax Spec\n\nSpec file not found.")

    if format in ("nest", "all"):
        nest_spec_path = spec_dir / "nest_syntax_spec.md"
        if nest_spec_path.exists():
            if result_parts:
                result_parts.append("\n\n---\n\n")
            result_parts.append(nest_spec_path.read_text())
        else:
            result_parts.append("# Nest Syntax Spec\n\nSpec file not found.")

    if not result_parts:
        return f"Unknown format: {format}. Use 'pml', 'nest', or 'all'."

    return "".join(result_parts)


def main():
    """Run the MCP server."""
    mcp.run()


if __name__ == "__main__":
    main()
