"""MCP server exposing mill_ui CAM pipeline tools."""

from __future__ import annotations

import json
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

sys.path.insert(0, str(Path(__file__).parent.parent))

from mill_mcp.config import ensure_output_dir

from pml import parse_pml, PMLParseError
from pml.compositional_parser import parse_compositional_pml
from pml.nest_parser import parse_nest_pml, nest_job_to_api_params, NestParseError
from pml.formatter import format_pml
from resolution.layout_resolver import resolve_layout
from layout_ast.layout import LayoutAST
from adapters.ast_to_cad import items_to_shape_dicts
from validation.removal_checks import check_overlap, check_depth_feasibility
from validation.runner import validate_recipe, validate, ValidationInput, ValidationOptions
from validation.regression import GoldenStore, ComparisonConfig
from nesting import nest_and_generate
from cad.export.stl import export_stl
from export.blueprint_svg import render_blueprint_svg
from cam.pipeline import run_pipeline, DEFAULT_TOOL_DB


def _sanitize_job_name(name: str) -> str:
    sanitized = re.sub(r"[^a-zA-Z0-9_-]", "_", name)
    return sanitized or "job"


def _safe_job_dir(output_dir: Path, job_name: str, timestamp: str) -> Path:
    safe_name = _sanitize_job_name(job_name)
    job_dir = output_dir / f"{safe_name}_{timestamp}"

    output_resolved = output_dir.resolve()
    job_resolved = job_dir.resolve()
    if not str(job_resolved).startswith(str(output_resolved)):
        raise ValueError(f"Job directory would escape output directory: {job_name}")

    if job_dir.exists():
        shutil.rmtree(job_dir)
    job_dir.mkdir(parents=True, exist_ok=True)
    return job_dir


MILL_UI_INSTRUCTIONS = """
You are a CAM (Computer-Aided Manufacturing) assistant for CNC router projects. You help users create panel layouts and generate G-code toolpaths.

## Your Role

Help users design and manufacture panel-based projects (cabinet doors, furniture parts, decorative panels) by:
1. Writing PML (Panel Machining Language) code for their designs
2. Compiling PML to G-code, SVG blueprints, and STL previews
3. Optimizing multi-part production with nesting

## Key Concepts

**PML** - Declarative language for single-sheet layouts. Defines shapes and machining operations.
**Nest files** - Bin-packing jobs for cutting multiple parts from stock sheets.
**Features** - What to machine: profile (cut outline), pocket (recess), hole (bore), engrave (surface)
**Generators** - Decorative patterns: wave, lines, raised_panel, hole_grid, concentric_border

## Quick Reference

**Simple rectangle with profile cut:**
```pml
sheet 450mm 650mm 19mm
rect door at 225mm,325mm size 400mm,600mm profile through outside
```

**Shaker door (frame with recessed panel):**
```pml
sheet 450mm 650mm 19mm
rect door
    profile outside through
    frame 57mm
        pocket 6mm
```

**Nesting multiple parts:**
```nest
nest maxrects
    sheet 1220mm 2440mm 19mm
    kerf 6.35mm
    parts
        door 400mm 600mm x10
            template shaker
                stile_w 57mm
                panel_recess 6mm
```

## Workflow

1. **Understand the project** - What parts? What size? What features?
2. **Write PML** - Use `validate_pml` to check before compiling
3. **Compile** - Use `compile_pml` for single sheets, `compile_nest` for production runs
4. **Review outputs** - Check the SVG blueprint and metrics

## Tools Available

- `compile_pml` - Generate G-code, SVG, STL from PML
- `compile_nest` - Optimize and compile multi-part nesting jobs
- `validate_pml` - Check PML for errors without generating files
- `list_templates` - Show available templates (shaker, etc.)
- `get_syntax_spec` - Full PML/nest language reference
- `get_docs` - Browse project documentation

## Best Practices

- Always include `mm` suffix on dimensions
- Use `validate_pml` before `compile_pml` to catch errors early
- For production runs (>1 part), use `.nest` files with `compile_nest`
- Profile cuts need `inside` or `outside` to specify tool offset direction
- `through` means cut/bore through full material thickness
""".strip()

mcp = FastMCP("mill_ui", instructions=MILL_UI_INSTRUCTIONS)


def _run_cam_pipeline(
    ast: LayoutAST,
    job_name: str,
    output_dir: Path,
    kerf_mm: float = 6.35,
) -> dict[str, Any]:
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

    pml_path = job_dir / f"{safe_name}.pml"
    pml_content = format_pml(ast)
    pml_path.write_text(pml_content)
    results["outputs"]["pml"] = str(pml_path)

    pipeline_result = run_pipeline(
        ast,
        kerf_mm=kerf_mm,
        min_channel_width_mm=12.0,
        tool_db=DEFAULT_TOOL_DB,
        generate_svg=True,
        svg_theme="dark",
        generate_stl=False,
    )

    results["intents"] = len(pipeline_result.intents)
    results["errors"].extend(pipeline_result.errors)
    results["warnings"].extend(pipeline_result.warnings)

    if pipeline_result.svg:
        svg_path = job_dir / f"{safe_name}.svg"
        svg_path.write_text(pipeline_result.svg, encoding="utf-8")
        results["outputs"]["svg"] = str(svg_path)

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

    results["passes"] = len(pipeline_result.passes)
    results["outputs"]["gcode"] = []

    total_moves = 0
    for pass_name, gcode in pipeline_result.gcode.items():
        gcode_path = job_dir / f"{safe_name}-{pass_name}.nc"
        gcode_path.write_text(gcode)

        move_count = pipeline_result.metrics["output_size"]["files"].get(pass_name, {}).get("lines", 0)
        results["outputs"]["gcode"].append({
            "pass": pass_name,
            "path": str(gcode_path),
            "moves": move_count,
        })
        total_moves += move_count

    results["total_moves"] = pipeline_result.metrics["complexity"]["total_moves"]

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
        nest_job = parse_nest_pml(nest_text)

        api_params = nest_job_to_api_params(nest_job)
        api_params["output_format"] = "ast"
        result = nest_and_generate(**api_params)

        asts = result["output"]

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        job_dir = output_dir / f"{job_name}_{timestamp}"
        if job_dir.exists():
            shutil.rmtree(job_dir)
        job_dir.mkdir(parents=True, exist_ok=True)

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

        for sheet_idx, ast in enumerate(asts):
            sheet_name = f"sheet_{sheet_idx + 1}"
            sheet_results = _run_cam_pipeline(
                ast,
                sheet_name,
                job_dir,
                kerf_mm=nest_job.kerf_mm,
            )
            results["sheets"].append(sheet_results)

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

        from adapters.ast_to_removal import ast_to_removal_intents
        intents = ast_to_removal_intents(ast)
        results["info"]["intents"] = len(intents)

        overlap_result = check_overlap(intents)
        if overlap_result.has_issues():
            results["valid"] = False
            for error in overlap_result.errors:
                results["errors"].append(error.message)
            for warning in overlap_result.warnings:
                results["warnings"].append(warning.message)

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


@mcp.tool()
def get_docs(
    name: str | None = None,
    section: str | None = None,
    list_only: bool = False,
) -> str:
    """Browse and retrieve markdown documentation from the project.

    Args:
        name: Specific .md filename without extension (e.g., "README", "CLAUDE")
        section: Folder path to scope search (e.g., "docs", "mill_mcp", "." for root)
        list_only: If True, list matching files instead of returning content

    Usage patterns:
        get_docs(list_only=True)                    - List all .md files in project
        get_docs(section="docs", list_only=True)   - List .md files in docs/ folder
        get_docs(name="README")                     - Content of README.md (searches project)
        get_docs(name="README", section="mill_mcp") - Content of mill_mcp/README.md
        get_docs(section="docs")                    - Content of all .md files in docs/
        get_docs()                                  - All .md content in entire project

    Returns JSON with either file list or file contents.
    """
    project_root = Path(__file__).parent.parent

    EXCLUDED_DIRS = {".git", ".venv", "venv", ".pytest_cache", "__pycache__", "node_modules"}
    LAZY_DIRS = {"docs/dev_docs", "docs/recipes"}

    def is_excluded(p: Path) -> bool:
        rel_parts = p.relative_to(project_root).parts[:-1]
        if any(part.startswith(".") or part in EXCLUDED_DIRS for part in rel_parts):
            return True
        rel_path = str(p.parent.relative_to(project_root))
        return any(rel_path == lazy or rel_path.startswith(lazy + "/") for lazy in LAZY_DIRS)

    def find_md_files(folder: Path, recursive: bool) -> list[Path]:
        if recursive:
            return sorted(p for p in folder.rglob("*.md") if not is_excluded(p))
        else:
            return sorted(folder.glob("*.md"))

    def relative_path(p: Path) -> str:
        return str(p.relative_to(project_root))

    try:
        if name is not None:
            target_name = name if name.endswith(".md") else f"{name}.md"
            if section is not None:
                search_dir = project_root / section
                if not search_dir.exists():
                    return json.dumps({"error": f"Section not found: {section}"})
                target_path = search_dir / target_name
                if not target_path.exists():
                    return json.dumps({"error": f"File not found: {section}/{target_name}"})
                matches = [target_path]
            else:
                matches = [p for p in project_root.rglob(target_name) if not is_excluded(p)]
                if not matches:
                    return json.dumps({"error": f"File not found: {target_name}"})

            if list_only:
                return json.dumps({
                    "files": [relative_path(m) for m in matches],
                    "total": len(matches),
                })

            contents = {}
            for m in matches:
                contents[relative_path(m)] = m.read_text()
            return json.dumps({"files": contents}, indent=2)

        if section is not None:
            search_dir = project_root / section
            if not search_dir.exists():
                return json.dumps({"error": f"Section not found: {section}"})
            matches = find_md_files(search_dir, recursive=False)

            if list_only:
                return json.dumps({
                    "section": section,
                    "files": [relative_path(m) for m in matches],
                    "total": len(matches),
                })

            contents = {}
            for m in matches:
                contents[relative_path(m)] = m.read_text()
            return json.dumps({"files": contents}, indent=2)

        matches = find_md_files(project_root, recursive=True)

        if list_only:
            sections: dict[str, list[str]] = {}
            for m in matches:
                rel = relative_path(m)
                folder = str(m.parent.relative_to(project_root))
                if folder == ".":
                    folder = "."
                if folder not in sections:
                    sections[folder] = []
                sections[folder].append(rel)
            return json.dumps({
                "sections": sections,
                "total": len(matches),
            }, indent=2)

        contents = {}
        for m in matches:
            contents[relative_path(m)] = m.read_text()
        return json.dumps({"files": contents}, indent=2)

    except Exception as e:
        return json.dumps({"error": str(e)})


@mcp.tool()
def validate_cam_recipe(
    recipe_path: str,
    golden_path: str | None = None,
    check_invariants: bool = True,
    check_assertions: bool = True,
    tolerance_percent: float = 0.1,
) -> str:
    """Validate CAM artifacts (SVG, STL, G-code) for a recipe directory.

    Args:
        recipe_path: Path to recipe directory with output/ subdirectory
        golden_path: Optional path to golden baseline metrics.json for regression
        check_invariants: Run structural invariant checks (default: True)
        check_assertions: Run intent assertions from PML (default: True)
        tolerance_percent: Default tolerance for numeric comparison (default: 0.1%)

    Returns JSON with:
        - verdict: "pass", "warn", or "fail"
        - metrics: Extracted metrics from SVG, STL, G-code
        - invariants: Structural check results
        - assertions: Intent assertion results (if PML present)
        - regressions: Golden baseline comparison (if golden_path provided)
    """
    try:
        recipe_dir = Path(recipe_path)
        if not recipe_dir.exists():
            return json.dumps({"error": f"Recipe directory not found: {recipe_path}"})
        if not recipe_dir.is_dir():
            return json.dumps({"error": f"Not a directory: {recipe_path}"})

        golden_metrics = None
        golden_file = None
        if golden_path:
            golden_path_obj = Path(golden_path)
            if not golden_path_obj.exists():
                return json.dumps({"error": f"Golden file not found: {golden_path}"})
            with open(golden_path_obj) as f:
                golden_metrics = json.load(f)
            golden_file = str(golden_path_obj)

        ast = None
        if check_assertions:
            for pml_name in ["example.pml", "source.pml"]:
                pml_path = recipe_dir / pml_name
                if pml_path.exists():
                    try:
                        from pml import parse_pml
                        pml_content = pml_path.read_text()
                        ast = parse_pml(pml_content)
                    except Exception:
                        pass
                    break

        options = ValidationOptions(
            extract_metrics=True,
            check_invariants=check_invariants,
            check_assertions=check_assertions and ast is not None,
            check_regressions=golden_metrics is not None,
        )

        comparison_config = ComparisonConfig(
            default_tolerance_percent=tolerance_percent,
        )

        result = validate_recipe(
            recipe_dir,
            ast=ast,
            golden_metrics=golden_metrics,
            golden_file=golden_file,
            comparison_config=comparison_config,
            options=options,
        )

        full_result = result.to_dict()
        return json.dumps(full_result.get("validation_result", full_result), indent=2, default=str)

    except Exception as e:
        return json.dumps({"error": str(e)})


@mcp.tool()
def validate_cam_artifacts(
    svg_path: str | None = None,
    stl_path: str | None = None,
    gcode_paths: list[str] | None = None,
    check_invariants: bool = True,
) -> str:
    """Validate specific CAM artifacts (SVG, STL, G-code files).

    Args:
        svg_path: Optional path to SVG file
        stl_path: Optional path to STL file
        gcode_paths: Optional list of G-code file paths
        check_invariants: Run structural invariant checks (default: True)

    Returns JSON with:
        - verdict: "pass", "warn", or "fail"
        - metrics: Extracted metrics from provided artifacts
        - invariants: Structural check results
    """
    try:
        if not svg_path and not stl_path and not gcode_paths:
            return json.dumps({"error": "At least one artifact path required"})

        if svg_path and not Path(svg_path).exists():
            return json.dumps({"error": f"SVG file not found: {svg_path}"})
        if stl_path and not Path(stl_path).exists():
            return json.dumps({"error": f"STL file not found: {stl_path}"})
        for gcode_path in (gcode_paths or []):
            if not Path(gcode_path).exists():
                return json.dumps({"error": f"G-code file not found: {gcode_path}"})

        inputs = ValidationInput(
            svg_path=svg_path,
            stl_path=stl_path,
            gcode_paths=gcode_paths or [],
        )

        options = ValidationOptions(
            extract_metrics=True,
            check_invariants=check_invariants,
            check_assertions=False,
            check_regressions=False,
        )

        result = validate(inputs, options)

        full_result = result.to_dict()
        return json.dumps(full_result.get("validation_result", full_result), indent=2, default=str)

    except Exception as e:
        return json.dumps({"error": str(e)})


@mcp.tool()
def list_golden_baselines(store_path: str = "tests/golden") -> str:
    """List available golden baselines for regression testing.

    Args:
        store_path: Path to golden store directory (default: tests/golden)

    Returns JSON with:
        - baselines: List of available baseline names
        - total: Total count
        - store_path: Path to the golden store
    """
    try:
        store = GoldenStore(store_path)
        if not store.exists():
            return json.dumps({
                "baselines": [],
                "total": 0,
                "store_path": store_path,
                "message": "Golden store not found",
            })

        entries = store.list_entries()
        index = store.load_index()

        baselines = []
        for name in sorted(entries):
            entry = index.entries.get(name)
            baselines.append({
                "name": name,
                "source_file": entry.source_file if entry else None,
                "updated_at": entry.updated_at if entry else None,
                "metrics_path": str(store.get_metrics_path(name)),
            })

        return json.dumps({
            "baselines": baselines,
            "total": len(baselines),
            "store_path": store_path,
        }, indent=2)

    except Exception as e:
        return json.dumps({"error": str(e)})


@mcp.tool()
def get_golden_metrics(recipe_name: str, store_path: str = "tests/golden") -> str:
    """Get golden baseline metrics for a specific recipe.

    Args:
        recipe_name: Name of the recipe (e.g., "01_simple_profile")
        store_path: Path to golden store directory (default: tests/golden)

    Returns JSON with the golden metrics for the recipe.
    """
    try:
        store = GoldenStore(store_path)
        if not store.exists():
            return json.dumps({"error": f"Golden store not found: {store_path}"})

        if not store.has_entry(recipe_name):
            return json.dumps({"error": f"No golden baseline for: {recipe_name}"})

        metrics = store.load_metrics(recipe_name)
        if metrics is None:
            return json.dumps({"error": f"Failed to load metrics for: {recipe_name}"})

        return json.dumps(metrics, indent=2, default=str)

    except Exception as e:
        return json.dumps({"error": str(e)})


def main():
    mcp.run()


if __name__ == "__main__":
    main()
