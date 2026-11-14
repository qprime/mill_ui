from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from layout_ast.layout import LayoutAST
from validation.core import Verdict
from validation.regression import ComparisonConfig
from validation.runner import (
    ValidationInput,
    ValidationOptions,
    resolve_validation_source,
    validate,
    validate_recipe,
)

EXIT_PASS = 0
EXIT_WARN = 1
EXIT_FAIL = 2


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate CAM artifacts (SVG, G-code)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:


  python -m cli.validate_cam --recipe docs/recipes/doors/shaker_door


  python -m cli.validate_cam --svg output/drawing.svg --gcode output/toolpath.nc


  python -m cli.validate_cam --recipe docs/recipes/doors/shaker_door --golden baseline.json


  python -m cli.validate_cam --svg output/drawing.svg --metrics-only


  python -m cli.validate_cam --recipe docs/recipes/doors/shaker_door --output result.json

Exit codes:
  0 = PASS (all checks passed)
  1 = WARN (warnings but no failures)
  2 = FAIL (one or more failures)
        """,
    )

    input_group = parser.add_argument_group("Input (choose one mode)")
    input_group.add_argument(
        "--recipe",
        "-r",
        metavar="DIR",
        help="Recipe directory with standard output/ structure",
    )
    input_group.add_argument(
        "--svg",
        metavar="FILE",
        help="SVG file to validate",
    )
    input_group.add_argument(
        "--gcode",
        "-g",
        metavar="FILE",
        nargs="+",
        help="G-code file(s) to validate (can specify multiple)",
    )
    input_group.add_argument(
        "--pml",
        "-p",
        metavar="FILE",
        help="PML source file (for intent assertions)",
    )

    options_group = parser.add_argument_group("Validation options")
    options_group.add_argument(
        "--golden",
        metavar="FILE",
        help="Golden metrics JSON file for regression comparison",
    )
    options_group.add_argument(
        "--tolerance",
        metavar="PERCENT",
        type=float,
        default=0.1,
        help="Default tolerance for numeric comparison (default: 0.1%%)",
    )
    options_group.add_argument(
        "--metrics-only",
        action="store_true",
        help="Extract metrics only, skip invariant/assertion checks",
    )
    options_group.add_argument(
        "--no-assertions",
        action="store_true",
        help="Skip intent assertion checks",
    )
    options_group.add_argument(
        "--no-regressions",
        action="store_true",
        help="Skip regression comparison (even if golden provided)",
    )

    output_group = parser.add_argument_group("Output options")
    output_group.add_argument(
        "--output",
        "-o",
        metavar="FILE",
        help="Output JSON file (default: stdout)",
    )
    output_group.add_argument(
        "--quiet",
        "-q",
        action="store_true",
        help="Suppress status messages, output JSON only",
    )
    output_group.add_argument(
        "--summary",
        action="store_true",
        help="Print human-readable summary instead of full JSON",
    )
    output_group.add_argument(
        "--compact",
        action="store_true",
        help="Output compact JSON (no indentation)",
    )

    args = parser.parse_args()

    if not args.recipe and not args.svg and not args.gcode:
        parser.error("At least one input required: --recipe, --svg, or --gcode")

    try:
        return run_validation(args)
    except (FileNotFoundError, ValueError) as e:
        if not args.quiet:
            print(f"Error: {e}", file=sys.stderr)
        return EXIT_FAIL
    except Exception as e:
        if not args.quiet:
            print(f"Error: {e}", file=sys.stderr)
            import traceback

            traceback.print_exc(file=sys.stderr)
        return EXIT_FAIL


def resolve_explicit_pml(pml_path: Path, artifacts: list[Path]) -> LayoutAST:
    folders = sorted({path.parent.resolve() for path in artifacts})
    matches = {}
    for folder in folders:
        metrics = folder / "metrics.json"
        if metrics.is_file():
            data = json.loads(metrics.read_text(encoding="utf-8"))
            context = data.get("build", {}).get("compilation_contexts", {}).get(pml_path.name)
            if context is not None:
                matches[folder] = context
    fingerprints = {context.get("fingerprint") for context in matches.values()}
    if len(fingerprints) > 1:
        raise ValueError("Explicit --pml artifacts have conflicting compilation contexts; validate one build at a time")
    output_dir = next(iter(matches)) if matches else folders[0] if folders else pml_path.parent
    asts = resolve_validation_source(pml_path, output_dir)
    if len(asts) != 1:
        raise ValueError(
            f"Multi-sheet --pml input resolves to {len(asts)} sheets; use --recipe to match every sheet to its artifacts"
        )
    return asts[0]


def run_validation(args: argparse.Namespace) -> int:

    golden_metrics = None
    golden_file = None
    if args.golden:
        golden_path = Path(args.golden)
        if not golden_path.exists():
            raise FileNotFoundError(f"Golden file not found: {args.golden}")
        with open(golden_path) as f:
            golden_metrics = json.load(f)
        golden_file = str(golden_path)

    comparison_config = ComparisonConfig(
        default_tolerance_percent=args.tolerance,
    )

    options = ValidationOptions(
        extract_metrics=True,
        check_invariants=not args.metrics_only,
        check_assertions=not args.metrics_only and not args.no_assertions,
        check_regressions=not args.metrics_only and not args.no_regressions and golden_metrics is not None,
    )

    ast = None
    pml_path = Path(args.pml) if args.pml else None
    if pml_path is not None and not pml_path.is_file():
        raise FileNotFoundError(f"PML file not found: {pml_path}")
    if pml_path is not None and not args.recipe:
        artifacts = [Path(path) for path in ([args.svg] if args.svg else []) + (args.gcode or [])]
        ast = resolve_explicit_pml(pml_path, artifacts)

    if args.recipe:
        recipe_dir = Path(args.recipe)
        if not recipe_dir.exists():
            raise FileNotFoundError(f"Recipe directory not found: {args.recipe}")
        if not recipe_dir.is_dir():
            raise ValueError(f"Not a directory: {args.recipe}")

        result = validate_recipe(
            recipe_dir,
            pml_source=pml_path,
            golden_metrics=golden_metrics,
            golden_file=golden_file,
            comparison_config=comparison_config,
            options=options,
        )
    else:
        inputs = ValidationInput(
            source_file=args.pml,
            ast=ast,
            sheet_width_mm=ast.sheet.width_mm if ast is not None else None,
            sheet_height_mm=ast.sheet.height_mm if ast is not None else None,
            svg_path=args.svg,
            gcode_paths=args.gcode or [],
            golden_metrics=golden_metrics,
            golden_file=golden_file,
            comparison_config=comparison_config,
        )

        if args.svg and not Path(args.svg).exists():
            raise FileNotFoundError(f"SVG file not found: {args.svg}")
        for gcode_path in args.gcode or []:
            if not Path(gcode_path).exists():
                raise FileNotFoundError(f"G-code file not found: {gcode_path}")

        result = validate(inputs, options)

    if args.summary:
        output_summary(result, args)
    else:
        output_json(result, args)

    if result.verdict == Verdict.PASS:
        return EXIT_PASS
    elif result.verdict == Verdict.WARN:
        return EXIT_WARN
    else:
        return EXIT_FAIL


def output_json(result, args: argparse.Namespace) -> None:
    result_dict = result.to_dict()
    indent = None if args.compact else 2
    json_str = json.dumps(result_dict, indent=indent, default=str)

    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json_str)
        if not args.quiet:
            print(f"Validation result written to: {args.output}", file=sys.stderr)
    else:
        print(json_str)


def output_summary(result, args: argparse.Namespace) -> None:  # noqa: C901 — summary formatter
    verdict_symbols = {
        Verdict.PASS: "PASS",
        Verdict.WARN: "WARN",
        Verdict.FAIL: "FAIL",
    }
    verdict_str = verdict_symbols.get(result.verdict, str(result.verdict))

    lines = [
        f"Validation Result: {verdict_str}",
        f"Input: {result.input_file or '(artifacts)'}",
        f"Execution time: {result.execution_time_ms:.1f}ms",
        "",
    ]

    if result.metrics:
        lines.append("Metrics extracted:")
        if "svg" in result.metrics:
            lines.append(f"  SVG: {result.metrics['svg'].get('layers', {}).get('count', 0)} layers")
        if "gcode" in result.metrics:
            motion = result.metrics["gcode"].get("motion", {})
            lines.append(f"  G-code: {motion.get('g0_count', 0)} rapids, {motion.get('g1_count', 0)} feeds")
        lines.append("")

    for index, sheet in enumerate(result.sheets, start=1):
        lines.append(
            f"Sheet {index}: {sheet.verdict.value.upper()} — {sheet.assertions.total} assertions, {sheet.invariants.total} invariants"
        )
    if result.sheets:
        lines.append("")

    inv = result.invariants
    if inv.total > 0:
        lines.append(f"Invariants: {inv.passed}/{inv.total} passed, {inv.warned} warnings, {inv.failed} failures")
        if inv.failed > 0:
            lines.append("  Failed:")
            for r in inv.results:
                if r.status == Verdict.FAIL:
                    lines.append(f"    - {r.id}: {r.description}")
        lines.append("")

    asrt = result.assertions
    if asrt.total > 0:
        lines.append(f"Assertions: {asrt.passed}/{asrt.total} passed, {asrt.failed} failures")
        if asrt.failed > 0:
            lines.append("  Failed:")
            for r in asrt.results:
                if r.status == Verdict.FAIL:
                    lines.append(f"    - {r.id}: {r.message}")
        lines.append("")

    reg = result.regressions
    if reg.compared:
        lines.append(f"Regressions: {reg.total} metrics compared")
        if reg.golden_file:
            lines.append(f"  Golden: {reg.golden_file}")
        failed_count = sum(1 for r in reg.results if r.status == Verdict.FAIL)
        warned_count = sum(1 for r in reg.results if r.status == Verdict.WARN)
        if failed_count > 0 or warned_count > 0:
            lines.append(f"  {failed_count} failures, {warned_count} warnings")
            if failed_count > 0:
                lines.append("  Failed:")
                for r in reg.results:
                    if r.status == Verdict.FAIL:
                        lines.append(f"    - {r.metric_path}: {r.message}")
        lines.append("")

    if result.verdict_reason:
        lines.append(f"Verdict: {result.verdict_reason}")

    output = "\n".join(lines)
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(output)
        if not args.quiet:
            print(f"Summary written to: {args.output}", file=sys.stderr)
    else:
        print(output)


if __name__ == "__main__":
    sys.exit(main())
