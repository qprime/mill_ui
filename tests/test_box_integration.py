"""Integration test demonstrating end-to-end box generation.

This test validates the complete flow:
1. Define box parameters
2. Compute panel specifications
3. Generate panel geometry with finger joints
4. Produce LayoutAST Items suitable for CAM processing
"""
import pytest

from domains import Domain
from generators.assemblies import BoxParams, FingerStrategy, compute_box_panels
from generators.panels import JointedPanelParams, jointed_panel_generator
from joints.profiles import FingerJointProfile


class TestBoxGenerationIntegration:
    def test_simple_finger_box_generates_valid_items(self):
        """Complete flow: BoxParams → PanelSpecs → Items"""
        params = BoxParams(
            outer_width_mm=150,
            outer_depth_mm=100,
            outer_height_mm=75,
            thickness_mm=6,
            joinery="finger",
            finger_strategy=FingerStrategy(mode="by_width", value=12.0),
            clearance_mm=0.15,
            include_bottom=True,
            include_lid=False,
        )

        panels = compute_box_panels(params)
        assert len(panels) == 5

        all_items = []
        y_offset = 0.0
        gap = 10.0

        for panel_spec in panels:
            panel_params = JointedPanelParams(
                width_mm=panel_spec.width_mm,
                height_mm=panel_spec.height_mm,
                edge_joints={
                    edge: profile
                    for edge, profile in panel_spec.edge_joints.items()
                    if profile is not None
                },
                part_name=panel_spec.name,
            )

            center_x = panel_spec.width_mm / 2 + gap
            center_y = y_offset + panel_spec.height_mm / 2 + gap

            items = jointed_panel_generator(
                panel_params,
                center=(center_x, center_y),
            )

            all_items.extend(items)
            y_offset += panel_spec.height_mm + gap

        assert len(all_items) == 5
        for item in all_items:
            assert item.feature.type == "profile"
            assert item.feature.depth == "through"
            assert "points" in item.geometry.data

    def test_butt_box_generates_simple_rectangles(self):
        """Butt joints produce simple 4-vertex rectangles"""
        params = BoxParams(
            outer_width_mm=200,
            outer_depth_mm=150,
            outer_height_mm=100,
            thickness_mm=6,
            joinery="butt",
            include_bottom=True,
            include_lid=False,
        )

        panels = compute_box_panels(params)

        for panel_spec in panels:
            panel_params = JointedPanelParams(
                width_mm=panel_spec.width_mm,
                height_mm=panel_spec.height_mm,
                edge_joints={},
                part_name=panel_spec.name,
            )

            items = jointed_panel_generator(panel_params, center=(50, 50))

            assert len(items) == 1
            assert len(items[0].geometry.data["points"]) == 4

    def test_finger_joints_create_comb_geometry(self):
        """Finger joints create many-vertex comb patterns"""
        params = BoxParams(
            outer_width_mm=200,
            outer_depth_mm=150,
            outer_height_mm=100,
            thickness_mm=6,
            joinery="finger",
            finger_strategy=FingerStrategy(mode="by_count", value=7),
            clearance_mm=0.0,
            include_bottom=True,
        )

        panels = compute_box_panels(params)
        front = next(p for p in panels if p.name == "front")

        panel_params = JointedPanelParams(
            width_mm=front.width_mm,
            height_mm=front.height_mm,
            edge_joints={
                edge: profile
                for edge, profile in front.edge_joints.items()
                if profile is not None
            },
            part_name=front.name,
        )

        items = jointed_panel_generator(panel_params, center=(100, 50))

        assert len(items[0].geometry.data["points"]) > 4

    def test_panels_fit_together_geometrically(self):
        """Adjacent panel edges should have complementary lengths"""
        params = BoxParams(
            outer_width_mm=200,
            outer_depth_mm=150,
            outer_height_mm=100,
            thickness_mm=6,
            joinery="finger",
            finger_strategy=FingerStrategy(mode="by_count", value=5),
        )

        panels = compute_box_panels(params)

        front = next(p for p in panels if p.name == "front")
        left = next(p for p in panels if p.name == "left_side")

        assert front.height_mm == left.height_mm

        assert front.edge_joints["left"].phase == 0
        assert left.edge_joints["right"].phase == 1

    def test_box_with_lid_adds_sixth_panel(self):
        """Including lid should add a top panel"""
        params_no_lid = BoxParams(
            outer_width_mm=200,
            outer_depth_mm=150,
            outer_height_mm=100,
            thickness_mm=6,
            joinery="butt",
            include_lid=False,
        )

        params_with_lid = BoxParams(
            outer_width_mm=200,
            outer_depth_mm=150,
            outer_height_mm=100,
            thickness_mm=6,
            joinery="butt",
            include_lid=True,
        )

        panels_no_lid = compute_box_panels(params_no_lid)
        panels_with_lid = compute_box_panels(params_with_lid)

        assert len(panels_no_lid) == 5
        assert len(panels_with_lid) == 6

        names = [p.name for p in panels_with_lid]
        assert "top" in names

    def test_nested_layout_simulation(self):
        """Simulate how panels would be laid out for nesting"""
        params = BoxParams(
            outer_width_mm=150,
            outer_depth_mm=100,
            outer_height_mm=75,
            thickness_mm=6,
            joinery="finger",
            finger_strategy=FingerStrategy(mode="by_width", value=10.0),
        )

        panels = compute_box_panels(params)

        sheet_width = 400
        sheet_height = 300
        margin = 10

        x = margin
        y = margin
        row_height = 0

        all_items = []
        for panel_spec in panels:
            if x + panel_spec.width_mm > sheet_width - margin:
                x = margin
                y += row_height + margin
                row_height = 0

            center = (x + panel_spec.width_mm / 2, y + panel_spec.height_mm / 2)

            panel_params = JointedPanelParams(
                width_mm=panel_spec.width_mm,
                height_mm=panel_spec.height_mm,
                edge_joints={
                    edge: profile
                    for edge, profile in panel_spec.edge_joints.items()
                    if profile is not None
                },
                part_name=panel_spec.name,
            )

            items = jointed_panel_generator(panel_params, center=center)
            all_items.extend(items)

            x += panel_spec.width_mm + margin
            row_height = max(row_height, panel_spec.height_mm)

        assert len(all_items) == 5
        for item in all_items:
            assert item.feature.type == "profile"
