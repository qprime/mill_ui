#!/usr/bin/env python3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from adapters.cnc_config_to_ir import machine_config_to_diagram_ir
from config.machine_loader import get_machines_dir, load_endmills, load_machine_by_name
from diagram_render import render_diagram_svg

def main():
    recipe_dir = Path(__file__).parent
    output_dir = recipe_dir / "output"
    output_dir.mkdir(exist_ok=True)

    endmills = load_endmills(get_machines_dir() / "endmills.yml")
    quarter_inch = next((e for e in endmills if "1/4" in e.name and "upcut" in e.name), endmills[0])

    altmill = load_machine_by_name("altmill_4x4")
    diagram = machine_config_to_diagram_ir(
        altmill,
        show_dimensions=False,
        show_centerlines=True,
    )

    svg_dark = render_diagram_svg(diagram, theme="dark")
    (output_dir / "altmill_4x4_dark.svg").write_text(svg_dark)

    svg_print = render_diagram_svg(diagram, theme="print")
    (output_dir / "altmill_4x4_print.svg").write_text(svg_print)

    wb = altmill.spoilboard
    tt = altmill.t_track
    margins = altmill.compute_margins()

    print(f"Generated diagrams for {altmill.machine.name}")
    print(f"  Envelope: {altmill.machine.envelope_width:.0f} x {altmill.machine.envelope_height:.0f} mm")
    print(f"  Spoilboard: {wb.width_mm:.1f} x {wb.height_mm:.0f} mm")
    print(
        f"  Margins: L={margins['left']:.0f} R={margins['right']:.0f} T={margins['top']:.0f} B={margins['bottom']:.0f} mm"
    )
    if tt:
        print(f"  T-track: L={tt.left_mm} R={tt.right_mm} F={tt.front_mm} B={tt.back_mm} mm")
    print()

    genmitsu = load_machine_by_name("genmitsu_4040_pro")
    diagram_g = machine_config_to_diagram_ir(
        genmitsu,
        endmill=quarter_inch,
        show_dimensions=True,
        show_centerlines=True,
    )

    svg_dark = render_diagram_svg(diagram_g, theme="dark")
    (output_dir / "genmitsu_4040_pro_dark.svg").write_text(svg_dark)

    svg_print = render_diagram_svg(diagram_g, theme="print")
    (output_dir / "genmitsu_4040_pro_print.svg").write_text(svg_print)

    print(f"Generated diagrams for {genmitsu.machine.name}")
    print(f"  Envelope: {genmitsu.machine.envelope_width:.0f} x {genmitsu.machine.envelope_height:.0f} mm")
    if genmitsu.spoilboard:
        gm = genmitsu.compute_margins()
        print(f"  Spoilboard: {genmitsu.spoilboard.width_mm:.0f} x {genmitsu.spoilboard.height_mm:.0f} mm")
        print(f"  Margins: L={gm['left']:.0f} R={gm['right']:.0f} T={gm['top']:.0f} B={gm['bottom']:.0f} mm")
    eff_g = genmitsu.effective_envelope(quarter_inch.radius_mm)
    print(f"  Effective envelope: ({eff_g[0]:.1f}, {eff_g[1]:.1f}) to ({eff_g[2]:.1f}, {eff_g[3]:.1f}) mm")
    print()


if __name__ == "__main__":
    main()
