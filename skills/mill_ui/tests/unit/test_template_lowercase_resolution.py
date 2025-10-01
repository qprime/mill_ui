from __future__ import annotations

from skills.mill_ui.compositions import resolve_templates


def test_lowercase_template_type_resolves():
    items = [
        {
            "kind": "template",
            "type": "insetframe",  # lowercase should still resolve
            "id": "f1",
            "params": {
                "aperture_w_mm": 100.0,
                "aperture_h_mm": 80.0,
                "lip_inset_mm": 6.0,
                "recess_extra_inset_mm": 2.0,
                "lip_depth_mm": 4.0,
                "recess_depth_mm": 10.0,
            },
        }
    ]
    resolved = resolve_templates(items, sheet_thickness_mm=18.0)
    # Expect at least outer profile to be present
    assert any(it.get("type") == "Rect" and it.get("feature", {}).get("type") == "profile" for it in resolved)

