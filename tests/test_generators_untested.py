from __future__ import annotations

import pytest

from domains import Domain
from generators import (
    EngraveTextParams,
    GridLinesParams,
    MeasurementEdgeParams,
    MeasurementGridParams,
    engrave_number_label,
    engrave_text_at_position,
    grid_lines_generator,
    measurement_edge_generator,
    measurement_grid_generator,
)


class TestGridLinesGenerator:
    def test_metric_grid_produces_items(self):
        domain = Domain.from_rectangle(100, 100, center=(50, 50))
        params = GridLinesParams(unit="metric", depth_mm=0.3)
        items = grid_lines_generator(domain, params)
        assert len(items) > 0

    def test_imperial_grid(self):
        domain = Domain.from_rectangle(200, 200, center=(100, 100))
        params = GridLinesParams(unit="imperial", depth_mm=0.3)
        items = grid_lines_generator(domain, params)
        assert len(items) > 0

    def test_custom_spacing(self):
        domain = Domain.from_rectangle(100, 100, center=(50, 50))
        params = GridLinesParams(unit="custom", spacing_mm=20.0, depth_mm=0.3)
        items = grid_lines_generator(domain, params)
        assert len(items) > 0

    def test_minor_lines(self):
        domain = Domain.from_rectangle(100, 100, center=(50, 50))
        params_no_minor = GridLinesParams(unit="metric", depth_mm=0.3, minor_lines=False)
        params_minor = GridLinesParams(unit="metric", depth_mm=0.3, minor_lines=True)
        items_no_minor = grid_lines_generator(domain, params_no_minor)
        items_minor = grid_lines_generator(domain, params_minor)
        assert len(items_minor) >= len(items_no_minor)

    def test_too_small_domain_raises(self):
        domain = Domain.from_rectangle(0.5, 0.5, center=(0.25, 0.25))
        params = GridLinesParams(unit="metric", depth_mm=0.3)
        with pytest.raises(ValueError):
            grid_lines_generator(domain, params)

    def test_too_small_domain_allow_empty(self):
        domain = Domain.from_rectangle(0.5, 0.5, center=(0.25, 0.25))
        params = GridLinesParams(unit="metric", depth_mm=0.3)
        items = grid_lines_generator(domain, params, allow_empty=True)
        assert items == []

    def test_depth_applied(self):
        domain = Domain.from_rectangle(100, 100, center=(50, 50))
        params = GridLinesParams(unit="metric", depth_mm=0.5)
        items = grid_lines_generator(domain, params)
        for item in items:
            assert item.feature is not None
            assert item.feature.depth_mm == pytest.approx(0.5)

    def test_items_have_line_geometry(self):
        domain = Domain.from_rectangle(100, 100, center=(50, 50))
        params = GridLinesParams(unit="metric", depth_mm=0.3)
        items = grid_lines_generator(domain, params)
        for item in items:
            assert item.geometry is not None
            assert "start" in item.geometry.data
            assert "end" in item.geometry.data

    def test_param_validation_custom_no_spacing(self):
        with pytest.raises(ValueError, match="spacing_mm required"):
            GridLinesParams(unit="custom", depth_mm=0.3)

    def test_param_validation_negative_depth(self):
        with pytest.raises(ValueError, match="positive"):
            GridLinesParams(unit="metric", depth_mm=-1.0)


class TestMeasurementGridGenerator:
    def test_metric_ticks_produced(self):
        domain = Domain.from_rectangle(100, 100, center=(50, 50))
        params = MeasurementGridParams(unit="metric", depth_mm=0.5)
        items = measurement_grid_generator(domain, params)
        assert len(items) > 0

    def test_imperial_ticks(self):
        domain = Domain.from_rectangle(200, 200, center=(100, 100))
        params = MeasurementGridParams(unit="imperial", depth_mm=0.5)
        items = measurement_grid_generator(domain, params)
        assert len(items) > 0

    def test_minor_ticks_disabled(self):
        domain = Domain.from_rectangle(100, 100, center=(50, 50))
        params_minor = MeasurementGridParams(unit="metric", depth_mm=0.5, minor_ticks=True)
        params_no_minor = MeasurementGridParams(unit="metric", depth_mm=0.5, minor_ticks=False)
        items_minor = measurement_grid_generator(domain, params_minor)
        items_no_minor = measurement_grid_generator(domain, params_no_minor)
        assert len(items_minor) >= len(items_no_minor)

    def test_labels_add_items(self):
        domain = Domain.from_rectangle(100, 100, center=(50, 50))
        params_no_labels = MeasurementGridParams(unit="metric", depth_mm=0.5, labels=False)
        params_labels = MeasurementGridParams(unit="metric", depth_mm=0.5, labels=True)
        items_no_labels = measurement_grid_generator(domain, params_no_labels)
        items_labels = measurement_grid_generator(domain, params_labels)
        assert len(items_labels) > len(items_no_labels)

    def test_too_small_domain_raises(self):
        domain = Domain.from_rectangle(0.5, 0.5, center=(0.25, 0.25))
        params = MeasurementGridParams(unit="metric", depth_mm=0.5)
        with pytest.raises(ValueError):
            measurement_grid_generator(domain, params)

    def test_too_small_domain_allow_empty(self):
        domain = Domain.from_rectangle(0.5, 0.5, center=(0.25, 0.25))
        params = MeasurementGridParams(unit="metric", depth_mm=0.5)
        items = measurement_grid_generator(domain, params, allow_empty=True)
        assert items == []

    def test_depth_applied(self):
        domain = Domain.from_rectangle(100, 100, center=(50, 50))
        params = MeasurementGridParams(unit="metric", depth_mm=0.8)
        items = measurement_grid_generator(domain, params)
        for item in items:
            assert item.feature is not None
            assert item.feature.depth_mm == pytest.approx(0.8)

    def test_custom_spacing(self):
        domain = Domain.from_rectangle(100, 100, center=(50, 50))
        params = MeasurementGridParams(
            unit="custom",
            minor_spacing_mm=5.0,
            major_spacing_mm=25.0,
            depth_mm=0.5,
        )
        items = measurement_grid_generator(domain, params)
        assert len(items) > 0


class TestMeasurementEdgeGenerator:
    def test_bottom_edge_ticks(self):
        domain = Domain.from_rectangle(100, 100, center=(50, 50))
        params = MeasurementEdgeParams(edges=("bottom",), unit="metric", depth_mm=0.3)
        items = measurement_edge_generator(domain, params)
        assert len(items) > 0

    def test_all_edges(self):
        domain = Domain.from_rectangle(100, 100, center=(50, 50))
        params = MeasurementEdgeParams(
            edges=("top", "bottom", "left", "right"),
            unit="metric",
            depth_mm=0.3,
        )
        items = measurement_edge_generator(domain, params)
        assert len(items) > 0

    def test_single_vs_all_edges(self):
        domain = Domain.from_rectangle(100, 100, center=(50, 50))
        single = MeasurementEdgeParams(edges=("bottom",), unit="metric", depth_mm=0.3)
        all_edges = MeasurementEdgeParams(
            edges=("top", "bottom", "left", "right"),
            unit="metric",
            depth_mm=0.3,
        )
        items_single = measurement_edge_generator(domain, single)
        items_all = measurement_edge_generator(domain, all_edges)
        assert len(items_all) > len(items_single)

    def test_labels(self):
        domain = Domain.from_rectangle(100, 100, center=(50, 50))
        params_no = MeasurementEdgeParams(
            edges=("bottom",),
            unit="metric",
            depth_mm=0.3,
            labels=False,
        )
        params_yes = MeasurementEdgeParams(
            edges=("bottom",),
            unit="metric",
            depth_mm=0.3,
            labels=True,
        )
        items_no = measurement_edge_generator(domain, params_no)
        items_yes = measurement_edge_generator(domain, params_yes)
        assert len(items_yes) > len(items_no)

    def test_too_small_domain_raises(self):
        domain = Domain.from_rectangle(0.5, 0.5, center=(0.25, 0.25))
        params = MeasurementEdgeParams(edges=("bottom",), unit="metric", depth_mm=0.3)
        with pytest.raises(ValueError):
            measurement_edge_generator(domain, params)

    def test_too_small_domain_allow_empty(self):
        domain = Domain.from_rectangle(0.5, 0.5, center=(0.25, 0.25))
        params = MeasurementEdgeParams(edges=("bottom",), unit="metric", depth_mm=0.3)
        items = measurement_edge_generator(domain, params, allow_empty=True)
        assert items == []

    def test_param_validation_no_edges(self):
        with pytest.raises(ValueError, match="at least one edge"):
            MeasurementEdgeParams(edges=(), depth_mm=0.3)


class TestEngraveText:
    def test_basic_text(self):
        items = engrave_text_at_position(
            text="Hello",
            position=(50, 50),
            height_mm=5.0,
            depth_mm=0.3,
        )
        assert len(items) > 0

    def test_empty_text_returns_empty(self):
        items = engrave_text_at_position(
            text="",
            position=(50, 50),
            height_mm=5.0,
            depth_mm=0.3,
        )
        assert items == []

    def test_alignment_center(self):
        items = engrave_text_at_position(
            text="Test",
            position=(100, 100),
            height_mm=5.0,
            depth_mm=0.3,
            alignment="center",
        )
        assert len(items) > 0

    def test_alignment_right(self):
        items = engrave_text_at_position(
            text="Test",
            position=(100, 100),
            height_mm=5.0,
            depth_mm=0.3,
            alignment="right",
        )
        assert len(items) > 0

    def test_vertical_orientation(self):
        items = engrave_text_at_position(
            text="V",
            position=(50, 50),
            height_mm=5.0,
            depth_mm=0.3,
            orientation="vertical",
        )
        assert len(items) > 0

    def test_depth_applied(self):
        items = engrave_text_at_position(
            text="X",
            position=(50, 50),
            height_mm=5.0,
            depth_mm=0.7,
        )
        for item in items:
            assert item.feature is not None
            assert item.feature.depth_mm == pytest.approx(0.7)

    def test_number_label(self):
        items = engrave_number_label(
            value=42,
            position=(50, 50),
            height_mm=3.0,
            depth_mm=0.3,
        )
        assert len(items) > 0

    def test_number_label_zero(self):
        items = engrave_number_label(
            value=0,
            position=(50, 50),
            height_mm=3.0,
            depth_mm=0.3,
        )
        assert len(items) > 0

    def test_param_validation_empty_text(self):
        with pytest.raises(ValueError, match="not be empty"):
            EngraveTextParams(text="")

    def test_param_validation_negative_height(self):
        with pytest.raises(ValueError, match="positive"):
            EngraveTextParams(text="X", height_mm=-1.0)

    def test_param_validation_invalid_alignment(self):
        with pytest.raises(ValueError, match="alignment"):
            EngraveTextParams(text="X", alignment="middle")  # type: ignore[arg-type]
