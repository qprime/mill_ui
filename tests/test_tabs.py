from adapters.ast_to_removal import ast_to_removal_intents, item_to_removal_intent
from ir.removal_intent import TabConstraint
from layout_ast.layout import Feature, Geometry, Item, LayoutAST, Placement, Sheet
from pml.yaml_formatter import format_pml_yaml
from pml.yaml_parser import parse_pml_yaml
from resolution.layout_resolver import resolve_layout


def test_pml_parse_profile_with_tabs():

    pml = """
Sheet:
  width: 450mm
  height: 650mm
  thickness: 19mm
  margin: 0mm

children:
  - Rect:
      id: cutout
      feature:
        type: profile
        depth: through
        side: outside
        tab_count: 4
        tab_height: 3mm
        tab_width: 10mm
"""

    ast = parse_pml_yaml(pml)
    flat = resolve_layout(ast)

    assert len(flat.items) == 1
    item = flat.items[0]

    assert item.feature is not None
    assert item.feature.type == "profile"
    assert item.feature.is_through
    assert item.feature.side == "outside"

    assert item.feature.tab_count == 4
    assert item.feature.tab_height_mm == 3.0
    assert item.feature.tab_width_mm == 10.0


def test_pml_parse_profile_with_tabs_no_width():

    pml = """
Sheet:
  width: 450mm
  height: 650mm
  thickness: 19mm
  margin: 0mm

children:
  - Rect:
      id: cutout
      feature:
        type: profile
        depth: through
        side: outside
        tab_count: 4
        tab_height: 3mm
"""

    ast = parse_pml_yaml(pml)
    flat = resolve_layout(ast)

    item = flat.items[0]

    assert item.feature is not None
    assert item.feature.tab_count == 4
    assert item.feature.tab_height_mm == 3.0
    assert item.feature.tab_width_mm is None


def test_pml_parse_profile_with_tabs_inside():

    pml = """
Sheet:
  width: 450mm
  height: 650mm
  thickness: 19mm
  margin: 0mm

children:
  - Rect:
      id: pocket_outline
      feature:
        type: profile
        depth: 6mm
        side: inside
        tab_count: 6
        tab_height: 2mm
        tab_width: 8mm
"""

    ast = parse_pml_yaml(pml)
    flat = resolve_layout(ast)

    item = flat.items[0]

    assert item.feature is not None
    assert item.feature.type == "profile"
    assert item.feature.depth_mm == 6.0
    assert item.feature.side == "inside"
    assert item.feature.tab_count == 6
    assert item.feature.tab_height_mm == 2.0
    assert item.feature.tab_width_mm == 8.0


def test_ast_construction_with_tabs():

    ast = LayoutAST(
        sheet=Sheet(width_mm=450, height_mm=650, thickness_mm=19, margin_mm=0.0),
        items=(
            Item(
                kind="shape",
                type="Rect",
                geometry=Geometry(data={"w_mm": 400, "h_mm": 600}),
                placement=Placement(center_xy_mm=(225, 325)),
                feature=Feature(
                    type="profile",
                    depth_mm=0.0,
                    is_through=True,
                    side="outside",
                    tab_count=4,
                    tab_height_mm=3.0,
                    tab_width_mm=10.0,
                ),
                shape_id="cutout",
            ),
        ),
    )

    item = ast.items[0]
    assert item.feature is not None
    assert item.feature.tab_count == 4
    assert item.feature.tab_height_mm == 3.0
    assert item.feature.tab_width_mm == 10.0


def test_ast_to_removal_intent_with_tabs():

    item = Item(
        kind="shape",
        type="Rect",
        geometry=Geometry(data={"w_mm": 400, "h_mm": 600}),
        placement=Placement(center_xy_mm=(225, 325)),
        feature=Feature(
            type="profile",
            depth_mm=0.0,
            is_through=True,
            side="outside",
            tab_count=4,
            tab_height_mm=3.0,
            tab_width_mm=10.0,
        ),
        shape_id="cutout",
    )

    intent = item_to_removal_intent(item, sheet_thickness_mm=19.0)

    assert intent.depth_mm() == 19.0
    assert intent.hint_type == "profile"
    assert intent.side == "outside"

    assert intent.constraints.tabs is not None
    assert isinstance(intent.constraints.tabs, TabConstraint)
    assert intent.constraints.tabs.count == 4
    assert intent.constraints.tabs.height_mm == 3.0
    assert intent.constraints.tabs.width_mm == 10.0


def test_ast_to_removal_intent_with_tabs_no_width():

    item = Item(
        kind="shape",
        type="Rect",
        geometry=Geometry(data={"w_mm": 400, "h_mm": 600}),
        placement=Placement(center_xy_mm=(225, 325)),
        feature=Feature(
            type="profile",
            depth_mm=0.0,
            is_through=True,
            side="outside",
            tab_count=4,
            tab_height_mm=3.0,
            tab_width_mm=None,
        ),
        shape_id="cutout",
    )

    intent = item_to_removal_intent(item, sheet_thickness_mm=19.0)

    assert intent.constraints.tabs is not None
    assert intent.constraints.tabs.count == 4
    assert intent.constraints.tabs.height_mm == 3.0
    assert intent.constraints.tabs.width_mm is None


def test_full_pipeline_pml_to_removal_intent():

    pml = """
Sheet:
  width: 450mm
  height: 650mm
  thickness: 19mm
  margin: 0mm

children:
  - Rect:
      id: door
      feature:
        type: profile
        depth: through
        side: outside
        tab_count: 4
        tab_height: 3mm
        tab_width: 10mm
  - Inset:
      distance: 75mm
      children:
        - Rect:
            id: panel
            feature:
              type: pocket
              depth: 6mm
"""

    ast = parse_pml_yaml(pml)
    flat = resolve_layout(ast)
    intents = ast_to_removal_intents(flat)

    assert len(intents) == 2

    profile_intent = intents[0]
    assert profile_intent.hint_type == "profile"
    assert profile_intent.constraints.tabs is not None
    assert profile_intent.constraints.tabs.count == 4
    assert profile_intent.constraints.tabs.height_mm == 3.0
    assert profile_intent.constraints.tabs.width_mm == 10.0

    pocket_intent = intents[1]
    assert pocket_intent.hint_type == "pocket"
    assert pocket_intent.constraints.tabs is None


def test_pml_roundtrip_with_tabs():

    pml_in = """
Sheet:
  width: 450mm
  height: 650mm
  thickness: 19mm
  margin: 0mm

children:
  - Rect:
      id: cutout
      feature:
        type: profile
        depth: through
        side: outside
        tab_count: 4
        tab_height: 3mm
        tab_width: 10mm
"""

    ast1 = parse_pml_yaml(pml_in)
    pml_out = format_pml_yaml(ast1)
    ast2 = parse_pml_yaml(pml_out)

    flat1 = resolve_layout(ast1)
    flat2 = resolve_layout(ast2)

    item1 = flat1.items[0]
    item2 = flat2.items[0]

    assert item1.feature is not None
    assert item2.feature is not None
    assert item1.feature.tab_count == item2.feature.tab_count
    assert item1.feature.tab_height_mm == item2.feature.tab_height_mm
    assert item1.feature.tab_width_mm == item2.feature.tab_width_mm
