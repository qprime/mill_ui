from __future__ import annotations

import pytest

from assembly.beam import (
    BeamRole,
    BeamSpec,
    Chamfer,
    Cutout,
    DrillHole,
    EdgeDado,
    Fillet,
    LayerSpec,
    Segment,
    SquareMortise,
    Tenon,
    compute_segments,
    validate_butts_never_align,
    validate_stagger_minimum,
)


class TestCutout:
    def test_valid_cutout(self):
        cutout = Cutout(start_mm=10, length_mm=20)
        assert cutout.start_mm == 10
        assert cutout.length_mm == 20

    def test_negative_start_raises(self):
        with pytest.raises(ValueError, match="non-negative"):
            Cutout(start_mm=-5, length_mm=20)

    def test_zero_length_raises(self):
        with pytest.raises(ValueError, match="positive"):
            Cutout(start_mm=0, length_mm=0)

    def test_negative_width_raises(self):
        with pytest.raises(ValueError, match="positive"):
            Cutout(start_mm=0, length_mm=10, width_mm=-5)


class TestLayerSpec:
    def test_valid_layer_spec(self):
        layer = LayerSpec(length_mm=500)
        assert layer.length_mm == 500
        assert layer.offset_mm == 0.0

    def test_with_offset(self):
        layer = LayerSpec(length_mm=500, offset_mm=10)
        assert layer.offset_mm == 10

    def test_with_cutouts(self):
        cutout = Cutout(start_mm=100, length_mm=50)
        layer = LayerSpec(length_mm=500, cutouts=(cutout,))
        assert len(layer.cutouts) == 1

    def test_cutout_exceeds_length_raises(self):
        cutout = Cutout(start_mm=450, length_mm=100)
        with pytest.raises(ValueError, match="exceeds layer length"):
            LayerSpec(length_mm=500, cutouts=(cutout,))

    def test_zero_length_raises(self):
        with pytest.raises(ValueError, match="positive"):
            LayerSpec(length_mm=0)


class TestSegment:
    def test_segment_length_property(self):
        seg = Segment(start_mm=0, end_mm=500, layer=0, index=0)
        assert seg.length == 500

    def test_segment_with_offset(self):
        seg = Segment(start_mm=100, end_mm=600, layer=1, index=1)
        assert seg.length == 500


class TestComputeSegments:
    def test_no_splicing_when_length_fits_sheet(self):
        segments = compute_segments(length=500, sheet_size=1200, layers=3)
        assert len(segments) == 3
        for layer_segments in segments:
            assert len(layer_segments) == 1
            assert layer_segments[0].length == 500

    def test_single_layer_no_splicing(self):
        segments = compute_segments(length=800, sheet_size=1200, layers=1)
        assert len(segments) == 1
        assert len(segments[0]) == 1
        assert segments[0][0].length == 800

    def test_splicing_when_length_exceeds_sheet(self):
        segments = compute_segments(length=2000, sheet_size=1200, layers=3)
        for layer_segments in segments:
            assert len(layer_segments) >= 2
            total_length = sum(seg.length for seg in layer_segments)
            assert abs(total_length - 2000) < 0.001

    def test_butts_never_align(self):
        segments = compute_segments(length=2000, sheet_size=1200, layers=3)
        butt_positions: list[float] = []
        for layer_segments in segments:
            for seg in layer_segments[:-1]:
                butt_positions.append(seg.end_mm)
        assert len(butt_positions) == len(set(butt_positions))

    def test_segment_indices_correct(self):
        segments = compute_segments(length=2000, sheet_size=1200, layers=2)
        for layer_idx, layer_segments in enumerate(segments):
            for seg_idx, seg in enumerate(layer_segments):
                assert seg.layer == layer_idx
                assert seg.index == seg_idx

    def test_invalid_layers_raises(self):
        with pytest.raises(ValueError, match="layers must be >= 1"):
            compute_segments(length=500, sheet_size=1200, layers=0)

    def test_invalid_length_raises(self):
        with pytest.raises(ValueError, match="length must be positive"):
            compute_segments(length=0, sheet_size=1200, layers=3)

    def test_minimum_segment_length_avoids_tiny_segments(self):
        segments = compute_segments(length=2000, sheet_size=1187.3, layers=3)
        min_len = 1187.3 * 0.1
        for layer_segments in segments:
            for seg in layer_segments:
                assert seg.length >= min_len, f"Segment {seg} is too short"

    def test_minimum_segment_length_custom(self):
        segments = compute_segments(length=2000, sheet_size=1200, layers=3, min_segment_length=200)
        for layer_segments in segments:
            for seg in layer_segments:
                assert seg.length >= 200, f"Segment {seg} is shorter than custom minimum"

    def test_minimum_segment_splits_evenly(self):
        segments = compute_segments(length=1250, sheet_size=1200, layers=1, min_segment_length=100)
        assert len(segments[0]) == 2
        seg0_len = segments[0][0].length
        seg1_len = segments[0][1].length
        assert abs(seg0_len - seg1_len) < 1.0


class TestValidateButtsNeverAlign:
    def test_valid_segments_pass(self):
        segments = compute_segments(length=2000, sheet_size=1200, layers=3)
        validate_butts_never_align(segments)

    def test_aligned_butts_raise(self):
        segments = [
            [Segment(0, 500, 0, 0), Segment(500, 1000, 0, 1)],
            [Segment(0, 500, 1, 0), Segment(500, 1000, 1, 1)],
        ]
        with pytest.raises(ValueError, match="BM-9"):
            validate_butts_never_align(segments)


class TestValidateStaggerMinimum:
    def test_sufficient_stagger_passes(self):
        segments = compute_segments(length=2000, sheet_size=1200, layers=3)
        validate_stagger_minimum(segments, thickness_mm=19)

    def test_single_layer_passes(self):
        segments = [[Segment(0, 500, 0, 0)]]
        validate_stagger_minimum(segments, thickness_mm=19)


class TestBeamSpecBasic:
    def test_single_layer_equivalent_to_panel(self):
        beam = BeamSpec(
            name="test",
            length_mm=500,
            width_mm=100,
            thickness_mm=19,
            layers=1,
        )
        panels = beam.expand(sheet_size=1200)
        assert len(panels) == 1
        assert panels[0].name == "test"
        assert panels[0].width_mm == 500
        assert panels[0].height_mm == 100
        assert panels[0].thickness_mm == 19

    def test_layer_count_from_int(self):
        beam = BeamSpec(name="test", length_mm=500, width_mm=100, thickness_mm=19, layers=3)
        assert beam.layer_count == 3

    def test_layer_count_from_tuple(self):
        beam = BeamSpec(
            name="test",
            length_mm=500,
            width_mm=100,
            thickness_mm=19,
            layers=(LayerSpec(500), LayerSpec(500)),
        )
        assert beam.layer_count == 2

    def test_total_thickness(self):
        beam = BeamSpec(name="test", length_mm=500, width_mm=100, thickness_mm=19, layers=3)
        assert beam.total_thickness == 57

    def test_role_assignment(self):
        beam = BeamSpec(
            name="post",
            length_mm=500,
            width_mm=76,
            thickness_mm=19,
            layers=3,
            role=BeamRole.POST,
        )
        assert beam.role == BeamRole.POST


class TestBeamSpecExpand:
    def test_multi_layer_expansion(self):
        beam = BeamSpec(
            name="post",
            length_mm=500,
            width_mm=76,
            thickness_mm=19,
            layers=3,
        )
        panels = beam.expand(sheet_size=1200)
        assert len(panels) == 3
        assert panels[0].name == "post_L0"
        assert panels[1].name == "post_L1"
        assert panels[2].name == "post_L2"

    def test_spliced_beam_expansion(self):
        beam = BeamSpec(
            name="rail",
            length_mm=2000,
            width_mm=100,
            thickness_mm=19,
            layers=3,
        )
        panels = beam.expand(sheet_size=1200)
        assert len(panels) > 3

    def test_expansion_deterministic(self):
        beam = BeamSpec(
            name="test",
            length_mm=2000,
            width_mm=100,
            thickness_mm=19,
            layers=3,
        )
        panels1 = beam.expand(sheet_size=1200)
        panels2 = beam.expand(sheet_size=1200)
        assert len(panels1) == len(panels2)
        for p1, p2 in zip(panels1, panels2, strict=False):
            assert p1.name == p2.name
            assert p1.width_mm == p2.width_mm
            assert p1.height_mm == p2.height_mm

    def test_explicit_layer_specs_expansion(self):
        beam = BeamSpec(
            name="post",
            length_mm=500,
            width_mm=76,
            thickness_mm=19,
            layers=(
                LayerSpec(length_mm=500),
                LayerSpec(length_mm=538, offset_mm=0),
                LayerSpec(length_mm=500),
            ),
        )
        panels = beam.expand(sheet_size=1200)
        assert len(panels) == 3
        assert panels[0].width_mm == 500
        assert panels[1].width_mm == 538
        assert panels[2].width_mm == 500


class TestBeamSpecValidation:
    def test_negative_length_raises(self):
        with pytest.raises(ValueError, match="positive"):
            BeamSpec(name="test", length_mm=-100, width_mm=100, thickness_mm=19, layers=1)

    def test_zero_width_raises(self):
        with pytest.raises(ValueError, match="positive"):
            BeamSpec(name="test", length_mm=100, width_mm=0, thickness_mm=19, layers=1)

    def test_zero_layers_raises(self):
        with pytest.raises(ValueError, match=">= 1"):
            BeamSpec(name="test", length_mm=100, width_mm=100, thickness_mm=19, layers=0)

    def test_empty_layers_tuple_raises(self):
        with pytest.raises(ValueError, match="at least one"):
            BeamSpec(name="test", length_mm=100, width_mm=100, thickness_mm=19, layers=())


class TestFeatureDataclasses:
    def test_drill_hole_defaults(self):
        hole = DrillHole(x_mm=100, y_mm=50, diameter_mm=10)
        assert hole.face == "front"
        assert hole.stage == "strip"
        assert hole.depth_mm is None

    def test_square_mortise(self):
        mortise = SquareMortise(x_mm=200, y_mm=38, width_mm=38, height_mm=50, depth_mm=19)
        assert mortise.width_mm == 38
        assert mortise.depth_mm == 19

    def test_tenon_defaults(self):
        tenon = Tenon(
            end="right",
            extension_mm=38,
            width_mm=100,
            height_mm=19,
        )
        assert tenon.layers == "center"
        assert tenon.center_offset_mm == 0.0

    def test_chamfer_defaults(self):
        chamfer = Chamfer(edge="top", width_mm=3)
        assert chamfer.angle_deg == 45.0
        assert chamfer.layers == "outer"
        assert chamfer.stage == "strip"

    def test_fillet_defaults(self):
        fillet = Fillet(edge="bottom", radius_mm=6)
        assert fillet.layers == "outer"
        assert fillet.start_mm == 0.0

    def test_edge_dado_defaults(self):
        dado = EdgeDado(edge="top", position_mm=100, width_mm=19, depth_mm=9.5)
        assert dado.layers == "all"


class TestBeamSpecWithFeatures:
    def test_beam_with_face_features(self):
        beam = BeamSpec(
            name="post",
            length_mm=500,
            width_mm=76,
            thickness_mm=19,
            layers=3,
            face_features=(
                DrillHole(x_mm=250, y_mm=38, diameter_mm=10),
                SquareMortise(x_mm=200, y_mm=38, width_mm=38, height_mm=50, depth_mm=19),
            ),
        )
        assert len(beam.face_features) == 2

    def test_beam_with_edge_features(self):
        beam = BeamSpec(
            name="post",
            length_mm=500,
            width_mm=76,
            thickness_mm=19,
            layers=3,
            edge_features=(
                Chamfer(edge="top", width_mm=3),
                Fillet(edge="bottom", radius_mm=6),
            ),
        )
        assert len(beam.edge_features) == 2

    def test_beam_with_end_features(self):
        beam = BeamSpec(
            name="rail",
            length_mm=500,
            width_mm=100,
            thickness_mm=19,
            layers=3,
            end_features=(Tenon(end="right", extension_mm=38, width_mm=100, height_mm=19),),
        )
        assert len(beam.end_features) == 1


class TestOuterLayerDetection:
    def test_is_outer_layer_first(self):
        beam = BeamSpec(name="test", length_mm=500, width_mm=100, thickness_mm=19, layers=3)
        assert beam._is_outer_layer(0) is True

    def test_is_outer_layer_last(self):
        beam = BeamSpec(name="test", length_mm=500, width_mm=100, thickness_mm=19, layers=3)
        assert beam._is_outer_layer(2) is True

    def test_is_outer_layer_middle(self):
        beam = BeamSpec(name="test", length_mm=500, width_mm=100, thickness_mm=19, layers=3)
        assert beam._is_outer_layer(1) is False

    def test_single_layer_is_outer(self):
        beam = BeamSpec(name="test", length_mm=500, width_mm=100, thickness_mm=19, layers=1)
        assert beam._is_outer_layer(0) is True


class TestEdgeFeatureLayerApplication:
    def test_outer_feature_applies_to_first_last(self):
        beam = BeamSpec(name="test", length_mm=500, width_mm=100, thickness_mm=19, layers=3)
        chamfer = Chamfer(edge="top", width_mm=3, layers="outer")
        assert beam._should_apply_edge_feature(chamfer, 0) is True
        assert beam._should_apply_edge_feature(chamfer, 1) is False
        assert beam._should_apply_edge_feature(chamfer, 2) is True

    def test_all_feature_applies_to_all(self):
        beam = BeamSpec(name="test", length_mm=500, width_mm=100, thickness_mm=19, layers=3)
        dado = EdgeDado(edge="top", position_mm=100, width_mm=19, depth_mm=9.5, layers="all")
        assert beam._should_apply_edge_feature(dado, 0) is True
        assert beam._should_apply_edge_feature(dado, 1) is True
        assert beam._should_apply_edge_feature(dado, 2) is True


class TestTenonLayerApplication:
    def test_center_tenon_applies_to_middle_only(self):
        beam = BeamSpec(name="test", length_mm=500, width_mm=100, thickness_mm=19, layers=3)
        tenon = Tenon(end="left", extension_mm=38, width_mm=100, height_mm=19, layers="center")
        assert beam._should_apply_tenon(tenon, 0) is False
        assert beam._should_apply_tenon(tenon, 1) is True
        assert beam._should_apply_tenon(tenon, 2) is False

    def test_outer_tenon_applies_to_first_last(self):
        beam = BeamSpec(name="test", length_mm=500, width_mm=100, thickness_mm=19, layers=3)
        tenon = Tenon(end="left", extension_mm=38, width_mm=100, height_mm=19, layers="outer")
        assert beam._should_apply_tenon(tenon, 0) is True
        assert beam._should_apply_tenon(tenon, 1) is False
        assert beam._should_apply_tenon(tenon, 2) is True

    def test_all_tenon_applies_to_all(self):
        beam = BeamSpec(name="test", length_mm=500, width_mm=100, thickness_mm=19, layers=3)
        tenon = Tenon(end="left", extension_mm=38, width_mm=100, height_mm=19, layers="all")
        assert beam._should_apply_tenon(tenon, 0) is True
        assert beam._should_apply_tenon(tenon, 1) is True
        assert beam._should_apply_tenon(tenon, 2) is True

    def test_explicit_indices_tenon(self):
        beam = BeamSpec(name="test", length_mm=500, width_mm=100, thickness_mm=19, layers=3)
        tenon = Tenon(end="left", extension_mm=38, width_mm=100, height_mm=19, layers=(1,))
        assert beam._should_apply_tenon(tenon, 0) is False
        assert beam._should_apply_tenon(tenon, 1) is True
        assert beam._should_apply_tenon(tenon, 2) is False


class TestExpandWithTenons:
    def test_center_tenons_extend_center_layer(self):
        beam = BeamSpec(
            name="rail",
            length_mm=600,
            width_mm=76,
            thickness_mm=19,
            layers=3,
            end_features=(
                Tenon(end="left", extension_mm=38, width_mm=76, height_mm=19, layers="center"),
                Tenon(end="right", extension_mm=38, width_mm=76, height_mm=19, layers="center"),
            ),
        )
        panels = beam.expand(sheet_size=1200)
        assert len(panels) == 3
        assert panels[0].width_mm == 600
        assert panels[1].width_mm == 676
        assert panels[2].width_mm == 600

    def test_outer_tenons_extend_outer_layers(self):
        beam = BeamSpec(
            name="rail",
            length_mm=600,
            width_mm=76,
            thickness_mm=19,
            layers=3,
            end_features=(Tenon(end="left", extension_mm=25, width_mm=76, height_mm=19, layers="outer"),),
        )
        panels = beam.expand(sheet_size=1200)
        assert len(panels) == 3
        assert panels[0].width_mm == 625
        assert panels[1].width_mm == 600
        assert panels[2].width_mm == 625

    def test_all_tenons_extend_all_layers(self):
        beam = BeamSpec(
            name="rail",
            length_mm=600,
            width_mm=76,
            thickness_mm=19,
            layers=3,
            end_features=(Tenon(end="left", extension_mm=20, width_mm=76, height_mm=19, layers="all"),),
        )
        panels = beam.expand(sheet_size=1200)
        assert len(panels) == 3
        assert panels[0].width_mm == 620
        assert panels[1].width_mm == 620
        assert panels[2].width_mm == 620

    def test_no_tenons_no_extension(self):
        beam = BeamSpec(
            name="rail",
            length_mm=600,
            width_mm=76,
            thickness_mm=19,
            layers=3,
        )
        panels = beam.expand(sheet_size=1200)
        assert len(panels) == 3
        assert all(p.width_mm == 600 for p in panels)

    def test_single_layer_center_tenon_not_applied(self):
        beam = BeamSpec(
            name="rail",
            length_mm=600,
            width_mm=76,
            thickness_mm=19,
            layers=1,
            end_features=(Tenon(end="left", extension_mm=38, width_mm=76, height_mm=19, layers="center"),),
        )
        panels = beam.expand(sheet_size=1200)
        assert len(panels) == 1
        assert panels[0].width_mm == 600
