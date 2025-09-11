import unittest
from skills.mill_ui.cad.layout.panel import Panel
from skills.mill_ui.api.cad import apply_grid_layout
from skills.mill_ui.api.cam import build_cam_hints

class TestHints(unittest.TestCase):
    def test_door_expansion_profiles_pockets(self):
        panel = Panel(width=600, height=300, thickness=12)
        # Single door item
        items = [{
            "kind": "door",
            "id": "D1",
            "params": {
                "outer_w": 200.0, "outer_h": 100.0,
                "stile_w": 20.0, "rail_h": 25.0,
                "panel_recess": 3.0
            }
        }]
        placements = apply_grid_layout(panel, items, rows=1, cols=1, border=10, fit="tight")
        # mimic resolved items (add placement to each item)
        resolved = []
        for pl in placements:
            item = dict(pl["item"])
            item["placement"] = {"center_xy_mm": pl["center_xy_mm"]}
            resolved.append(item)
        hints = build_cam_hints(items_resolved=resolved, sheet_thickness=panel.thickness, kerf_width_mm=3.175)

        # Check outer profile present
        profs = [p for p in hints["profiles"] if p["shape"]=="Rect"]
        self.assertTrue(any(abs(p["geometry"]["w_mm"]-200.0)<1e-6 and abs(p["geometry"]["h_mm"]-100.0)<1e-6 for p in profs))
        # Check pocket present with inner dims
        pockets = hints["pockets"]
        self.assertTrue(any(abs(p["geometry"]["w_mm"]-(200-2*20))<1e-6 and abs(p["geometry"]["h_mm"]-(100-2*25))<1e-6 for p in pockets))
        # Depths
        self.assertTrue(any(abs(p["depth_mm"]-panel.thickness)<1e-6 for p in profs))
        self.assertTrue(any(abs(p["depth_mm"]-3.0)<1e-6 for p in pockets))

    def test_pass_through_shape(self):
        panel = Panel(width=200, height=200, thickness=12)
        items = [{
            "kind": "shape",
            "id": "S1",
            "type": "Circle",
            "geometry": {"diameter_mm": 10},
            "feature": {"type": "hole", "depth": "through"}
        }]
        pl = apply_grid_layout(panel, items, rows=1, cols=1, fit="tight")
        resolved = []
        for r in pl:
            it = dict(r["item"])
            it["placement"] = {"center_xy_mm": r["center_xy_mm"]}
            resolved.append(it)
        hints = build_cam_hints(items_resolved=resolved, sheet_thickness=panel.thickness)
        self.assertTrue(any(rec["shape"]=="Circle" for rec in hints["holes"]))
