from adapters.ast_to_removal import ast_to_removal_intents
from layout_ast.layout import Feature, Geometry, Item, LayoutAST, Placement, Sheet


def test_warning_collection_on_invalid_item():
    """Test that warnings are collected when items fail to convert."""

    # Create AST with one valid item and one invalid item (missing geometry)
    ast = LayoutAST(
        sheet=Sheet(width_mm=450, height_mm=650, thickness_mm=19, margin_mm=0.0),
        items=(
            # Valid item
            Item(
                kind="shape",
                type="Rect",
                geometry=Geometry(data={"w_mm": 100, "h_mm": 50}),
                placement=Placement(center_xy_mm=(200, 150)),
                feature=Feature(type="profile", depth_mm=0.0, is_through=True, side="outside"),
                shape_id="valid_rect",
            ),
            # Invalid item - missing geometry entirely (raises ValueError)
            Item(
                kind="shape",
                type="Rect",
                geometry=None,
                placement=Placement(center_xy_mm=(100, 100)),
                feature=Feature(type="profile", depth_mm=0.0, is_through=True, side="outside"),
                shape_id="invalid_rect",
            ),
        ),
    )

    warnings: list[str] = []
    intents = ast_to_removal_intents(ast, warnings=warnings)

    # Should get one valid intent
    assert len(intents) == 1, f"Expected 1 intent, got {len(intents)}"
    assert intents[0].region_id == "profile_valid_rect"

    # Should have collected one warning
    assert len(warnings) == 1, f"Expected 1 warning, got {len(warnings)}"
    assert "invalid_rect" in warnings[0]

    print("  ✓ PASS")


def test_no_warnings_when_all_valid():
    """Test that no warnings are collected when all items are valid."""

    ast = LayoutAST(
        sheet=Sheet(width_mm=450, height_mm=650, thickness_mm=19, margin_mm=0.0),
        items=(
            Item(
                kind="shape",
                type="Rect",
                geometry=Geometry(data={"w_mm": 100, "h_mm": 50}),
                placement=Placement(center_xy_mm=(200, 150)),
                feature=Feature(type="profile", depth_mm=0.0, is_through=True, side="outside"),
                shape_id="rect1",
            ),
            Item(
                kind="shape",
                type="Circle",
                geometry=Geometry(data={"diameter_mm": 20}),
                placement=Placement(center_xy_mm=(300, 200)),
                feature=Feature(type="hole", depth_mm=0.0, is_through=True),
                shape_id="hole1",
            ),
        ),
    )

    warnings: list[str] = []
    intents = ast_to_removal_intents(ast, warnings=warnings)

    assert len(intents) == 2, f"Expected 2 intents, got {len(intents)}"
    assert len(warnings) == 0, f"Expected 0 warnings, got {len(warnings)}"

    print("  ✓ PASS")


def test_warnings_none_by_default():
    """Test that function works without warnings parameter (backward compat)."""

    ast = LayoutAST(
        sheet=Sheet(width_mm=450, height_mm=650, thickness_mm=19, margin_mm=0.0),
        items=(
            Item(
                kind="shape",
                type="Rect",
                geometry=Geometry(data={"w_mm": 100, "h_mm": 50}),
                placement=Placement(center_xy_mm=(200, 150)),
                feature=Feature(type="profile", depth_mm=0.0, is_through=True, side="outside"),
                shape_id="rect1",
            ),
        ),
    )

    # Should work without warnings parameter
    intents = ast_to_removal_intents(ast)
    assert len(intents) == 1

    print("  ✓ PASS")


def test_skips_non_shape_items():
    """Test that non-shape items are skipped without warnings."""

    ast = LayoutAST(
        sheet=Sheet(width_mm=450, height_mm=650, thickness_mm=19, margin_mm=0.0),
        items=(
            Item(
                kind="component",  # Not a shape
                type="Shaker",
                shape_id="door1",
            ),
            Item(
                kind="shape",
                type="Rect",
                geometry=Geometry(data={"w_mm": 100, "h_mm": 50}),
                placement=Placement(center_xy_mm=(200, 150)),
                feature=Feature(type="profile", depth_mm=0.0, is_through=True, side="outside"),
                shape_id="rect1",
            ),
        ),
    )

    warnings: list[str] = []
    intents = ast_to_removal_intents(ast, warnings=warnings)

    # Only shape items are processed
    assert len(intents) == 1
    # Non-shape items don't generate warnings (they're just skipped)
    assert len(warnings) == 0

    print("  ✓ PASS")


def test_unknown_feature_type_warning():
    """Test that unknown feature type generates a warning."""

    ast = LayoutAST(
        sheet=Sheet(width_mm=450, height_mm=650, thickness_mm=19, margin_mm=0.0),
        items=(
            Item(
                kind="shape",
                type="Rect",
                geometry=Geometry(data={"w_mm": 100, "h_mm": 50}),
                placement=Placement(center_xy_mm=(200, 150)),
                feature=Feature(type="unknown_feature", depth_mm=0.0, is_through=True),  # Unknown type
                shape_id="bad_feature",
            ),
        ),
    )

    warnings: list[str] = []
    intents = ast_to_removal_intents(ast, warnings=warnings)

    assert len(intents) == 0
    assert len(warnings) == 1
    assert "bad_feature" in warnings[0]
    assert "Unknown feature type" in warnings[0]

    print("  ✓ PASS")


def test_multiple_warnings():
    """Test that multiple invalid items each generate warnings."""

    ast = LayoutAST(
        sheet=Sheet(width_mm=450, height_mm=650, thickness_mm=19, margin_mm=0.0),
        items=(
            # Missing geometry (raises ValueError)
            Item(
                kind="shape",
                type="Rect",
                geometry=None,
                placement=Placement(center_xy_mm=(100, 100)),
                feature=Feature(type="profile", depth_mm=0.0, is_through=True, side="outside"),
                shape_id="bad1",
            ),
            # Missing placement (raises ValueError)
            Item(
                kind="shape",
                type="Circle",
                geometry=Geometry(data={"diameter_mm": 20}),
                placement=None,
                feature=Feature(type="hole", depth_mm=0.0, is_through=True),
                shape_id="bad2",
            ),
        ),
    )

    warnings: list[str] = []
    intents = ast_to_removal_intents(ast, warnings=warnings)

    assert len(intents) == 0
    assert len(warnings) == 2
    assert "bad1" in warnings[0]
    assert "bad2" in warnings[1]

    print("  ✓ PASS")


def _face_ast(face: str) -> LayoutAST:
    return LayoutAST(
        sheet=Sheet(width_mm=400, height_mm=600, thickness_mm=19, margin_mm=0.0),
        items=(
            Item(
                kind="shape",
                type="Circle",
                geometry=Geometry(data={"diameter_mm": 35.0}),
                placement=Placement(center_xy_mm=(40.0, 100.0)),
                feature=Feature(type="pocket", depth_mm=12.5, face=face),
                shape_id="hinge_cup",
            ),
        ),
    )


def test_intent_face_stamped_from_feature():
    intents = ast_to_removal_intents(_face_ast("back"))

    assert len(intents) == 1
    assert intents[0].face == "back"
    assert intents[0].to_dict()["face"] == "back"


def test_intent_face_defaults_front():
    intents = ast_to_removal_intents(_face_ast("front"))

    assert intents[0].face == "front"
    assert "face" not in intents[0].to_dict()
