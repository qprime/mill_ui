#!/usr/bin/env python3

from adapters.ast_to_removal import ast_to_removal_intents
from adapters.removal_to_planner import removal_intents_to_planner_input
from cam.config import Config
from cam.model.machine import Machine
from cam.model.stock import Stock
from cam.planner.passes import plan_passes
from cam.planner.passes.tools import normalize_tool_entries
from layout_ast.layout import Feature, Geometry, Item, LayoutAST, Placement, Sheet


def test_corner_cleanup_basic():

    ast = LayoutAST(
        sheet=Sheet(width_mm=200, height_mm=150, thickness_mm=19, margin_mm=0.0),
        items=(
            Item(
                kind="shape",
                type="Rect",
                geometry=Geometry(data={"w_mm": 100, "h_mm": 80}),
                placement=Placement(center_xy_mm=(100, 75)),
                feature=Feature(type="pocket", depth_mm=6.0, corner_cleanup_tool_diameter_mm=3.175),
                shape_id="panel",
            ),
        ),
    )

    intents = ast_to_removal_intents(ast)
    assert len(intents) == 1
    assert intents[0].corner_cleanup_tool_diameter_mm == 3.175

    planner_input = removal_intents_to_planner_input(intents, kerf_width_mm=3.175, min_channel_width_mm=6.0)
    assert len(planner_input.corner_cleanups) == 1

    corner_cleanup = planner_input.corner_cleanups[0]
    assert corner_cleanup.corner_tool_diameter_mm == 3.175
    assert len(corner_cleanup.corners) == 4

    corners = corner_cleanup.corners

    assert (50.0, 35.0) in corners
    assert (150.0, 35.0) in corners
    assert (150.0, 115.0) in corners
    assert (50.0, 115.0) in corners


def test_corner_cleanup_planner():
    ast = LayoutAST(
        sheet=Sheet(width_mm=200, height_mm=150, thickness_mm=19, margin_mm=0.0),
        items=(
            Item(
                kind="shape",
                type="Rect",
                geometry=Geometry(data={"w_mm": 100, "h_mm": 80}),
                placement=Placement(center_xy_mm=(100, 75)),
                feature=Feature(type="pocket", depth_mm=6.0, corner_cleanup_tool_diameter_mm=3.175),
                shape_id="panel",
            ),
        ),
    )

    intents = ast_to_removal_intents(ast)
    planner_input = removal_intents_to_planner_input(intents, kerf_width_mm=3.175, min_channel_width_mm=6.0)

    tool_db = [
        {"name": "1/8_endmill", "diameter": 3.175, "kind": "flat", "rpm": 14000, "feed_xy": 900, "feed_z": 300},
        {"name": "3/8_endmill", "diameter": 9.525, "kind": "flat", "rpm": 12000, "feed_xy": 1200, "feed_z": 400},
    ]

    config = Config(safe_z_mm=6.0)
    machine = Machine()
    stock = Stock(width=200, height=150, thickness=19)

    passes, *_ = plan_passes(
        planner_input,
        config=config,
        tool_db=normalize_tool_entries(tool_db),
        machine=machine,
        stock=stock,
    )

    assert len(passes) == 2

    pocket_pass = None
    corner_pass = None
    for p in passes:
        if p.op == "pocket":
            pocket_pass = p
        elif p.op == "corner_cleanup":
            corner_pass = p

    assert pocket_pass is not None, "Missing pocket pass"
    assert corner_pass is not None, "Missing corner_cleanup pass"

    pocket_tool_diameter = pocket_pass.tool_selection.diameter

    assert pocket_tool_diameter in [3.175, 9.525]

    corner_tool_diameter = corner_pass.tool_selection.diameter
    assert corner_tool_diameter == 3.175

    assert len(pocket_pass.moves) > 0
    assert len(corner_pass.moves) > 0


def test_corner_cleanup_tool_not_found():
    ast = LayoutAST(
        sheet=Sheet(width_mm=200, height_mm=150, thickness_mm=19, margin_mm=0.0),
        items=(
            Item(
                kind="shape",
                type="Rect",
                geometry=Geometry(data={"w_mm": 100, "h_mm": 80}),
                placement=Placement(center_xy_mm=(100, 75)),
                feature=Feature(type="pocket", depth_mm=6.0, corner_cleanup_tool_diameter_mm=2.0),
                shape_id="panel",
            ),
        ),
    )

    intents = ast_to_removal_intents(ast)
    planner_input = removal_intents_to_planner_input(intents)

    tool_db = [
        {"name": "3/8_endmill", "diameter": 9.525, "kind": "flat", "rpm": 12000, "feed_xy": 1200, "feed_z": 400},
    ]

    config = Config()
    machine = Machine()
    stock = Stock(width=200, height=150, thickness=19)

    try:
        _passes, *_ = plan_passes(
            planner_input,
            config=config,
            tool_db=normalize_tool_entries(tool_db),
            machine=machine,
            stock=stock,
        )
        raise AssertionError("Expected ValueError for missing tool")
    except ValueError as e:
        assert "2.0mm not found in tool_db" in str(e)


def test_corner_cleanup_non_rect_error():
    ast = LayoutAST(
        sheet=Sheet(width_mm=200, height_mm=150, thickness_mm=19, margin_mm=0.0),
        items=(
            Item(
                kind="shape",
                type="Circle",
                geometry=Geometry(data={"diameter_mm": 80}),
                placement=Placement(center_xy_mm=(100, 75)),
                feature=Feature(type="pocket", depth_mm=6.0, corner_cleanup_tool_diameter_mm=3.175),
                shape_id="round_pocket",
            ),
        ),
    )

    intents = ast_to_removal_intents(ast)
    warnings: list[str] = []
    planner_input = removal_intents_to_planner_input(intents, warnings=warnings)
    assert len(planner_input.corner_cleanups) == 0
    assert any("only supported for rectangular pockets" in w.lower() for w in warnings)


def test_corner_cleanup_without_flag():
    ast = LayoutAST(
        sheet=Sheet(width_mm=200, height_mm=150, thickness_mm=19, margin_mm=0.0),
        items=(
            Item(
                kind="shape",
                type="Rect",
                geometry=Geometry(data={"w_mm": 100, "h_mm": 80}),
                placement=Placement(center_xy_mm=(100, 75)),
                feature=Feature(
                    type="pocket",
                    depth_mm=6.0,
                ),
                shape_id="panel",
            ),
        ),
    )

    intents = ast_to_removal_intents(ast)
    planner_input = removal_intents_to_planner_input(intents)

    assert len(planner_input.corner_cleanups) == 0

    tool_db = [
        {"name": "3/8_endmill", "diameter": 9.525, "kind": "flat", "rpm": 12000, "feed_xy": 1200, "feed_z": 400},
    ]

    config = Config()
    machine = Machine()
    stock = Stock(width=200, height=150, thickness=19)

    passes, *_ = plan_passes(
        planner_input,
        config=config,
        tool_db=normalize_tool_entries(tool_db),
        machine=machine,
        stock=stock,
    )

    assert len(passes) == 1
    assert passes[0].op == "pocket"
