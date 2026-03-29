from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, cast

from layout_ast.layout import LayoutAST
from validation.assertions import check_assertions, derive_assertions
from validation.core import (
    CAMValidationResult,
)
from validation.invariants import (
    check_gcode_invariants,
    check_gcode_invariants_from_content,
    check_svg_invariants,
)
from validation.metrics import (
    GCodeMetrics,
    SVGMetrics,
    extract_svg_metrics,
)
from validation.metrics.gcode_metrics import extract_gcode_metrics_from_file
from validation.metrics.svg_metrics import extract_svg_metrics_from_file
from validation.regression import ComparisonConfig, compare_metrics


@dataclass
class ValidationInput:
    source_file: str | Path | None = None

    ast: LayoutAST | None = None

    svg_path: str | Path | None = None
    gcode_paths: list[str | Path] = field(default_factory=list)

    svg_content: str | None = None
    gcode_content: list[str] = field(default_factory=list)

    golden_metrics: dict[str, Any] | None = None
    golden_file: str | None = None

    sheet_width_mm: float | None = None
    sheet_height_mm: float | None = None
    comparison_config: ComparisonConfig | None = None


@dataclass
class ValidationOptions:
    extract_metrics: bool = True
    check_invariants: bool = True
    check_assertions: bool = True
    check_regressions: bool = True

    svg_expected_layers: list[str] | None = None

    include_all_results: bool = True


def validate(
    inputs: ValidationInput,
    options: ValidationOptions | None = None,
) -> CAMValidationResult:
    if options is None:
        options = ValidationOptions()

    start_time = time.perf_counter()

    result = CAMValidationResult(
        input_file=str(inputs.source_file) if inputs.source_file else "",
    )

    svg_metrics = None
    gcode_metrics_list: list[GCodeMetrics] = []

    if options.extract_metrics:
        svg_metrics, gcode_metrics_list = _extract_all_metrics(inputs)

        if svg_metrics:
            result.metrics.update(svg_metrics.to_dict())
        if gcode_metrics_list:
            merged_gcode = _merge_gcode_metrics(gcode_metrics_list)
            result.metrics["gcode"] = merged_gcode

    if options.check_invariants:
        _run_invariant_checks(
            result,
            inputs,
            svg_metrics,
            gcode_metrics_list,
            options,
        )

    if options.check_assertions and inputs.ast is not None:
        _run_assertion_checks(
            result,
            inputs.ast,
            svg_metrics,
            gcode_metrics_list,
        )

    if options.check_regressions and inputs.golden_metrics is not None:
        _run_regression_checks(
            result,
            inputs.golden_metrics,
            inputs.golden_file,
            inputs.comparison_config,
        )

    result.execution_time_ms = (time.perf_counter() - start_time) * 1000
    result.compute_verdict()

    return result


def validate_recipe(
    recipe_dir: str | Path,
    ast: LayoutAST | None = None,
    golden_metrics: dict[str, Any] | None = None,
    golden_file: str | None = None,
    comparison_config: ComparisonConfig | None = None,
    options: ValidationOptions | None = None,
) -> CAMValidationResult:
    recipe_dir = Path(recipe_dir)
    output_dir = recipe_dir / "output"

    source_file = None
    for candidate in ["example.pml.yml", "source.pml.yml"]:
        if (recipe_dir / candidate).exists():
            source_file = recipe_dir / candidate
            break

    svg_path = None
    gcode_paths: list[str | Path] = []

    if output_dir.exists():
        for svg_file in output_dir.glob("*.svg"):
            if not svg_file.name.startswith("."):
                svg_path = svg_file
                break

        for nc_file in sorted(output_dir.glob("*.nc")):
            if not nc_file.name.startswith("."):
                gcode_paths.append(nc_file)

    sheet_width_mm = None
    sheet_height_mm = None
    if ast is not None:
        sheet_width_mm = ast.sheet.width_mm
        sheet_height_mm = ast.sheet.height_mm

    inputs = ValidationInput(
        source_file=source_file,
        ast=ast,
        svg_path=svg_path,
        gcode_paths=gcode_paths,
        golden_metrics=golden_metrics,
        golden_file=golden_file,
        comparison_config=comparison_config,
        sheet_width_mm=sheet_width_mm,
        sheet_height_mm=sheet_height_mm,
    )

    return validate(inputs, options)


def _extract_all_metrics(
    inputs: ValidationInput,
) -> tuple[SVGMetrics | None, list[GCodeMetrics]]:
    svg_metrics = None
    gcode_metrics_list: list[GCodeMetrics] = []

    if inputs.svg_content:
        svg_metrics = extract_svg_metrics(inputs.svg_content)
    elif inputs.svg_path and Path(inputs.svg_path).exists():
        svg_metrics = extract_svg_metrics_from_file(str(inputs.svg_path))

    for gcode_path in inputs.gcode_paths:
        if Path(gcode_path).exists():
            gcode_metrics_list.append(extract_gcode_metrics_from_file(gcode_path))

    for gcode_content in inputs.gcode_content:
        from validation.metrics.gcode_metrics import extract_gcode_metrics_from_content

        gcode_metrics_list.append(extract_gcode_metrics_from_content(gcode_content))

    return svg_metrics, gcode_metrics_list


def _merge_gcode_metrics(gcode_list: list[GCodeMetrics]) -> dict[str, Any]:  # noqa: C901 — metric aggregation
    if not gcode_list:
        return {}

    if len(gcode_list) == 1:
        return cast(dict[str, Any], gcode_list[0].to_dict().get("gcode", {}))

    merged: dict[str, Any] = cast(dict[str, Any], gcode_list[0].to_dict().get("gcode", {}))

    for gcode in gcode_list[1:]:
        other = gcode.to_dict().get("gcode", {})

        if "summary" in merged and "summary" in other:
            for key in [
                "total_lines",
                "comment_lines",
                "motion_lines",
                "tool_change_lines",
                "spindle_lines",
                "feed_lines",
            ]:
                if key in merged["summary"] and key in other["summary"]:
                    merged["summary"][key] += other["summary"][key]

        if "motion" in merged and "motion" in other:
            for key in [
                "g0_count",
                "g1_count",
                "g2_count",
                "g3_count",
                "total_rapid_distance_mm",
                "total_feed_distance_mm",
            ]:
                if key in merged["motion"] and key in other["motion"]:
                    merged["motion"][key] += other["motion"][key]

        if "z_profile" in merged and "z_profile" in other:
            zp_merged = merged["z_profile"]
            zp_other = other["z_profile"]

            if "safe_z_mm" in zp_merged and "safe_z_mm" in zp_other:
                zp_merged["safe_z_mm"] = max(zp_merged["safe_z_mm"], zp_other["safe_z_mm"])
            if "max_plunge_z_mm" in zp_merged and "max_plunge_z_mm" in zp_other:
                zp_merged["max_plunge_z_mm"] = min(zp_merged["max_plunge_z_mm"], zp_other["max_plunge_z_mm"])
            if "unique_cutting_depths" in zp_merged and "unique_cutting_depths" in zp_other:
                depths = set(zp_merged["unique_cutting_depths"]) | set(zp_other["unique_cutting_depths"])
                zp_merged["unique_cutting_depths"] = sorted(depths)
                zp_merged["depth_count"] = len(depths)
            if "max_single_plunge_mm" in zp_merged and "max_single_plunge_mm" in zp_other:
                zp_merged["max_single_plunge_mm"] = max(
                    zp_merged["max_single_plunge_mm"], zp_other["max_single_plunge_mm"]
                )

        if "xy_bounds" in merged and "xy_bounds" in other:
            xy_merged = merged["xy_bounds"]
            xy_other = other["xy_bounds"]
            if "x_min" in xy_merged and "x_min" in xy_other:
                xy_merged["x_min"] = min(xy_merged["x_min"], xy_other["x_min"])
            if "x_max" in xy_merged and "x_max" in xy_other:
                xy_merged["x_max"] = max(xy_merged["x_max"], xy_other["x_max"])
            if "y_min" in xy_merged and "y_min" in xy_other:
                xy_merged["y_min"] = min(xy_merged["y_min"], xy_other["y_min"])
            if "y_max" in xy_merged and "y_max" in xy_other:
                xy_merged["y_max"] = max(xy_merged["y_max"], xy_other["y_max"])

        if "tools" in merged and "tools" in other:
            tools_merged = merged["tools"]
            tools_other = other["tools"]
            if "tool_numbers" in tools_merged and "tool_numbers" in tools_other:
                tools_merged["tool_numbers"] = sorted(
                    set(tools_merged["tool_numbers"]) | set(tools_other["tool_numbers"])
                )
            if "tool_changes" in tools_merged and "tool_changes" in tools_other:
                tools_merged["tool_changes"] += tools_other["tool_changes"]
            if "spindle_speeds" in tools_merged and "spindle_speeds" in tools_other:
                tools_merged["spindle_speeds"] = sorted(
                    set(tools_merged["spindle_speeds"]) | set(tools_other["spindle_speeds"])
                )

        if "feeds" in merged and "feeds" in other:
            feeds_merged = merged["feeds"]
            feeds_other = other["feeds"]
            if "min_feed_rate" in feeds_merged and "min_feed_rate" in feeds_other:
                feeds_merged["min_feed_rate"] = min(feeds_merged["min_feed_rate"], feeds_other["min_feed_rate"])
            if "max_feed_rate" in feeds_merged and "max_feed_rate" in feeds_other:
                feeds_merged["max_feed_rate"] = max(feeds_merged["max_feed_rate"], feeds_other["max_feed_rate"])
            if "feed_rates_used" in feeds_merged and "feed_rates_used" in feeds_other:
                feeds_merged["feed_rates_used"] = sorted(
                    set(feeds_merged["feed_rates_used"]) | set(feeds_other["feed_rates_used"])
                )

        if "time_estimate" in merged and "time_estimate" in other:
            for key in ["rapid_time_s", "feed_time_s", "total_time_s"]:
                if key in merged["time_estimate"] and key in other["time_estimate"]:
                    merged["time_estimate"][key] += other["time_estimate"][key]

        if "tabs" in merged and "tabs" in other:
            tabs_merged = merged["tabs"]
            tabs_other = other["tabs"]
            if "detected_count" in tabs_merged and "detected_count" in tabs_other:
                tabs_merged["detected_count"] += tabs_other["detected_count"]
            if "tab_heights_mm" in tabs_merged and "tab_heights_mm" in tabs_other:
                tabs_merged["tab_heights_mm"] = tabs_merged["tab_heights_mm"] + tabs_other["tab_heights_mm"]
            if "max_cutting_depth_mm" in tabs_merged and "max_cutting_depth_mm" in tabs_other:
                tabs_merged["max_cutting_depth_mm"] = min(
                    tabs_merged["max_cutting_depth_mm"], tabs_other["max_cutting_depth_mm"]
                )
        elif "tabs" in other:
            merged["tabs"] = other["tabs"]

    merged["file_count"] = len(gcode_list)

    return merged


def _run_invariant_checks(
    result: CAMValidationResult,
    inputs: ValidationInput,
    svg_metrics: SVGMetrics | None,
    gcode_metrics_list: list[GCodeMetrics],
    options: ValidationOptions,
) -> None:

    if inputs.svg_path or inputs.svg_content:
        svg_content = inputs.svg_content
        if not svg_content and inputs.svg_path:
            with open(inputs.svg_path) as f:
                svg_content = f.read()

        if svg_content:
            svg_results = check_svg_invariants(
                svg_content,
                metrics=svg_metrics,
                expected_layers=options.svg_expected_layers,
            )
            for inv_result in svg_results:
                result.invariants.add(inv_result)

    gcode_kwargs: dict[str, Any] = {}
    if inputs.sheet_width_mm is not None:
        gcode_kwargs["sheet_width_mm"] = inputs.sheet_width_mm
    if inputs.sheet_height_mm is not None:
        gcode_kwargs["sheet_height_mm"] = inputs.sheet_height_mm

    for gcode_path in inputs.gcode_paths:
        if Path(gcode_path).exists():
            gcode_results = check_gcode_invariants(gcode_path, **gcode_kwargs)
            for inv_result in gcode_results:
                result.invariants.add(inv_result)

    for gcode_content in inputs.gcode_content:
        gcode_results = check_gcode_invariants_from_content(gcode_content, **gcode_kwargs)
        for inv_result in gcode_results:
            result.invariants.add(inv_result)


def _run_assertion_checks(
    result: CAMValidationResult,
    ast: LayoutAST,
    svg_metrics: SVGMetrics | None,
    gcode_metrics_list: list[GCodeMetrics],
) -> None:

    assertions = derive_assertions(ast)

    svg_dict = svg_metrics.to_dict() if svg_metrics else None

    gcode_dict = None
    if gcode_metrics_list:
        merged = _merge_gcode_metrics(gcode_metrics_list)
        gcode_dict = {"gcode": merged}

    assertion_results = check_assertions(
        assertions,
        svg_metrics=svg_dict,
        gcode_metrics=gcode_dict,
    )

    for assertion_result in assertion_results:
        result.assertions.add(assertion_result)


def _run_regression_checks(
    result: CAMValidationResult,
    golden_metrics: dict[str, Any],
    golden_file: str | None,
    config: ComparisonConfig | None,
) -> None:
    summary = compare_metrics(
        current=result.metrics,
        golden=golden_metrics,
        config=config,
        golden_file=golden_file,
    )

    result.regressions.compared = summary.compared
    result.regressions.golden_file = summary.golden_file
    for reg_result in summary.results:
        result.regressions.add(reg_result)
