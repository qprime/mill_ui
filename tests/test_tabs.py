
from pml import parse_pml
from layout_ast.layout import LayoutAST, Sheet, Item, Geometry, Placement, Feature
from adapters.ast_to_removal import ast_to_removal_intents, item_to_removal_intent
from ir.removal_intent import TabConstraint


def test_pml_parse_profile_with_tabs():
    print("Running test_pml_parse_profile_with_tabs...")

    pml = """
sheet 450mm 650mm 19mm

rect cutout at 225mm,325mm size 400mm,600mm profile through outside tabs 4 height 3mm width 10mm
"""

    ast = parse_pml(pml)

    assert len(ast.items) == 1
    item = ast.items[0]


    assert item.feature.type == "profile"
    assert item.feature.depth == "through"
    assert item.feature.side == "outside"


    assert item.feature.tab_count == 4
    assert item.feature.tab_height_mm == 3.0
    assert item.feature.tab_width_mm == 10.0

    print("  ✓ PASS")
    return True


def test_pml_parse_profile_with_tabs_no_width():
    print("Running test_pml_parse_profile_with_tabs_no_width...")

    pml = """
sheet 450mm 650mm 19mm

rect cutout at 225mm,325mm size 400mm,600mm profile through outside tabs 4 height 3mm
"""

    ast = parse_pml(pml)

    item = ast.items[0]


    assert item.feature.tab_count == 4
    assert item.feature.tab_height_mm == 3.0
    assert item.feature.tab_width_mm is None

    print("  ✓ PASS")
    return True


def test_pml_parse_profile_with_tabs_inside():
    print("Running test_pml_parse_profile_with_tabs_inside...")

    pml = """
sheet 450mm 650mm 19mm

rect pocket_outline at 225mm,325mm size 300mm,500mm profile 6mm inside tabs 6 height 2mm width 8mm
"""

    ast = parse_pml(pml)

    item = ast.items[0]


    assert item.feature.type == "profile"
    assert item.feature.depth_mm == 6.0
    assert item.feature.side == "inside"
    assert item.feature.tab_count == 6
    assert item.feature.tab_height_mm == 2.0
    assert item.feature.tab_width_mm == 8.0

    print("  ✓ PASS")
    return True


def test_ast_construction_with_tabs():
    print("Running test_ast_construction_with_tabs...")

    ast = LayoutAST(
        sheet=Sheet(width_mm=450, height_mm=650, thickness_mm=19),
        items=(
            Item(
                kind="shape",
                type="Rect",
                geometry=Geometry(data={"w_mm": 400, "h_mm": 600}),
                placement=Placement(center_xy_mm=(225, 325)),
                feature=Feature(
                    type="profile",
                    depth="through",
                    side="outside",
                    tab_count=4,
                    tab_height_mm=3.0,
                    tab_width_mm=10.0,
                ),
                shape_id="cutout"
            ),
        )
    )

    item = ast.items[0]
    assert item.feature.tab_count == 4
    assert item.feature.tab_height_mm == 3.0
    assert item.feature.tab_width_mm == 10.0

    print("  ✓ PASS")
    return True


def test_ast_to_removal_intent_with_tabs():
    print("Running test_ast_to_removal_intent_with_tabs...")

    item = Item(
        kind="shape",
        type="Rect",
        geometry=Geometry(data={"w_mm": 400, "h_mm": 600}),
        placement=Placement(center_xy_mm=(225, 325)),
        feature=Feature(
            type="profile",
            depth="through",
            side="outside",
            tab_count=4,
            tab_height_mm=3.0,
            tab_width_mm=10.0,
        ),
        shape_id="cutout"
    )

    intent = item_to_removal_intent(item, sheet_thickness_mm=19.0)


    assert intent.depth_mm() == 19.0
    assert intent.metadata["hint_type"] == "profile"
    assert intent.metadata["side"] == "outside"


    assert intent.constraints.tabs is not None
    assert isinstance(intent.constraints.tabs, TabConstraint)
    assert intent.constraints.tabs.count == 4
    assert intent.constraints.tabs.height_mm == 3.0
    assert intent.constraints.tabs.width_mm == 10.0

    print("  ✓ PASS")
    return True


def test_ast_to_removal_intent_with_tabs_no_width():
    print("Running test_ast_to_removal_intent_with_tabs_no_width...")

    item = Item(
        kind="shape",
        type="Rect",
        geometry=Geometry(data={"w_mm": 400, "h_mm": 600}),
        placement=Placement(center_xy_mm=(225, 325)),
        feature=Feature(
            type="profile",
            depth="through",
            side="outside",
            tab_count=4,
            tab_height_mm=3.0,
            tab_width_mm=None,
        ),
        shape_id="cutout"
    )

    intent = item_to_removal_intent(item, sheet_thickness_mm=19.0)


    assert intent.constraints.tabs is not None
    assert intent.constraints.tabs.count == 4
    assert intent.constraints.tabs.height_mm == 3.0
    assert intent.constraints.tabs.width_mm is None

    print("  ✓ PASS")
    return True


def test_full_pipeline_pml_to_removal_intent():
    print("Running test_full_pipeline_pml_to_removal_intent...")

    pml = """
sheet 450mm 650mm 19mm

rect door at 225mm,325mm size 400mm,600mm profile through outside tabs 4 height 3mm width 10mm
rect panel at 225mm,325mm size 300mm,500mm pocket 6mm
"""

    ast = parse_pml(pml)
    intents = ast_to_removal_intents(ast)


    assert len(intents) == 2


    profile_intent = intents[0]
    assert profile_intent.metadata["hint_type"] == "profile"
    assert profile_intent.constraints.tabs is not None
    assert profile_intent.constraints.tabs.count == 4
    assert profile_intent.constraints.tabs.height_mm == 3.0
    assert profile_intent.constraints.tabs.width_mm == 10.0


    pocket_intent = intents[1]
    assert pocket_intent.metadata["hint_type"] == "pocket"
    assert pocket_intent.constraints.tabs is None

    print("  ✓ PASS")
    return True


def test_pml_roundtrip_with_tabs():
    print("Running test_pml_roundtrip_with_tabs...")

    from pml import format_pml

    pml_in = """sheet 450mm 650mm 19mm

rect cutout at 225mm,325mm size 400mm,600mm profile through outside tabs 4 height 3mm width 10mm
"""

    ast = parse_pml(pml_in)
    pml_out = format_pml(ast)
    ast2 = parse_pml(pml_out)


    item1 = ast.items[0]
    item2 = ast2.items[0]

    assert item1.feature.tab_count == item2.feature.tab_count
    assert item1.feature.tab_height_mm == item2.feature.tab_height_mm
    assert item1.feature.tab_width_mm == item2.feature.tab_width_mm

    print("  ✓ PASS")
    return True


def run_all_tests():
    tests = [
        test_pml_parse_profile_with_tabs,
        test_pml_parse_profile_with_tabs_no_width,
        test_pml_parse_profile_with_tabs_inside,
        test_ast_construction_with_tabs,
        test_ast_to_removal_intent_with_tabs,
        test_ast_to_removal_intent_with_tabs_no_width,
        test_full_pipeline_pml_to_removal_intent,
        test_pml_roundtrip_with_tabs,
    ]

    print("\n" + "="*60)
    print("Running Tab Tests")
    print("="*60 + "\n")

    passed = 0
    failed = 0

    for test_fn in tests:
        try:
            if test_fn():
                passed += 1
        except AssertionError as e:
            print(f"  ✗ FAIL: {e}")
            failed += 1
        except Exception as e:
            print(f"  ✗ ERROR: {e}")
            failed += 1

    print("\n" + "="*60)
    print(f"Results: {passed} passed, {failed} failed")
    print("="*60 + "\n")

    return failed == 0


if __name__ == "__main__":
    import sys
    success = run_all_tests()
    sys.exit(0 if success else 1)
