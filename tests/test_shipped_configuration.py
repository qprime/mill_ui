from __future__ import annotations

import pytest

from cam.compilation import compilation_context, default_machine_name
from cam.planner.passes.tools import tools_for_role
from config.machine_loader import load_machine_by_name

pytestmark = pytest.mark.shipped_configuration


def test_shipped_production_defaults_reference_a_supported_preset():
    machine = load_machine_by_name(default_machine_name())
    assert machine.cutting_preset is not None
    context = compilation_context("mdf", machine_config=machine)
    assert context.profile_diameter_mm is not None
    assert tools_for_role(context.tools, "pocket")


def test_shipped_altmill_seed_parameters_are_explicit():
    machine = load_machine_by_name("altmill_4x4")
    context = compilation_context("mdf", machine_config=machine)
    profile = tools_for_role(context.tools, "profile")[0]
    pocket = tools_for_role(context.tools, "pocket")[0]
    assert profile.name == "Example 3/8 carbide mortise compression"
    assert pocket.name == "Example 3/8 PCD straight plunge"
    assert (profile.rpm, profile.feed_xy, profile.feed_z, profile.depth_per_pass) == (18000, 4500, 1125, 6)
    assert (pocket.rpm, pocket.feed_xy, pocket.feed_z, pocket.depth_per_pass, pocket.stepover_percent) == (
        18000,
        2520,
        630,
        6,
        40,
    )


def test_shipped_genmitsu_requires_its_own_supported_cutting_data():
    machine = load_machine_by_name("genmitsu_4040_pro")
    with pytest.raises(ValueError, match=r"Genmitsu.*genmitsu.*mdf.*unsupported material"):
        compilation_context("mdf", machine_config=machine)
