from nesting.sheet_packer import pack_sheets
from nesting.types import PartSpec, SheetSpec


def test_single_part_single_sheet():
    parts = [PartSpec(name="door", width_mm=400, height_mm=600, quantity=1)]
    sheet = SheetSpec(width_mm=1000, height_mm=1000, thickness_mm=19)

    result = pack_sheets(parts, sheet)

    assert result.total_sheets == 1
    assert result.total_parts == 1
    assert len(result.unplaced_parts) == 0
    print("  PASSED")


def test_multiple_parts_single_sheet():
    parts = [PartSpec(name="panel", width_mm=200, height_mm=200, quantity=4)]
    sheet = SheetSpec(width_mm=500, height_mm=500, thickness_mm=19, margin_mm=10)

    result = pack_sheets(parts, sheet)

    assert result.total_sheets == 1
    assert result.total_parts == 4
    assert len(result.unplaced_parts) == 0
    print("  PASSED")


def test_parts_require_multiple_sheets():

    parts = [PartSpec(name="large", width_mm=400, height_mm=400, quantity=4)]
    sheet = SheetSpec(width_mm=500, height_mm=500, thickness_mm=19, margin_mm=10, kerf_mm=0)

    result = pack_sheets(parts, sheet)

    assert result.total_sheets == 4
    assert result.total_parts == 4
    assert len(result.unplaced_parts) == 0
    print("  PASSED")


def test_mixed_part_sizes():
    parts = [
        PartSpec(name="large", width_mm=400, height_mm=400, quantity=2),
        PartSpec(name="small", width_mm=100, height_mm=100, quantity=10),
    ]
    sheet = SheetSpec(width_mm=1000, height_mm=1000, thickness_mm=19, margin_mm=10, kerf_mm=6)

    result = pack_sheets(parts, sheet)

    assert result.total_parts >= 10
    print(f"  Placed {result.total_parts} parts on {result.total_sheets} sheet(s)")
    print("  PASSED")


def test_part_too_large():
    parts = [PartSpec(name="huge", width_mm=2000, height_mm=2000, quantity=1)]
    sheet = SheetSpec(width_mm=1000, height_mm=1000, thickness_mm=19)

    result = pack_sheets(parts, sheet)

    assert result.total_sheets == 0
    assert result.total_parts == 0
    assert len(result.unplaced_parts) == 1
    assert result.unplaced_parts[0].name == "huge"
    print("  PASSED")


def test_some_parts_too_large():
    parts = [
        PartSpec(name="fits", width_mm=200, height_mm=200, quantity=2),
        PartSpec(name="huge", width_mm=2000, height_mm=2000, quantity=1),
    ]
    sheet = SheetSpec(width_mm=500, height_mm=500, thickness_mm=19)

    result = pack_sheets(parts, sheet)

    assert result.total_parts == 2
    assert len(result.unplaced_parts) == 1
    assert result.unplaced_parts[0].name == "huge"
    print("  PASSED")


def test_zero_quantity_ignored():
    parts = [
        PartSpec(name="real", width_mm=200, height_mm=200, quantity=1),
        PartSpec(name="placeholder", width_mm=100, height_mm=100, quantity=0),
    ]
    sheet = SheetSpec(width_mm=500, height_mm=500, thickness_mm=19)

    result = pack_sheets(parts, sheet)

    assert result.total_parts == 1
    print("  PASSED")


def test_max_sheets_limit():

    parts = [PartSpec(name="part", width_mm=400, height_mm=400, quantity=10)]
    sheet = SheetSpec(width_mm=500, height_mm=500, thickness_mm=19, margin_mm=10, kerf_mm=0)

    result = pack_sheets(parts, sheet, max_sheets=2)

    assert result.total_sheets <= 2
    assert len(result.unplaced_parts) > 0
    print(f"  Placed {result.total_parts} parts, {result.unplaced_parts[0].quantity} unplaced")
    print("  PASSED")


def test_placements_have_correct_coords():
    parts = [PartSpec(name="panel", width_mm=100, height_mm=100, quantity=1)]
    sheet = SheetSpec(width_mm=500, height_mm=500, thickness_mm=19, margin_mm=20)

    result = pack_sheets(parts, sheet)

    assert result.total_sheets == 1
    p = result.sheets[0].placements[0]

    assert p.x_mm == 70, f"Expected x=70, got {p.x_mm}"
    assert p.y_mm == 70, f"Expected y=70, got {p.y_mm}"
    print("  PASSED")


def test_utilization_calculated():
    parts = [PartSpec(name="half", width_mm=480, height_mm=480, quantity=1)]
    sheet = SheetSpec(width_mm=1000, height_mm=1000, thickness_mm=19, margin_mm=10)

    result = pack_sheets(parts, sheet)

    assert result.total_sheets == 1
    util = result.sheets[0].utilization
    assert 0.23 < util < 0.25, f"Expected ~24% utilization, got {util * 100:.1f}%"
    print("  PASSED")


def test_rotation_improves_packing():

    parts = [PartSpec(name="long", width_mm=800, height_mm=200, quantity=2, allow_rotation=True)]
    sheet = SheetSpec(width_mm=1020, height_mm=520, thickness_mm=19, margin_mm=10, kerf_mm=6)

    result = pack_sheets(parts, sheet)

    assert result.total_sheets == 1
    assert result.total_parts == 2
    print("  PASSED")


def test_recipe16_scenario():
    parts = [
        PartSpec(name="door", width_mm=457, height_mm=597, quantity=4),
        PartSpec(name="drawer", width_mm=254, height_mm=152, quantity=7),
    ]

    sheet = SheetSpec(
        width_mm=1245,
        height_mm=1232,
        thickness_mm=19,
        margin_mm=10,
        kerf_mm=6,
    )

    result = pack_sheets(parts, sheet)

    assert result.total_sheets >= 1
    assert result.total_sheets <= 2

    placed_doors = 0
    placed_drawers = 0
    for sheet_layout in result.sheets:
        for p in sheet_layout.placements:
            if p.part_spec.name == "door":
                placed_doors += 1
            elif p.part_spec.name == "drawer":
                placed_drawers += 1

    assert placed_doors == 4, f"Expected 4 doors, got {placed_doors}"

    assert placed_drawers >= 5, f"Expected at least 5 drawers, got {placed_drawers}"

    print(f"  Placed {placed_doors} doors + {placed_drawers} drawers on {result.total_sheets} sheet(s)")
    print(f"  Utilization: {result.overall_utilization_percent:.1f}%")
    print("  PASSED")


def test_user_example_scenario():
    parts = [
        PartSpec(name="large_door", width_mm=457, height_mm=597, quantity=20),
        PartSpec(name="small_door", width_mm=305, height_mm=203, quantity=15),
        PartSpec(name="tall_door", width_mm=457, height_mm=914, quantity=2),
    ]

    sheet = SheetSpec(
        width_mm=1220,
        height_mm=2440,
        thickness_mm=19,
        margin_mm=10,
        kerf_mm=6,
    )

    result = pack_sheets(parts, sheet)

    assert result.total_sheets >= 3

    total_requested = 20 + 15 + 2
    assert result.total_parts >= total_requested - 2

    print(f"  Placed {result.total_parts}/{total_requested} parts on {result.total_sheets} sheets")
    print(f"  Overall utilization: {result.overall_utilization_percent:.1f}%")

    if result.unplaced_parts:
        print(f"  Unplaced: {[(p.name, p.quantity) for p in result.unplaced_parts]}")

    print("  PASSED")


def test_sheet_index_increments():
    parts = [PartSpec(name="part", width_mm=900, height_mm=900, quantity=3)]
    sheet = SheetSpec(width_mm=1000, height_mm=1000, thickness_mm=19, margin_mm=10, kerf_mm=0)

    result = pack_sheets(parts, sheet)

    assert result.total_sheets == 3

    for i, sheet_layout in enumerate(result.sheets):
        assert sheet_layout.sheet_index == i, f"Sheet {i} has wrong index {sheet_layout.sheet_index}"

    print("  PASSED")


def test_instance_ids_preserved():
    parts = [PartSpec(name="item", width_mm=100, height_mm=100, quantity=3)]
    sheet = SheetSpec(width_mm=500, height_mm=500, thickness_mm=19, margin_mm=10, kerf_mm=0)

    result = pack_sheets(parts, sheet)

    instance_ids = []
    for sheet_layout in result.sheets:
        for p in sheet_layout.placements:
            instance_ids.append(p.instance_id)

    assert sorted(instance_ids) == [0, 1, 2]
    print("  PASSED")
