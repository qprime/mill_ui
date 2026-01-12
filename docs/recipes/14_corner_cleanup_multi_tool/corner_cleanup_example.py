#!/usr/bin/env python3
"""Demo: Shaker door with multi-tool corner cleanup."""

from layout_ast.layout import LayoutAST, Sheet, Item, Geometry, Placement, Feature
from adapters.ast_to_removal import ast_to_removal_intents
from adapters.removal_to_planner import removal_intents_to_v1_hints
from cam.config import Config
from cam.planner.passes import plan_passes
from cam.post.gcode import write_gcode
from cam.model.stock import Stock
from cam.model.material import Material
from cam.model.machine import Machine

# Design: Shaker door 400x600mm, panel recess 300x500mm
ast = LayoutAST(
    sheet=Sheet(width_mm=450, height_mm=650, thickness_mm=19),
    items=(
        # Panel pocket (with corner cleanup)
        Item(
            kind="shape",
            type="Rect",
            geometry=Geometry(data={"w_mm": 300, "h_mm": 500}),
            placement=Placement(center_xy_mm=(225, 325)),
            feature=Feature(
                type="pocket",
                depth=6.0,
                corner_cleanup_tool_diameter_mm=3.175  # 1/8" corners
            ),
            shape_id="panel"
        ),
        # Door outer profile
        Item(
            kind="shape",
            type="Rect",
            geometry=Geometry(data={"w_mm": 400, "h_mm": 600}),
            placement=Placement(center_xy_mm=(225, 325)),
            feature=Feature(type="profile", side="outside", depth="through"),
            shape_id="door_outer"
        ),
    )
)

# Convert to IR and hints
intents = ast_to_removal_intents(ast)
hints = removal_intents_to_v1_hints(intents, kerf_width_mm=3.175, min_channel_width_mm=6.0)

# Multi-tool database
tool_db = [
    {"name": "1/8_endmill", "diameter": 3.175, "kind": "flat", "rpm": 14000, "feed_xy": 900, "feed_z": 300},
    {"name": "1/4_endmill", "diameter": 6.35, "kind": "flat", "rpm": 12000, "feed_xy": 1200, "feed_z": 400},
    {"name": "3/8_endmill", "diameter": 9.525, "kind": "flat", "rpm": 10000, "feed_xy": 1500, "feed_z": 500},
]

# Configuration
config = Config(safe_z_mm=6.0, pocket_finish_perimeter=True)
material = Material(name="plywood")
machine = Machine()
stock = Stock(width=450, height=650, thickness=19)

# Plan passes
passes, summary = plan_passes(
    hints,
    config=config,
    tool_db=tool_db,
    material=material,
    machine=machine,
    stock=stock,
)

# Generate G-code
print("Generating G-code for multi-tool job:")
for pass_rec in passes:
    gcode = write_gcode(pass_rec["moves"], safe_z=config.safe_z_mm)
    filename = pass_rec["filename"]

    with open(filename, 'w') as f:
        f.write(gcode)

    op = pass_rec["op"]
    tool_name = pass_rec["tool"]["name"]
    line_count = len(gcode.splitlines())

    print(f"  {filename:30s} ({op:15s} with {tool_name}, {line_count:5d} lines)")

print("\nWorkflow:")
print("  1. Load 3/8\" endmill → Run pocket-9.53mm.nc")
print("  2. Change to 1/8\" endmill → Run corner_cleanup-3.18mm.nc")
print("  3. Change to 1/4\" endmill → Run profile-6.35mm.nc")
print("  4. Done!")
