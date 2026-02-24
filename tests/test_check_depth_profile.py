from __future__ import annotations

from ir.removal_intent import (
    BevelSpec,
    Bounds2D,
    DepthProfile,
    RemovalIntent,
)
from validation.removal_checks import check_depth_profile


def _intent(
    mode: str = "constant",
    z_top: float = 0.0,
    z_bottom: float = -5.0,
    bevel: BevelSpec | None = None,
    **depth_kwargs,
) -> RemovalIntent:
    if mode == "linear_gradient":
        dp = DepthProfile.linear_gradient(
            z_top=z_top,
            z_bottom=z_bottom,
            direction_deg=depth_kwargs.get("direction_deg", 0.0),
        )
    elif mode == "v_carve":
        dp = DepthProfile.v_carve(
            z_top=z_top,
            z_bottom=z_bottom,
            v_angle_deg=depth_kwargs.get("v_angle_deg", 90.0),
        )
    else:
        dp = DepthProfile.constant(z_top=z_top, z_bottom=z_bottom)

    return RemovalIntent(
        region_id="test_region",
        bounds=Bounds2D(x_min=0, x_max=50, y_min=0, y_max=50),
        depth_profile=dp,
        edge_feature=bevel,
    )


class TestLinearGradientMode:
    def test_gradient_within_thickness(self):
        intent = _intent(mode="linear_gradient", z_bottom=-5.0)
        result = check_depth_profile(intent, sheet_thickness_mm=12.0)
        assert result.is_valid()
        assert len(result.errors) == 0

    def test_gradient_exceeds_thickness(self):
        intent = _intent(mode="linear_gradient", z_bottom=-15.0)
        result = check_depth_profile(intent, sheet_thickness_mm=12.0)
        assert not result.is_valid()
        assert len(result.errors) == 1
        assert "Gradient depth" in result.errors[0].message

    def test_gradient_at_exactly_thickness(self):
        intent = _intent(mode="linear_gradient", z_bottom=-12.0)
        result = check_depth_profile(intent, sheet_thickness_mm=12.0)
        assert result.is_valid()


class TestVCarveMode:
    def test_v_carve_matching_angle(self):
        intent = _intent(mode="v_carve", v_angle_deg=90.0)
        result = check_depth_profile(
            intent,
            sheet_thickness_mm=12.0,
            available_v_angles=[60.0, 90.0, 120.0],
        )
        assert result.is_valid()

    def test_v_carve_no_matching_angle(self):
        intent = _intent(mode="v_carve", v_angle_deg=90.0)
        result = check_depth_profile(
            intent,
            sheet_thickness_mm=12.0,
            available_v_angles=[60.0, 120.0],
        )
        assert not result.is_valid()
        assert len(result.errors) == 1
        assert "V-bit" in result.errors[0].message

    def test_v_carve_close_angle_match(self):
        intent = _intent(mode="v_carve", v_angle_deg=90.0)
        result = check_depth_profile(
            intent,
            sheet_thickness_mm=12.0,
            available_v_angles=[89.5],
        )
        assert result.is_valid()

    def test_v_carve_no_available_angles_skips_check(self):
        intent = _intent(mode="v_carve", v_angle_deg=90.0)
        result = check_depth_profile(intent, sheet_thickness_mm=12.0)
        assert result.is_valid()

    def test_v_carve_depth_exceeds_material(self):
        intent = _intent(mode="v_carve", z_bottom=-15.0, v_angle_deg=90.0)
        result = check_depth_profile(intent, sheet_thickness_mm=12.0)
        assert result.is_valid()
        assert len(result.warnings) == 1
        assert "may exceed material" in result.warnings[0].message

    def test_v_carve_depth_within_material(self):
        intent = _intent(mode="v_carve", z_bottom=-5.0, v_angle_deg=90.0)
        result = check_depth_profile(intent, sheet_thickness_mm=12.0)
        assert len(result.warnings) == 0


class TestBevelGeometry:
    def test_bevel_achievable(self):
        intent = _intent(bevel=BevelSpec(width_mm=10.0, angle_deg=45.0, inner_depth_mm=9.0))
        result = check_depth_profile(intent, sheet_thickness_mm=12.0)
        assert len(result.warnings) == 0

    def test_bevel_unachievable(self):
        intent = _intent(bevel=BevelSpec(width_mm=5.0, angle_deg=30.0, inner_depth_mm=20.0))
        result = check_depth_profile(intent, sheet_thickness_mm=12.0)
        assert len(result.warnings) == 1
        assert "Bevel inner depth" in result.warnings[0].message

    def test_no_bevel_metadata(self):
        intent = _intent()
        result = check_depth_profile(intent, sheet_thickness_mm=12.0)
        assert len(result.warnings) == 0
        assert result.is_valid()

    def test_bevel_zero_angle_skips(self):
        intent = _intent(bevel=BevelSpec(width_mm=10.0, angle_deg=0, inner_depth_mm=20.0))
        result = check_depth_profile(intent, sheet_thickness_mm=12.0)
        assert len(result.warnings) == 0

    def test_bevel_90_angle_skips(self):
        intent = _intent(bevel=BevelSpec(width_mm=10.0, angle_deg=90, inner_depth_mm=20.0))
        result = check_depth_profile(intent, sheet_thickness_mm=12.0)
        assert len(result.warnings) == 0


class TestConstantMode:
    def test_constant_no_checks(self):
        intent = _intent(mode="constant")
        result = check_depth_profile(intent, sheet_thickness_mm=12.0)
        assert result.is_valid()
        assert len(result.warnings) == 0
