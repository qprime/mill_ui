from adapters.ast_to_removal import ast_to_removal_intents
from layout_ast.layout import Feature, Geometry, Item, LayoutAST, Placement, Sheet
from pml import format_pml, parse_pml


def example_simple_cutout_with_tabs():
    print("\n=== Example 1: Simple Cutout with Tabs ===\n")

    ast = LayoutAST(
        sheet=Sheet(width_mm=600, height_mm=400, thickness_mm=19),
        items=(
            Item(
                kind="shape",
                type="Rect",
                geometry=Geometry(data={"w_mm": 400, "h_mm": 250}),
                placement=Placement(center_xy_mm=(300, 200)),
                feature=Feature(
                    type="profile",
                    depth="through",
                    side="outside",
                    tab_count=4,
                    tab_height_mm=3.0,
                    tab_width_mm=12.0,
                ),
                shape_id="cutout",
            ),
        ),
    )

    intents = ast_to_removal_intents(ast)
    intent = intents[0]

    print(f"Profile: {intent.region_id}")
    print(f"  Bounds: {intent.bounds.x_min:.0f}mm to {intent.bounds.x_max:.0f}mm (X)")
    print(f"          {intent.bounds.y_min:.0f}mm to {intent.bounds.y_max:.0f}mm (Y)")
    print(f"  Depth: {intent.depth_mm():.1f}mm")
    if intent.constraints.tabs:
        print(f"  Tabs: {intent.constraints.tabs.count} tabs")
        print(f"    Height: {intent.constraints.tabs.height_mm:.1f}mm")
        print(f"    Width: {intent.constraints.tabs.width_mm:.1f}mm")

    pml = format_pml(ast)
    print(f"\nPML output:\n{pml}")


def example_multiple_tabs():
    print("\n=== Example 2: Multiple Tab Configurations ===\n")

    pml = """
sheet 800mm 600mm 19mm


rect small at 200mm,150mm size 150mm,100mm profile through outside tabs 3 height 2mm width 8mm


rect medium at 200mm,400mm size 250mm,150mm profile through outside tabs 4 height 3mm width 12mm


rect large at 550mm,300mm size 400mm,250mm profile through outside tabs 6 height 4mm width 15mm
"""

    ast = parse_pml(pml)
    intents = ast_to_removal_intents(ast)

    for i, intent in enumerate(intents, 1):
        print(f"Part {i}: {intent.region_id}")
        if intent.constraints.tabs:
            tabs = intent.constraints.tabs
            print(f"  {tabs.count} tabs x {tabs.height_mm:.1f}mm high x {tabs.width_mm:.1f}mm wide")
        print()


def example_tabs_with_optional_width():
    print("\n=== Example 3: Tabs with Default Width ===\n")

    pml = """
sheet 600mm 400mm 19mm


rect cutout at 300mm,200mm size 400mm,250mm profile through outside tabs 4 height 3mm
"""

    ast = parse_pml(pml)
    intent = ast_to_removal_intents(ast)[0]

    print(f"Profile: {intent.region_id}")
    if intent.constraints.tabs:
        tabs = intent.constraints.tabs
        print(f"  Tabs: {tabs.count}")
        print(f"  Height: {tabs.height_mm:.1f}mm")
        print(f"  Width: {tabs.width_mm if tabs.width_mm else 'default (2x tool diameter)'}")


def example_inside_profile_with_tabs():
    print("\n=== Example 4: Inside Profile with Tabs ===\n")

    pml = """
sheet 600mm 400mm 19mm


rect pocket_outline at 300mm,200mm size 300mm,200mm profile 6mm inside tabs 4 height 2mm width 10mm
"""

    ast = parse_pml(pml)
    intent = ast_to_removal_intents(ast)[0]

    print(f"Profile: {intent.region_id}")
    print(f"  Side: {intent.side or 'outside'}")
    print(f"  Depth: {intent.depth_mm():.1f}mm")
    if intent.constraints.tabs:
        tabs = intent.constraints.tabs
        print(f"  Tabs: {tabs.count} x {tabs.height_mm:.1f}mm x {tabs.width_mm:.1f}mm")


if __name__ == "__main__":
    print("=" * 70)
    print("Recipe: Profile Cuts with Holding Tabs")
    print("=" * 70)

    example_simple_cutout_with_tabs()
    example_multiple_tabs()
    example_tabs_with_optional_width()
    example_inside_profile_with_tabs()

    print("\n" + "=" * 70)
    print("Tab Usage Guidelines:")
    print("=" * 70)
    print("""
1. Tab Count:
   - Small parts (< 200mm): 3 tabs minimum
   - Medium parts (200-400mm): 4 tabs recommended
   - Large parts (> 400mm): 6+ tabs for secure holding

2. Tab Height:
   - Standard: 2-4mm (typically 3mm for 19mm stock)
   - Should be less than material thickness
   - Higher tabs = stronger holding, harder to break free

3. Tab Width:
   - Typical: 8-15mm wide
   - Narrower tabs easier to break/sand clean
   - Wider tabs provide better support
   - If omitted, defaults to 2x tool diameter (min 6mm)

4. Placement:
   - Tabs are automatically distributed evenly around perimeter
   - System calculates optimal positions based on geometry

5. Limitations:
   - Cannot combine tabs with onion-skin roughing strategy
   - Tabs only supported on profile cuts (not pockets/holes)
""")
