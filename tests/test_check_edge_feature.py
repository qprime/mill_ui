from __future__ import annotations

from ir.removal_intent import (
    Bounds2D,
    DepthProfile,
    RemovalIntent,
    RoundoverSpec,
)
from validation.removal_checks import check_edge_feature


def _intent(edge_feature=None) -> RemovalIntent:
    return RemovalIntent(
        region_id="test_region",
        bounds=Bounds2D(x_min=0, x_max=50, y_min=0, y_max=50),
        depth_profile=DepthProfile.constant(z_top=0, z_bottom=-5.0),
        edge_feature=edge_feature,
    )


class TestCheckEdgeFeatureRoundover:
    def test_valid_roundover(self):
        intent = _intent(edge_feature=RoundoverSpec(radius_mm=6.0))
        result = check_edge_feature(intent, sheet_thickness_mm=19.0)
        assert result.is_valid()
        assert len(result.errors) == 0

    def test_zero_radius_error(self):
        intent = _intent(edge_feature=RoundoverSpec(radius_mm=0.0))
        result = check_edge_feature(intent, sheet_thickness_mm=19.0)
        assert not result.is_valid()
        assert any("positive" in e.message.lower() for e in result.errors)

    def test_negative_radius_error(self):
        intent = _intent(edge_feature=RoundoverSpec(radius_mm=-3.0))
        result = check_edge_feature(intent, sheet_thickness_mm=19.0)
        assert not result.is_valid()
        assert any("positive" in e.message.lower() for e in result.errors)

    def test_radius_exceeds_thickness_error(self):
        intent = _intent(edge_feature=RoundoverSpec(radius_mm=25.0))
        result = check_edge_feature(intent, sheet_thickness_mm=19.0)
        assert not result.is_valid()
        assert any("exceeds sheet thickness" in e.message for e in result.errors)

    def test_radius_at_thickness_ok(self):
        intent = _intent(edge_feature=RoundoverSpec(radius_mm=19.0))
        result = check_edge_feature(intent, sheet_thickness_mm=19.0)
        assert result.is_valid()

    def test_none_spec_returns_valid(self):
        intent = _intent(edge_feature=None)
        result = check_edge_feature(intent, sheet_thickness_mm=19.0)
        assert result.is_valid()
