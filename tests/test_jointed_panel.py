import pytest
from generators.panels import NotchedPanelParams, notched_panel_generator
from assembly.panel import Edge, NotchSpec


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
                NotchSpec(edge=Edge.BOTTOM, u_start_mm=10, u_len_mm=20, depth_mm=6),
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

    def test_panel_with_notches_bakes_cutouts_into_profile(self):
        notches = (
            NotchSpec(edge=Edge.BOTTOM, u_start_mm=10, u_len_mm=20, depth_mm=6),
            NotchSpec(edge=Edge.BOTTOM, u_start_mm=40, u_len_mm=20, depth_mm=6),
            NotchSpec(edge=Edge.BOTTOM, u_start_mm=70, u_len_mm=20, depth_mm=6),
        )
        params = NotchedPanelParams(
            width_mm=100,
            height_mm=50,
            notches=notches,
        )
        items = notched_panel_generator(params, center=(50, 25))

        assert len(items) == 1
        assert items[0].feature.type == "profile"
        pts = items[0].geometry.data.get("points", [])
        assert len(pts) > 4

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

    def test_notched_panel_emits_profile_and_notch_items(self):
        notches = (
            NotchSpec(edge=Edge.BOTTOM, u_start_mm=20, u_len_mm=20, depth_mm=6),
        )
        params = NotchedPanelParams(
            width_mm=100,
            height_mm=50,
            notches=notches,
        )
        items = notched_panel_generator(params, center=(50, 25))

        assert len(items) == 1
        assert items[0].feature.type == "profile"
        assert items[0].feature.depth == "through"

    def test_notches_on_different_edges_emits_all_notches(self):
        notches = (
            NotchSpec(edge=Edge.BOTTOM, u_start_mm=20, u_len_mm=20, depth_mm=6),
            NotchSpec(edge=Edge.RIGHT, u_start_mm=10, u_len_mm=15, depth_mm=6),
            NotchSpec(edge=Edge.TOP, u_start_mm=30, u_len_mm=25, depth_mm=6),
            NotchSpec(edge=Edge.LEFT, u_start_mm=15, u_len_mm=10, depth_mm=6),
        )
        params = NotchedPanelParams(
            width_mm=100,
            height_mm=50,
            notches=notches,
        )
        items = notched_panel_generator(params, center=(50, 25))

        assert len(items) == 1
        assert items[0].feature.type == "profile"
        pts = items[0].geometry.data.get("points", [])
        assert len(pts) > 4

    def test_profile_polygon_includes_notch_inset_vertices(self):
        notches = (
            NotchSpec(edge=Edge.TOP, u_start_mm=10, u_len_mm=30, depth_mm=8),
        )
        params = NotchedPanelParams(
            width_mm=100,
            height_mm=50,
            notches=notches,
        )
        items = notched_panel_generator(params, center=(50, 25))

        pts = items[0].geometry.data.get("points", [])
        ys = [float(p[1]) for p in pts if isinstance(p, (tuple, list)) and len(p) >= 2]
        assert any(y < 25.0 for y in ys)
