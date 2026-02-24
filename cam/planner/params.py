from __future__ import annotations


def feeds_for(*, feed_xy: float, feed_z: float) -> tuple[float, float]:
    return float(feed_xy), float(feed_z)


def stepdown_for(*, tool_diameter: float, cap_mm: float | None = None) -> float:
    sd = 0.5 * float(tool_diameter)
    return min(sd, float(cap_mm)) if cap_mm is not None else sd


def stepover_for(*, tool_diameter: float, ratio: float = 0.4) -> float:
    return float(tool_diameter) * float(ratio)
