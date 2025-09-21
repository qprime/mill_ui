from __future__ import annotations

import pytest

from skills.mill_ui.cad.ingest.sanitize import canonicalize_item, canonicalize_items


def test_canonicalize_items_normalises_types_and_values() -> None:
    items = [
        {"kind": "Shape", "type": "Rectangle", "geometry": {"w_mm": "10", "h_mm": 5}},
        {"kind": "shape", "type": "CIRCLE", "geometry": {"radius_mm": 3}},
        {"kind": "shape", "type": "Polyline", "geometry": {"points": [(0, 0), (1, 1)]}},
    ]

    canonical = canonicalize_items(items)

    assert canonical[0]["type"] == "rect"
    assert canonical[1]["type"] == "circle"
    assert canonical[2]["type"] == "polyline"
    assert canonical[0]["kind"] == "shape"
    assert canonical[0]["geometry"]["w_mm"] == "10"


def test_canonicalize_item_requires_geometry_fields() -> None:
    with pytest.raises(ValueError):
        canonicalize_item({"kind": "shape", "type": "rect", "geometry": {"w_mm": 10}})

    with pytest.raises(ValueError):
        canonicalize_item({"kind": "shape", "type": "circle", "geometry": {}})

    with pytest.raises(ValueError):
        canonicalize_item({"kind": "shape", "type": "polyline", "geometry": {"points": [(0,)]}})
