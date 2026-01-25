# cli/validate_cam.py - Command-line interface for CAM validation
#
# Validates CAM artifacts (SVG, G-code) using the validation pipeline.
# See docs/cam_validation_plan.md for architecture and schema details.

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from validation.runner import (
    ValidationInput,
    ValidationOptions,
    validate,
    validate_recipe,
)
from validation.core import Verdict
from validation.regression import ComparisonConfig


# Exit codes for CI integration
EXIT_PASS = 0
EXIT_WARN = 1
EXIT_FAIL = 2


def main() -> int:
    """Main entry point for CLI validation."""
    parser = argparse.ArgumentParser(
        description="Validate CAM artifacts (SVG, G-code)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:

  # Validate a recipe directory (auto-discovers artifacts)
  python -m cli.validate_cam --recipe docs/recipes/01_simple_profile

  # Validate specific artifacts
  python -m cli.validate_cam --svg output/drawing.svg --gcode output/toolpath.nc

  # Validate with golden baseline for regression testing
  python -m cli.validate_cam --recipe docs/recipes/01_simple_profile --golden tests/golden/01_simple_profile/metrics.json

  # Extract metrics only (no invariant checks)
  python -m cli.validate_cam --svg output/drawing.svg --metrics-only

  # Output JSON to file instead of stdout
  python -m cli.validate_cam --recipe docs/recipes/01_simple_profile --output result.json

Exit codes:
  0 = PASS (all checks passed)
  1 = WARN (warnings but no failures)
  2 = FAIL (one or more failures)
        """,
    )

    # Input modes (mutually exclusive)
    input_group = parser.add_argument_group("Input (choose one mode)")
    input_group.add_argument(
        "--recipe", "-r",
        metavar="DIR",
        help="Recipe directory with standard output/ structure",
    )
    input_group.add_argument(
        "--svg",
        metavar="FILE",
        help="SVG file to validate",
    )
    input_group.add_argument(
        "--gcode", "-g",
        metavar="FILE",
        nargs="+",
        help="G-code file(s) to validate (can specify multiple)",
    )
    input_group.add_argument(
        "--pml", "-p",
        metavar="FILE",
        help="PML source file (for intent assertions)",
    )

    # Validation options
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

    # Output options
    output_group = parser.add_argument_group("Output options")
    output_group.add_argument(
        "--output", "-o",
        metavar="FILE",
        help="Output JSON file (default: stdout)",
    )
    output_group.add_argument(
        "--quiet", "-q",
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

    # Validate inputs
    if not args.recipe and not args.svg and not args.gcode:
        parser.error("At least one input required: --recipe, --svg, or --gcode")

    try:
        return run_validation(args)
    except FileNotFoundError as e:
        if not args.quiet:
            print(f"Error: {e}", file=sys.stderr)
        return EXIT_FAIL
    except Exception as e:
        if not args.quiet:
            print(f"Error: {e}", file=sys.stderr)
            import traceback
            traceback.print_exc(file=sys.stderr)
        return EXIT_FAIL


def run_validation(args: argparse.Namespace) -> int:
    """Run validation based on parsed arguments."""
    # Load golden metrics if provided
    golden_metrics = None
    golden_file = None
    if args.golden:
        golden_path = Path(args.golden)
        if not golden_path.exists():
            raise FileNotFoundError(f"Golden file not found: {args.golden}")
        with open(golden_path) as f:
            golden_metrics = json.load(f)
        golden_file = str(golden_path)

    # Build comparison config
    comparison_config = ComparisonConfig(
        default_tolerance_percent=args.tolerance,
    )

    # Build validation options
    # --metrics-only disables all checks including regressions
    options = ValidationOptions(
        extract_metrics=True,
        check_invariants=not args.metrics_only,
        check_assertions=not args.metrics_only and not args.no_assertions,
        check_regressions=not args.metrics_only and not args.no_regressions and golden_metrics is not None,
    )

    # Parse AST if PML provided
    ast = None
    if args.pml:
        pml_path = Path(args.pml)
        if not pml_path.exists():
            raise FileNotFoundError(f"PML file not found: {args.pml}")
        from pml import parse_pml
        with open(pml_path) as f:
            ast = parse_pml(f.read())

    # Run validation
    if args.recipe:
        # Recipe mode
        recipe_dir = Path(args.recipe)
        if not recipe_dir.exists():
            raise FileNotFoundError(f"Recipe directory not found: {args.recipe}")
        if not recipe_dir.is_dir():
            raise ValueError(f"Not a directory: {args.recipe}")

        # If no AST provided, try to parse from recipe's PML
        if ast is None:
            for candidate in ["example.pml", "source.pml"]:
                pml_path = recipe_dir / candidate
                if pml_path.exists():
                    from pml import parse_pml
                    with open(pml_path) as f:
                        ast = parse_pml(f.read())
                    break

        result = validate_recipe(
            recipe_dir,
            ast=ast,
            golden_metrics=golden_metrics,
            golden_file=golden_file,
            comparison_config=comparison_config,
            options=options,
        )
    else:
        # Explicit artifact mode
        inputs = ValidationInput(
            source_file=args.pml,
            ast=ast,
            svg_path=args.svg,
            gcode_paths=args.gcode or [],
            golden_metrics=golden_metrics,
            golden_file=golden_file,
            comparison_config=comparison_config,
        )

        # Verify files exist
        if args.svg and not Path(args.svg).exists():
            raise FileNotFoundError(f"SVG file not found: {args.svg}")
        for gcode_path in (args.gcode or []):
            if not Path(gcode_path).exists():
                raise FileNotFoundError(f"G-code file not found: {gcode_path}")

        result = validate(inputs, options)

    # Output result
    if args.summary:
        output_summary(result, args)
    else:
        output_json(result, args)

    # Return exit code based on verdict
    if result.verdict == Verdict.PASS:
        return EXIT_PASS
    elif result.verdict == Verdict.WARN:
        return EXIT_WARN
    else:
        return EXIT_FAIL


def output_json(result, args: argparse.Namespace) -> None:
    """Output validation result as JSON."""
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


def output_summary(result, args: argparse.Namespace) -> None:
    """Output human-readable summary."""
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

    # Metrics summary
    if result.metrics:
        lines.append("Metrics extracted:")
        if "svg" in result.metrics:
            lines.append(f"  SVG: {result.metrics['svg'].get('layers', {}).get('count', 0)} layers")
        if "gcode" in result.metrics:
            motion = result.metrics['gcode'].get('motion', {})
            lines.append(f"  G-code: {motion.get('g0_count', 0)} rapids, {motion.get('g1_count', 0)} feeds")
        lines.append("")

    # Invariants summary
    inv = result.invariants
    if inv.total > 0:
        lines.append(f"Invariants: {inv.passed}/{inv.total} passed, {inv.warned} warnings, {inv.failed} failures")
        if inv.failed > 0:
            lines.append("  Failed:")
            for r in inv.results:
                if r.status == Verdict.FAIL:
                    lines.append(f"    - {r.id}: {r.description}")
        lines.append("")

    # Assertions summary
    asrt = result.assertions
    if asrt.total > 0:
        lines.append(f"Assertions: {asrt.passed}/{asrt.total} passed, {asrt.failed} failures")
        if asrt.failed > 0:
            lines.append("  Failed:")
            for r in asrt.results:
                if r.status == Verdict.FAIL:
                    lines.append(f"    - {r.id}: {r.message}")
        lines.append("")

    # Regressions summary
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

    # Verdict reason
    if result.verdict_reason:
        lines.append(f"Verdict: {result.verdict_reason}")

    # Output
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
