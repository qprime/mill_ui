#!/usr/bin/env python3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from config.machine_loader import load_machine_by_name, load_endmills, get_machines_dir
from adapters.cnc_config_to_ir import machine_config_to_diagram_ir
from diagram_render import render_diagram_svg


def main():
    recipe_dir = Path(__file__).parent
    output_dir = recipe_dir / "output"
    output_dir.mkdir(exist_ok=True)

    endmills = load_endmills(get_machines_dir() / "endmills.yml")
    quarter_inch = next((e for e in endmills if "1/4" in e.name and "upcut" in e.name), endmills[0])

    machines = ["default", "shapeoko_xxl", "onefinity_woodworker"]

    for machine_name in machines:
        machine = load_machine_by_name(machine_name)

        diagram = machine_config_to_diagram_ir(
            machine,
            endmill=quarter_inch,
            show_dimensions=True,
            show_centerlines=True,
        )

        svg_dark = render_diagram_svg(diagram, theme="dark")
        (output_dir / f"{machine_name}_dark.svg").write_text(svg_dark)

        svg_print = render_diagram_svg(diagram, theme="print")
        (output_dir / f"{machine_name}_print.svg").write_text(svg_print)

        print(f"Generated diagrams for {machine.machine.name}")
        print(f"  Envelope: {machine.machine.envelope_width:.0f} x {machine.machine.envelope_height:.0f} mm")
        if machine.wasteboard:
            margins = machine.compute_margins()
            print(f"  Wasteboard: {machine.wasteboard.width_mm:.0f} x {machine.wasteboard.height_mm:.0f} mm")
            print(f"  Margins: L={margins['left']:.0f} R={margins['right']:.0f} T={margins['top']:.0f} B={margins['bottom']:.0f} mm")
        eff = machine.effective_envelope(quarter_inch.radius_mm)
        print(f"  Effective: ({eff[0]:.1f}, {eff[1]:.1f}) to ({eff[2]:.1f}, {eff[3]:.1f}) mm")
        print()


if __name__ == "__main__":
    main()
