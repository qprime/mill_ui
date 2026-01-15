
from pathlib import Path
from pml.compositional_parser import parse_compositional_pml
from resolution.layout_resolver import resolve_layout
from adapters.ast_to_removal import ast_to_removal_intents
from adapters.removal_to_planner import removal_intents_to_v1_hints
from cam.config import Config
from cam.model.machine import Machine
from cam.model.material import Material
from cam.model.stock import Stock
from cam.planner.passes import plan_passes
from cam.post.gcode import write_gcode
import json


pml_text = Path('golden_trace_input.pml').read_text()


comp_ast = parse_compositional_pml(pml_text)


flat_ast = resolve_layout(comp_ast)


intents = ast_to_removal_intents(flat_ast)


hints = removal_intents_to_v1_hints(intents, kerf_width_mm=3.175, min_channel_width_mm=6.0)


tool_db = [
    {
        "name": "1_8_endmill",
        "diameter": 3.175,
        "kind": "flat",
        "rpm": 14000,
        "feed_xy": 900,
        "feed_z": 300,
    }
]

config = Config(
    safe_z_mm=5.0,
    merge_epsilon_mm=0.1,
    pocket_finish_perimeter=True,
)

material = Material(name="MDF")
machine = Machine()
stock = Stock(width=450.0, height=650.0, thickness=19.0)

passes, summary = plan_passes(
    hints,
    config=config,
    tool_db=tool_db,
    material=material,
    machine=machine,
    stock=stock,
    safe_z=5.0,
)

print('=== STEP 5: Planner Operations ===')
print(f'Total passes: {len(passes)}\n')
for i, pass_dict in enumerate(passes):
    print(f'Pass {i}: {pass_dict["op"]}')
    print(f'  Tool: {pass_dict["tool"]["name"]} (diameter={pass_dict["tool"]["diameter"]}mm)')
    print(f'  Move count: {len(pass_dict["moves"])}')
    print(f'  Filename: {pass_dict["filename"]}')


if passes:
    print('\n=== STEP 6: G-code Sample (first pass, first 30 lines) ===')
    first_pass = passes[0]
    gcode = write_gcode(
        first_pass["moves"],
        unit="mm",
        prec=3,
        safe_z=5.0,
        header=["G90", "G21", "G17"],
        footer=["M5", "M2"],
    )
    lines = gcode.split('\n')[:30]
    for i, line in enumerate(lines, 1):
        print(f'{i:3d}: {line}')
    if len(gcode.split('\n')) > 30:
        print(f'... ({len(gcode.split("\n")) - 30} more lines)')
