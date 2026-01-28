import pytest
from generators.panels import NotchedPanelParams, notched_panel_generator
from assembly.notches import NotchSpec


class TestNotchedPanelParams:
    def test_validation_positive_dimensions(self):
        with pytest.raises(ValueError, match="width_mm must be positive"):
            NotchedPanelParams(width_mm=0, height_mm=50).validate()

        with pytest.raises(ValueError, match="height_mm must be positive"):
            NotchedPanelParams(width_mm=100, height_mm=-1).validate()

    def test_valid_params(self):
        params = NotchedPanelParams(
            width_mm=100,
            height_mm=50,
            notches=(
                NotchSpec(edge_index=0, u_start_mm=10, u_len_mm=20, depth_mm=6),
            ),
        )
        params.validate()


class TestNotchedPanelGenerator:
    def test_simple_rectangle_no_notches(self):
        params = NotchedPanelParams(
            width_mm=100,
            height_mm=50,
            notches=(),
        )
        items = notched_panel_generator(params, center=(50, 25))

        assert len(items) == 1
        assert items[0].feature.type == "profile"
        assert "points" in items[0].geometry.data

    def test_panel_with_notches(self):
        notches = (
            NotchSpec(edge_index=0, u_start_mm=10, u_len_mm=20, depth_mm=6),
            NotchSpec(edge_index=0, u_start_mm=40, u_len_mm=20, depth_mm=6),
            NotchSpec(edge_index=0, u_start_mm=70, u_len_mm=20, depth_mm=6),
        )
        params = NotchedPanelParams(
            width_mm=100,
            height_mm=50,
            notches=notches,
        )
        items = notched_panel_generator(params, center=(50, 25))

        assert len(items) == 1
        assert items[0].type == "Polygon"
        assert items[0].feature.type == "profile"
        points = items[0].geometry.data.get("points", [])
        assert len(points) > 4

    def test_panel_with_part_name(self):
        params = NotchedPanelParams(
            width_mm=100,
            height_mm=50,
            notches=(),
            part_name="FRONT",
        )
        items = notched_panel_generator(params, center=(50, 25))

        assert "front" in items[0].shape_id.lower()

    def test_panel_profile_is_through_cut(self):
        params = NotchedPanelParams(
            width_mm=100,
            height_mm=50,
            notches=(),
        )
        items = notched_panel_generator(params, center=(50, 25))

        assert items[0].feature.depth == "through"

    def test_notched_panel_is_single_profile(self):
        notches = (
            NotchSpec(edge_index=0, u_start_mm=20, u_len_mm=20, depth_mm=6),
        )
        params = NotchedPanelParams(
            width_mm=100,
            height_mm=50,
            notches=notches,
        )
        items = notched_panel_generator(params, center=(50, 25))

        assert len(items) == 1
        assert items[0].type == "Polygon"
        assert items[0].feature.type == "profile"
        assert items[0].feature.depth == "through"
        points = items[0].geometry.data.get("points", [])
        assert len(points) == 8

    def test_notches_on_different_edges(self):
        notches = (
            NotchSpec(edge_index=0, u_start_mm=20, u_len_mm=20, depth_mm=6),
            NotchSpec(edge_index=1, u_start_mm=10, u_len_mm=15, depth_mm=6),
            NotchSpec(edge_index=2, u_start_mm=30, u_len_mm=25, depth_mm=6),
            NotchSpec(edge_index=3, u_start_mm=15, u_len_mm=10, depth_mm=6),
        )
        params = NotchedPanelParams(
            width_mm=100,
            height_mm=50,
            notches=notches,
        )
        items = notched_panel_generator(params, center=(50, 25))

        assert len(items) == 1
        assert items[0].type == "Polygon"
        points = items[0].geometry.data.get("points", [])
        assert len(points) == 20
