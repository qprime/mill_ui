from __future__ import annotations

import warnings

from assembly.panel import PanelSpec
from assembly.partitioner import (
    decode_panel_id,
    encode_panel_id,
    partition_panels,
)


def _panel(name: str, w: float, h: float) -> PanelSpec:
    return PanelSpec(name=name, width_mm=w, height_mm=h, thickness_mm=19.0)


class TestEncodeDecode:
    def test_roundtrip(self):
        for idx, name in [(0, "left"), (5, "shelf_1"), (99, "back_panel")]:
            encoded = encode_panel_id(idx, name)
            dec_idx, dec_name = decode_panel_id(encoded)
            assert dec_idx == idx
            assert dec_name == name

    def test_name_with_separator_chars(self):
        encoded = encode_panel_id(3, "a::b")
        idx, name = decode_panel_id(encoded)
        assert idx == 3
        assert name == "a::b"


class TestPartitionPanels:
    def test_all_fit_single_sheet(self):
        panels = [_panel("a", 100, 100), _panel("b", 100, 100), _panel("c", 100, 100), _panel("d", 100, 100)]
        result = partition_panels(panels, usable_width_mm=1200, usable_height_mm=1200, gap_mm=10.0)
        assert len(result.sheets) == 1
        assert len(result.sheets[0]) == 4
        assert len(result.unplaceable) == 0

    def test_overflow_to_two_sheets(self):
        panels = [_panel(f"p{i}", 400, 400) for i in range(6)]
        result = partition_panels(panels, usable_width_mm=900, usable_height_mm=900, gap_mm=10.0)
        assert len(result.sheets) == 2
        total = sum(len(s) for s in result.sheets)
        assert total == 6
        assert len(result.unplaceable) == 0

    def test_single_panel_per_sheet(self):
        panels = [_panel("big_a", 1100, 1100), _panel("big_b", 1100, 1100)]
        result = partition_panels(panels, usable_width_mm=1200, usable_height_mm=1200, gap_mm=10.0)
        assert len(result.sheets) == 2
        assert all(len(s) == 1 for s in result.sheets)

    def test_unplaceable_panel(self):
        panels = [_panel("too_wide", 1500, 100)]
        result = partition_panels(panels, usable_width_mm=1200, usable_height_mm=1200, gap_mm=10.0)
        assert len(result.sheets) == 0
        assert len(result.unplaceable) == 1
        assert result.unplaceable[0].name == "too_wide"

    def test_panel_identity_preserved(self):
        from assembly.panel import DadoSpec, Edge, NotchSpec

        notch = NotchSpec(edge=Edge.BOTTOM, u_start_mm=10.0, u_len_mm=20.0, depth_mm=6.0)
        dado = DadoSpec(
            position_from_edge_mm=50.0,
            width_mm=6.0,
            depth_mm=3.0,
            edge="left",
            orientation="vertical",
        )
        panel = PanelSpec(
            name="detailed",
            width_mm=200,
            height_mm=300,
            thickness_mm=19.0,
            notches=(notch,),
            dados=(dado,),
        )
        result = partition_panels([panel], usable_width_mm=1200, usable_height_mm=1200)
        assert len(result.sheets) == 1
        recovered = result.sheets[0][0]
        assert recovered is panel
        assert recovered.notches == (notch,)
        assert recovered.dados == (dado,)

    def test_no_rotation(self):
        panel = _panel("tall", 100, 1100)
        result = partition_panels(
            [panel],
            usable_width_mm=1200,
            usable_height_mm=200,
            gap_mm=0.0,
        )
        assert len(result.unplaceable) == 1

    def test_deterministic(self):
        panels = [_panel(f"p{i}", 300, 200) for i in range(8)]
        r1 = partition_panels(panels, usable_width_mm=700, usable_height_mm=700, gap_mm=10.0)
        r2 = partition_panels(panels, usable_width_mm=700, usable_height_mm=700, gap_mm=10.0)
        assert len(r1.sheets) == len(r2.sheets)
        for s1, s2 in zip(r1.sheets, r2.sheets, strict=True):
            assert [p.name for p in s1] == [p.name for p in s2]

    def test_gap_inflation_one_sided(self):
        result_no_gap = partition_panels(
            [_panel("a", 500, 500), _panel("b", 500, 500)],
            usable_width_mm=1010,
            usable_height_mm=510,
            gap_mm=0.0,
        )
        assert len(result_no_gap.sheets) == 1
        assert len(result_no_gap.sheets[0]) == 2

        result_with_gap = partition_panels(
            [_panel("a", 500, 500), _panel("b", 500, 500)],
            usable_width_mm=1010,
            usable_height_mm=520,
            gap_mm=11.0,
        )
        assert len(result_with_gap.sheets) == 2

    def test_kerf_mm_zero_no_warning(self):
        panels = [_panel("a", 100, 100)]
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            partition_panels(panels, usable_width_mm=1200, usable_height_mm=1200)

    def test_clearance_reduces_usable_area(self):
        panel = _panel("edge", 1190, 100)
        result_no_clear = partition_panels(
            [panel],
            usable_width_mm=1200,
            usable_height_mm=1200,
            gap_mm=0.0,
            edge_clearance_mm=0.0,
        )
        assert len(result_no_clear.sheets) == 1

        result_with_clear = partition_panels(
            [panel],
            usable_width_mm=1200,
            usable_height_mm=1200,
            gap_mm=0.0,
            edge_clearance_mm=10.0,
        )
        assert len(result_with_clear.unplaceable) == 1
