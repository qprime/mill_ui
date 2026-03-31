from pml.nest_parser import nest_job_to_api_params
from pml.yaml_parser import NestParseError, parse_nest_yaml


def test_basic_nest_parsing():

    source = """
Nest:
  algorithm: maxrects

  Sheet:
    width: 1000mm
    height: 2000mm
    thickness: 19mm

  kerf: 6.35mm
  margin: 10mm

  parts:
    - name: panel
      width: 400mm
      height: 600mm
      quantity: 4
"""

    job = parse_nest_yaml(source)

    assert job.algorithm == "maxrects"
    assert job.sheet_width_mm == 1000.0
    assert job.sheet_height_mm == 2000.0
    assert job.sheet_thickness_mm == 19.0
    assert job.kerf_mm == 6.35
    assert job.margin_mm == 10.0
    assert len(job.parts) == 1
    assert job.parts[0].name == "panel"
    assert job.parts[0].width_mm == 400.0
    assert job.parts[0].height_mm == 600.0
    assert job.parts[0].quantity == 4


def test_guillotine_algorithm():

    source = """
Nest:
  algorithm: guillotine

  Sheet:
    width: 1200mm
    height: 2400mm
    thickness: 18mm

  parts:
    - name: door
      width: 500mm
      height: 800mm
      quantity: 2
"""

    job = parse_nest_yaml(source)

    assert job.algorithm == "guillotine"
    assert job.sheet_width_mm == 1200.0
    assert job.sheet_height_mm == 2400.0
    assert job.sheet_thickness_mm == 18.0

    assert job.kerf_mm == 6.35
    assert job.margin_mm == 10.0


def test_multiple_parts():

    source = """
Nest:
  algorithm: maxrects

  Sheet:
    width: 1232mm
    height: 1245mm
    thickness: 19mm

  kerf: 6.35mm
  margin: 10mm

  parts:
    - name: large_door
      width: 457mm
      height: 597mm
      quantity: 20

    - name: small_door
      width: 305mm
      height: 203mm
      quantity: 15

    - name: tall_door
      width: 457mm
      height: 914mm
      quantity: 2
"""

    job = parse_nest_yaml(source)

    assert len(job.parts) == 3
    assert job.parts[0].name == "large_door"
    assert job.parts[0].quantity == 20
    assert job.parts[1].name == "small_door"
    assert job.parts[1].quantity == 15
    assert job.parts[2].name == "tall_door"
    assert job.parts[2].quantity == 2


def test_part_with_template():

    source = """
Nest:
  algorithm: maxrects

  Sheet:
    width: 1000mm
    height: 2000mm
    thickness: 19mm

  parts:
    - name: door
      width: 400mm
      height: 600mm
      quantity: 2
      template:
        name: Shaker
        params:
          stile_w: 50mm
          rail_h: 50mm
          panel_recess: 6mm
"""

    job = parse_nest_yaml(source)

    assert len(job.parts) == 1
    part = job.parts[0]
    assert part.name == "door"
    assert part.template == "Shaker"
    assert part.template_params["stile_w"] == 50.0
    assert part.template_params["rail_h"] == 50.0
    assert part.template_params["panel_recess"] == 6.0


def test_mixed_parts_with_and_without_template():

    source = """
Nest:
  algorithm: maxrects

  Sheet:
    width: 1232mm
    height: 1245mm
    thickness: 19mm

  kerf: 6.35mm
  margin: 10mm

  parts:
    - name: large_door
      width: 457mm
      height: 597mm
      quantity: 20
      template:
        name: Shaker
        params:
          stile_w: 57mm
          rail_h: 57mm
          panel_recess: 6mm

    - name: small_door
      width: 305mm
      height: 203mm
      quantity: 15

    - name: tall_door
      width: 457mm
      height: 914mm
      quantity: 2
      template:
        name: Shaker
        params:
          stile_w: 57mm
          rail_h: 57mm
          panel_recess: 6mm
"""

    job = parse_nest_yaml(source)

    assert len(job.parts) == 3

    assert job.parts[0].name == "large_door"
    assert job.parts[0].template == "Shaker"
    assert job.parts[0].template_params["stile_w"] == 57.0

    assert job.parts[1].name == "small_door"
    assert job.parts[1].template is None
    assert job.parts[1].template_params == {}

    assert job.parts[2].name == "tall_door"
    assert job.parts[2].template == "Shaker"


def test_quantity_default():

    source = """
Nest:
  algorithm: maxrects

  Sheet:
    width: 1000mm
    height: 2000mm
    thickness: 19mm

  parts:
    - name: panel
      width: 400mm
      height: 600mm
"""

    job = parse_nest_yaml(source)

    assert job.parts[0].quantity == 1


def test_nest_job_to_api_params():

    source = """
Nest:
  algorithm: maxrects

  Sheet:
    width: 1232mm
    height: 1245mm
    thickness: 19mm

  kerf: 6.35mm
  margin: 10mm

  parts:
    - name: door
      width: 457mm
      height: 597mm
      quantity: 20
      template:
        name: Shaker
        params:
          stile_w: 57mm
          rail_h: 57mm
          panel_recess: 6mm

    - name: panel
      width: 305mm
      height: 203mm
      quantity: 15
"""

    job = parse_nest_yaml(source)
    params = nest_job_to_api_params(job)

    assert params["algorithm"] == "maxrects"
    assert params["sheet_width_mm"] == 1232.0
    assert params["sheet_height_mm"] == 1245.0
    assert params["sheet_thickness_mm"] == 19.0
    assert params["kerf_mm"] == 6.35
    assert params["margin_mm"] == 10.0

    assert len(params["parts"]) == 2
    assert params["parts"][0]["name"] == "door"
    assert params["parts"][0]["template"] == "Shaker"
    assert params["parts"][0]["template_params"]["stile_w"] == 57.0
    assert params["parts"][1]["name"] == "panel"
    assert "template" not in params["parts"][1]


def test_error_missing_nest_directive():

    source = """
Sheet:
  width: 1000mm
  height: 2000mm
  thickness: 19mm

parts:
  - name: panel
    width: 400mm
    height: 600mm
"""

    try:
        parse_nest_yaml(source)
        raise AssertionError("Should have raised NestParseError")
    except NestParseError as e:
        assert "nest" in str(e).lower()


def test_error_missing_sheet():

    source = """
Nest:
  algorithm: maxrects

  parts:
    - name: panel
      width: 400mm
      height: 600mm
"""

    try:
        parse_nest_yaml(source)
        raise AssertionError("Should have raised NestParseError")
    except NestParseError as e:
        assert "sheet" in str(e).lower()


def test_error_no_parts():

    source = """
Nest:
  algorithm: maxrects

  Sheet:
    width: 1000mm
    height: 2000mm
    thickness: 19mm

  parts: []
"""

    try:
        parse_nest_yaml(source)
        raise AssertionError("Should have raised NestParseError")
    except NestParseError as e:
        assert "parts" in str(e).lower() or "no parts" in str(e).lower()


def test_simple_template_reference():

    source = """
Nest:
  algorithm: maxrects

  Sheet:
    width: 1000mm
    height: 2000mm
    thickness: 19mm

  parts:
    - name: door
      width: 400mm
      height: 600mm
      quantity: 2
      template: shaker
"""

    job = parse_nest_yaml(source)

    assert len(job.parts) == 1
    part = job.parts[0]
    assert part.name == "door"
    assert part.template == "shaker"
    assert part.template_params == {}


def test_parse_shape_rounded_rect():
    source = """
Nest:
  algorithm: maxrects
  Sheet:
    width: 1000mm
    height: 2000mm
    thickness: 19mm
  parts:
    - name: coaster
      width: 100mm
      height: 100mm
      quantity: 10
      shape:
        type: RoundedRect
        radius: 10mm
"""
    job = parse_nest_yaml(source)
    part = job.parts[0]
    assert part.shape == "RoundedRect"
    assert part.shape_params["radius_mm"] == 10.0
    assert "corners" not in part.shape_params


def test_parse_shape_rounded_rect_selective_corners():
    source = """
Nest:
  algorithm: maxrects
  Sheet:
    width: 1000mm
    height: 2000mm
    thickness: 19mm
  parts:
    - name: edge_strip
      width: 228.6mm
      height: 863.6mm
      quantity: 2
      shape:
        type: RoundedRect
        radius: 12.7mm
        corners: [tl, bl]
"""
    job = parse_nest_yaml(source)
    part = job.parts[0]
    assert part.shape == "RoundedRect"
    assert part.shape_params["radius_mm"] == 12.7
    assert part.shape_params["corners"] == ("bl", "tl")


def test_parse_shape_circle():
    source = """
Nest:
  algorithm: maxrects
  Sheet:
    width: 1000mm
    height: 2000mm
    thickness: 19mm
  parts:
    - name: disc
      width: 200mm
      height: 200mm
      quantity: 4
      shape:
        type: Circle
"""
    job = parse_nest_yaml(source)
    part = job.parts[0]
    assert part.shape == "Circle"
    assert part.shape_params == {}


def test_parse_shape_circle_nonsquare_error():
    source = """
Nest:
  algorithm: maxrects
  Sheet:
    width: 1000mm
    height: 2000mm
    thickness: 19mm
  parts:
    - name: disc
      width: 200mm
      height: 150mm
      shape:
        type: Circle
"""
    try:
        parse_nest_yaml(source)
        raise AssertionError("Should have raised NestParseError")
    except NestParseError as e:
        assert "width == height" in str(e)


def test_parse_shape_omitted():
    source = """
Nest:
  algorithm: maxrects
  Sheet:
    width: 1000mm
    height: 2000mm
    thickness: 19mm
  parts:
    - name: panel
      width: 400mm
      height: 600mm
"""
    job = parse_nest_yaml(source)
    part = job.parts[0]
    assert part.shape is None
    assert part.shape_params == {}


def test_parse_shape_and_template_error():
    source = """
Nest:
  algorithm: maxrects
  Sheet:
    width: 1000mm
    height: 2000mm
    thickness: 19mm
  parts:
    - name: door
      width: 400mm
      height: 600mm
      template: shaker
      shape:
        type: RoundedRect
        radius: 10mm
"""
    try:
        parse_nest_yaml(source)
        raise AssertionError("Should have raised NestParseError")
    except NestParseError as e:
        assert "mutually exclusive" in str(e)


def test_parse_shape_unknown_type():
    source = """
Nest:
  algorithm: maxrects
  Sheet:
    width: 1000mm
    height: 2000mm
    thickness: 19mm
  parts:
    - name: panel
      width: 400mm
      height: 600mm
      shape:
        type: Hexagon
"""
    try:
        parse_nest_yaml(source)
        raise AssertionError("Should have raised NestParseError")
    except NestParseError as e:
        assert "Hexagon" in str(e)


def test_parse_shape_rounded_rect_missing_radius():
    source = """
Nest:
  algorithm: maxrects
  Sheet:
    width: 1000mm
    height: 2000mm
    thickness: 19mm
  parts:
    - name: panel
      width: 400mm
      height: 600mm
      shape:
        type: RoundedRect
"""
    try:
        parse_nest_yaml(source)
        raise AssertionError("Should have raised NestParseError")
    except NestParseError as e:
        assert "radius" in str(e).lower()


def test_parse_shape_polygon_points_exceed_bounds():
    source = """
Nest:
  algorithm: maxrects
  Sheet:
    width: 1000mm
    height: 2000mm
    thickness: 19mm
  parts:
    - name: gusset
      width: 50mm
      height: 50mm
      shape:
        type: Polygon
        points: [[-100, -100], [100, -100], [0, 100]]
"""
    try:
        parse_nest_yaml(source)
        raise AssertionError("Should have raised NestParseError")
    except NestParseError as e:
        assert "exceeds" in str(e).lower()
        assert "bounding box" in str(e).lower()


def test_parse_shape_polygon_points_within_bounds():
    source = """
Nest:
  algorithm: maxrects
  Sheet:
    width: 1000mm
    height: 2000mm
    thickness: 19mm
  parts:
    - name: gusset
      width: 100mm
      height: 100mm
      shape:
        type: Polygon
        points: [[-50, -50], [50, -50], [0, 50]]
"""
    job = parse_nest_yaml(source)
    part = job.parts[0]
    assert part.shape == "Polygon"
    assert len(part.shape_params["points"]) == 3


def test_nest_job_to_api_params_with_shape():
    source = """
Nest:
  algorithm: maxrects
  Sheet:
    width: 1000mm
    height: 2000mm
    thickness: 19mm
  parts:
    - name: coaster
      width: 100mm
      height: 100mm
      quantity: 10
      shape:
        type: RoundedRect
        radius: 10mm
"""
    job = parse_nest_yaml(source)
    params = nest_job_to_api_params(job)
    part_dict = params["parts"][0]
    assert part_dict["shape"] == "RoundedRect"
    assert part_dict["shape_params"]["radius_mm"] == 10.0


def test_holding_onion_skin_job_level():
    source = """
Nest:
  algorithm: guillotine
  holding:
    onion_skin: 0.3mm
  Sheet:
    width: 1220mm
    height: 1220mm
    thickness: 19mm
  parts:
    - name: shelf
      width: 400mm
      height: 200mm
      quantity: 4
"""
    job = parse_nest_yaml(source)
    assert job.holding is not None
    assert job.holding.onion_skin_mm == 0.3
    assert job.holding.tab_count is None
    for part in job.parts:
        assert part.holding is not None
        assert part.holding.onion_skin_mm == 0.3


def test_holding_tabs_job_level():
    source = """
Nest:
  algorithm: maxrects
  holding:
    tab_count: 4
    tab_height: 3mm
    tab_width: 10mm
  Sheet:
    width: 1220mm
    height: 1220mm
    thickness: 19mm
  parts:
    - name: shelf
      width: 400mm
      height: 200mm
      quantity: 2
"""
    job = parse_nest_yaml(source)
    assert job.holding is not None
    assert job.holding.tab_count == 4
    assert job.holding.tab_height_mm == 3.0
    assert job.holding.tab_width_mm == 10.0
    assert job.holding.onion_skin_mm is None
    assert job.parts[0].holding == job.holding


def test_holding_tabs_without_width():
    source = """
Nest:
  algorithm: maxrects
  holding:
    tab_count: 4
    tab_height: 3mm
  Sheet:
    width: 1220mm
    height: 1220mm
    thickness: 19mm
  parts:
    - name: shelf
      width: 400mm
      height: 200mm
"""
    job = parse_nest_yaml(source)
    assert job.holding is not None
    assert job.holding.tab_width_mm is None


def test_holding_per_part_override():
    source = """
Nest:
  algorithm: guillotine
  holding:
    onion_skin: 0.3mm
  Sheet:
    width: 1220mm
    height: 1220mm
    thickness: 19mm
  parts:
    - name: small
      width: 200mm
      height: 100mm
      quantity: 4
    - name: large
      width: 600mm
      height: 400mm
      quantity: 2
      holding:
        tab_count: 6
        tab_height: 3mm
"""
    job = parse_nest_yaml(source)
    small = job.parts[0]
    large = job.parts[1]
    assert small.holding is not None
    assert small.holding.onion_skin_mm == 0.3
    assert large.holding is not None
    assert large.holding.tab_count == 6
    assert large.holding.tab_height_mm == 3.0
    assert large.holding.onion_skin_mm is None


def test_holding_mutual_exclusivity_error():
    source = """
Nest:
  algorithm: maxrects
  holding:
    onion_skin: 0.3mm
    tab_count: 4
    tab_height: 3mm
  Sheet:
    width: 1220mm
    height: 1220mm
    thickness: 19mm
  parts:
    - name: shelf
      width: 400mm
      height: 200mm
"""
    try:
        parse_nest_yaml(source)
        raise AssertionError("Expected NestParseError")
    except NestParseError:
        pass


def test_holding_empty_block_error():
    source = """
Nest:
  algorithm: maxrects
  holding: {}
  Sheet:
    width: 1220mm
    height: 1220mm
    thickness: 19mm
  parts:
    - name: shelf
      width: 400mm
      height: 200mm
"""
    try:
        parse_nest_yaml(source)
        raise AssertionError("Expected NestParseError")
    except NestParseError:
        pass


def test_holding_tabs_missing_required_fields():
    source = """
Nest:
  algorithm: maxrects
  holding:
    tab_count: 4
  Sheet:
    width: 1220mm
    height: 1220mm
    thickness: 19mm
  parts:
    - name: shelf
      width: 400mm
      height: 200mm
"""
    try:
        parse_nest_yaml(source)
        raise AssertionError("Expected NestParseError for missing tab_height")
    except NestParseError:
        pass


def test_holding_api_params_propagation():
    source = """
Nest:
  algorithm: guillotine
  holding:
    onion_skin: 0.5mm
  Sheet:
    width: 1220mm
    height: 1220mm
    thickness: 19mm
  parts:
    - name: shelf
      width: 400mm
      height: 200mm
"""
    job = parse_nest_yaml(source)
    params = nest_job_to_api_params(job)
    part = params["parts"][0]
    assert part["holding"]["onion_skin_mm"] == 0.5


def test_holding_no_default():
    source = """
Nest:
  algorithm: maxrects
  Sheet:
    width: 1220mm
    height: 1220mm
    thickness: 19mm
  parts:
    - name: shelf
      width: 400mm
      height: 200mm
"""
    job = parse_nest_yaml(source)
    assert job.holding is None
    assert job.parts[0].holding is None


def test_holding_unknown_key_error():
    source = """
Nest:
  algorithm: maxrects
  holding:
    onion_skn: 0.3mm
  Sheet:
    width: 1220mm
    height: 1220mm
    thickness: 19mm
  parts:
    - name: shelf
      width: 400mm
      height: 200mm
"""
    try:
        parse_nest_yaml(source)
        raise AssertionError("Expected NestParseError for unknown key")
    except NestParseError as e:
        assert "onion_skn" in str(e)


def test_holding_roundtrip():
    from pml.yaml_formatter import format_nest_yaml

    source = """
Nest:
  algorithm: guillotine
  holding:
    onion_skin: 0.3mm
  Sheet:
    width: 1220mm
    height: 1220mm
    thickness: 19mm
  parts:
    - name: small
      width: 200mm
      height: 100mm
    - name: large
      width: 600mm
      height: 400mm
      holding:
        tab_count: 6
        tab_height: 3mm
"""
    job = parse_nest_yaml(source)
    yaml_out = format_nest_yaml(job)
    job2 = parse_nest_yaml(yaml_out)
    assert job2.holding is not None
    assert job2.holding.onion_skin_mm == 0.3
    assert job2.parts[0].holding is not None
    assert job2.parts[0].holding.onion_skin_mm == 0.3
    assert job2.parts[1].holding is not None
    assert job2.parts[1].holding.tab_count == 6
    assert job2.parts[1].holding.tab_height_mm == 3.0
