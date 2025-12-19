"""Unit tests for layout resolution: compositional AST → flat LayoutAST.

Stage 12 acceptance tests.
"""

from __future__ import annotations

import pytest

from layout_ast.compositional import (
    Panel,
    Inset,
    Frame,
    Grid,
    Cell,
    ComponentDef,
    UseComponent,
    Place,
    Rect,
    CompositionalLayoutAST,
)
from layout_ast.layout import Sheet, Feature
from resolution.layout_resolver import resolve_layout
from pml import format_pml


def test_simple_panel_with_rect():
    """Test basic panel with single rect fills region."""
    ast = CompositionalLayoutAST(
        sheet=Sheet(width_mm=400, height_mm=600, thickness_mm=19),
        root=Panel(
            children=(
                Rect(
                    feature=Feature(type="profile", depth="through", side="outside"),
                    id="outer",
                ),
            )
        ),
    )

    flat = resolve_layout(ast)

    assert len(flat.items) == 1
    item = flat.items[0]
    assert item.type == "Rect"
    assert item.geometry.data["w_mm"] == 400.0
    assert item.geometry.data["h_mm"] == 600.0
    assert item.placement.center_xy_mm == (200.0, 300.0)  # Center of 400x600
    assert item.feature.type == "profile"


def test_panel_with_inset():
    """Test inset shrinks region before placing children."""
    ast = CompositionalLayoutAST(
        sheet=Sheet(width_mm=400, height_mm=600, thickness_mm=19),
        root=Panel(
            children=(
                Inset(
                    amount_mm=25,
                    children=(
                        Rect(
                            feature=Feature(type="pocket", depth="6.0", depth_mm=6.0),
                            id="panel",
                        ),
                    ),
                ),
            )
        ),
    )

    flat = resolve_layout(ast)

    assert len(flat.items) == 1
    item = flat.items[0]
    # Inset 25mm on all sides: 400-50=350, 600-50=550
    assert item.geometry.data["w_mm"] == 350.0
    assert item.geometry.data["h_mm"] == 550.0
    # Center shifts by inset: (200, 300)
    assert item.placement.center_xy_mm == (200.0, 300.0)


def test_frame_creates_profile_and_inner_region():
    """Test frame creates outer profile and places children in inner region."""
    ast = CompositionalLayoutAST(
        sheet=Sheet(width_mm=400, height_mm=600, thickness_mm=19),
        root=Panel(
            children=(
                Rect(
                    children=(
                        Frame(
                            width_mm=50,
                            children=(
                                Rect(
                                    feature=Feature(type="pocket", depth="6.0", depth_mm=6.0),
                                    id="inner",
                                ),
                            ),
                        ),
                    ),
                    feature=Feature(type="profile", depth="through", side="outside"),
                    id="outer",
                ),
            )
        ),
    )

    flat = resolve_layout(ast)

    # Should have: outer rect + frame profile + inner pocket
    assert len(flat.items) == 3

    # Outer rect (panel fill)
    outer = flat.items[0]
    assert outer.shape_id == "outer"
    assert outer.geometry.data["w_mm"] == 400.0
    assert outer.geometry.data["h_mm"] == 600.0

    # Frame profile (same size as outer)
    frame_profile = flat.items[1]
    assert frame_profile.feature.type == "profile"
    assert frame_profile.geometry.data["w_mm"] == 400.0
    assert frame_profile.geometry.data["h_mm"] == 600.0

    # Inner pocket (frame creates inset region: 400-100=300, 600-100=500)
    inner = flat.items[2]
    assert inner.shape_id == "inner"
    assert inner.feature.type == "pocket"
    assert inner.geometry.data["w_mm"] == 300.0
    assert inner.geometry.data["h_mm"] == 500.0


def test_grid_subdivides_region():
    """Test grid subdivides region into cells."""
    ast = CompositionalLayoutAST(
        sheet=Sheet(width_mm=400, height_mm=400, thickness_mm=19),
        root=Panel(
            children=(
                Grid(
                    rows=2,
                    cols=2,
                    gap_mm=10,
                    children=(
                        Cell(
                            children=(
                                Rect(
                                    feature=Feature(type="pocket", depth="5.0", depth_mm=5.0),
                                    id="cell_pocket",
                                ),
                            )
                        ),
                    ),
                ),
            )
        ),
    )

    flat = resolve_layout(ast)

    # 2x2 grid = 4 cells, each with 1 pocket rect
    assert len(flat.items) == 4

    # Verify cell dimensions
    # Total width/height: 400mm
    # Gap: 10mm (one gap between 2 cols/rows)
    # Cell size: (400 - 10) / 2 = 195mm
    for item in flat.items:
        assert item.feature.type == "pocket"
        assert item.geometry.data["w_mm"] == pytest.approx(195.0)
        assert item.geometry.data["h_mm"] == pytest.approx(195.0)


def test_component_definition_and_use():
    """Test component definition with parameter substitution."""
    # Define a simple component
    simple_panel = ComponentDef(
        name="SimplePanel",
        params={"recess_depth": 6.0},
        body=Rect(
            feature=Feature(type="pocket", depth="6.0", depth_mm=6.0),
            id="panel",
        ),
    )

    ast = CompositionalLayoutAST(
        sheet=Sheet(width_mm=400, height_mm=600, thickness_mm=19),
        components={"SimplePanel": simple_panel},
        root=Panel(
            children=(
                UseComponent(
                    component_name="SimplePanel",
                    args={"recess_depth": 8.0},
                ),
            )
        ),
    )

    flat = resolve_layout(ast)

    assert len(flat.items) == 1
    item = flat.items[0]
    assert item.shape_id == "panel"
    # Note: parameter substitution for feature depth would require
    # more sophisticated param binding. For now, component uses literal values.


def test_place_grid_with_components():
    """Test Place+Grid for multi-instance sheet layout."""
    # Define a component
    shaker_panel = ComponentDef(
        name="ShakerPanel",
        params={"frame_width": 50.0, "recess_depth": 6.0},
        body=Rect(
            children=(
                Frame(
                    width_mm=50,  # Literal for now; param binding deferred
                    children=(
                        Rect(
                            feature=Feature(type="pocket", depth="6.0", depth_mm=6.0),
                            id="inner",
                        ),
                    ),
                ),
            ),
            feature=Feature(type="profile", depth="through", side="outside"),
            id="outer",
        ),
    )

    ast = CompositionalLayoutAST(
        sheet=Sheet(width_mm=1000, height_mm=1000, thickness_mm=19),
        components={"ShakerPanel": shaker_panel},
        root=Place(
            layout=Grid(rows=2, cols=2, gap_mm=50),
            children=(
                UseComponent(component_name="ShakerPanel"),
                UseComponent(component_name="ShakerPanel"),
                UseComponent(component_name="ShakerPanel"),
                UseComponent(component_name="ShakerPanel"),
            ),
        ),
    )

    flat = resolve_layout(ast)

    # Each component instance produces: outer rect + frame profile + inner pocket = 3 items
    # 4 instances × 3 items = 12 total items
    assert len(flat.items) == 12

    # Verify items are distributed across grid cells
    # Grid: 2×2 with 50mm gap
    # Cell size: (1000 - 50) / 2 = 475mm

    # First instance (top-left cell)
    first_outer = flat.items[0]
    assert first_outer.shape_id == "outer"
    assert first_outer.geometry.data["w_mm"] == pytest.approx(475.0)
    assert first_outer.geometry.data["h_mm"] == pytest.approx(475.0)


def test_acceptance_4_instances_frame_grid_pocket():
    """Acceptance test: 4 identical instances via grid, each with frame+grid+pocket.

    This is the Stage 12 acceptance criteria test case.
    """
    # Define component: frame + 2×2 grid of pockets
    grid_panel = ComponentDef(
        name="GridPanel",
        params={},
        body=Rect(
            children=(
                Frame(
                    width_mm=40,
                    children=(
                        Grid(
                            rows=2,
                            cols=2,
                            gap_mm=10,
                            children=(
                                Cell(
                                    children=(
                                        Rect(
                                            feature=Feature(type="pocket", depth="5.0", depth_mm=5.0),
                                        ),
                                    )
                                ),
                            ),
                        ),
                    ),
                ),
            ),
            feature=Feature(type="profile", depth="through", side="outside"),
            id="panel_outer",
        ),
    )

    # Place 4 instances on sheet via 2×2 grid
    ast = CompositionalLayoutAST(
        sheet=Sheet(width_mm=1200, height_mm=1200, thickness_mm=19),
        components={"GridPanel": grid_panel},
        root=Place(
            layout=Grid(rows=2, cols=2, gap_mm=100),
            children=(
                UseComponent(component_name="GridPanel"),
                UseComponent(component_name="GridPanel"),
                UseComponent(component_name="GridPanel"),
                UseComponent(component_name="GridPanel"),
            ),
        ),
        project="acceptance_test_grid_panels",
    )

    flat = resolve_layout(ast)

    # Each instance produces:
    # - 1 outer rect (panel fill)
    # - 1 frame profile
    # - 4 pocket rects (2×2 grid)
    # Total per instance: 6 items
    # 4 instances × 6 = 24 items
    assert len(flat.items) == 24

    # Verify flat AST is valid
    assert flat.sheet.width_mm == 1200
    assert flat.sheet.height_mm == 1200
    assert flat.project == "acceptance_test_grid_panels"

    # Verify we can export to FlatPML
    pml_output = format_pml(flat)
    assert "sheet 1200.00mm 1200.00mm 19.00mm" in pml_output
    assert "project acceptance_test_grid_panels" in pml_output
    assert "profile through outside" in pml_output
    assert "pocket 5.00mm" in pml_output

    # Verify item distribution
    profile_items = [item for item in flat.items if item.feature and item.feature.type == "profile"]
    pocket_items = [item for item in flat.items if item.feature and item.feature.type == "pocket"]

    # 4 instances × (1 outer rect + 1 frame profile) = 8 rects, but only frame profiles are marked
    # Actually: outer rects have profile feature too
    # Let's count: each instance has 1 outer profile + 1 frame profile = 2 profiles
    # 4 instances × 2 = 8 profiles
    assert len(profile_items) == 8

    # 4 instances × 4 pockets = 16 pockets
    assert len(pocket_items) == 16

    print("\n=== Acceptance Test FlatPML Output ===")
    print(pml_output[:1000])  # Print first 1000 chars for inspection


def test_grid_with_no_explicit_cell():
    """Test grid without explicit Cell node treats children as cell content."""
    ast = CompositionalLayoutAST(
        sheet=Sheet(width_mm=400, height_mm=400, thickness_mm=19),
        root=Panel(
            children=(
                Grid(
                    rows=2,
                    cols=2,
                    gap_mm=0,
                    children=(
                        Rect(
                            feature=Feature(type="pocket", depth="5.0", depth_mm=5.0),
                        ),
                    ),
                ),
            )
        ),
    )

    flat = resolve_layout(ast)

    # 2×2 grid = 4 cells, each with rect
    assert len(flat.items) == 4
