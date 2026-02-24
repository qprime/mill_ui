#!/usr/bin/env python3

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from xml.etree import ElementTree as ET


def parse_path_to_points(path_d: str) -> list[tuple[float, float]]:
    points = []
    parts = path_d.replace(",", " ").split()
    i = 0
    while i < len(parts):
        cmd = parts[i]
        if cmd in ("M", "L"):
            points.append((float(parts[i + 1]), float(parts[i + 2])))
            i += 3
        elif cmd == "Z":
            i += 1
        else:
            try:
                points.append((float(parts[i]), float(parts[i + 1])))
                i += 2
            except (ValueError, IndexError):
                i += 1
    return points


def generate_diagnostic_svg(
    svg_path: Path,
    tool_diameter: float = 3.175,
    output_path: Path | None = None,
) -> str:
    tree = ET.parse(svg_path)
    root = tree.getroot()

    ET.register_namespace("", "http://www.w3.org/2000/svg")

    profile_group = root.find(".//{http://www.w3.org/2000/svg}g[@id='PROFILE_CUTS']")
    if profile_group is None:
        profile_group = root.find(".//g[@id='PROFILE_CUTS']")

    profile_paths = []
    if profile_group is not None:
        for elem in profile_group:
            if elem.tag.endswith("path") or elem.tag == "path":
                d = elem.get("d", "")
                if d:
                    profile_paths.append(d)

    viewbox = root.get("viewBox", "0 0 1000 800")
    vb_parts = viewbox.split()
    vb_width = float(vb_parts[2])
    vb_height = float(vb_parts[3])

    svg = ET.Element(
        "svg",
        {
            "xmlns": "http://www.w3.org/2000/svg",
            "viewBox": f"0 0 {vb_width} {vb_height + 350}",
            "width": f"{vb_width}mm",
            "height": f"{vb_height + 350}mm",
        },
    )

    style = ET.SubElement(svg, "style")
    style.text = """
        .background { fill: #1a1a2e; }
        .part-fill { fill: #c4a574; stroke: #8b7355; stroke-width: 0.5; }
        .title { fill: #e0e0e0; font-size: 16px; font-family: monospace; }
        .label { fill: #b0b0b0; font-size: 11px; font-family: monospace; }
    """

    ET.SubElement(
        svg, "rect", {"x": "0", "y": "0", "width": str(vb_width), "height": str(vb_height + 350), "class": "background"}
    )

    title = ET.SubElement(svg, "text", {"x": "20", "y": "25", "class": "title"})
    title.text = "FINISHED PARTS - Material Remaining After Cutting"

    subtitle = ET.SubElement(svg, "text", {"x": "20", "y": "42", "class": "label"})
    subtitle.text = f"Tool: {tool_diameter}mm endmill | This is what you hold in your hand"

    main_group = ET.SubElement(svg, "g", {"id": "PARTS", "transform": "translate(0, 50)"})

    for path_d in profile_paths:
        ET.SubElement(main_group, "path", {"d": path_d, "class": "part-fill"})

    part_labels = [
        (250, 596, "FRONT"),
        (460, 596, "BACK"),
        (639, 596, "LEFT SIDE"),
        (787, 596, "RIGHT SIDE"),
        (244, 473, "BOTTOM"),
    ]
    for x, y, text in part_labels:
        label = ET.SubElement(
            main_group,
            "text",
            {
                "x": str(x),
                "y": str(y),
                "class": "label",
                "text-anchor": "middle",
            },
        )
        label.text = text

    if len(profile_paths) >= 3:
        mating_group = ET.SubElement(svg, "g", {"id": "MATING_TEST", "transform": f"translate(0, {vb_height + 70})"})

        mating_title = ET.SubElement(mating_group, "text", {"x": "20", "y": "0", "class": "title"})
        mating_title.text = "MATING TEST - FRONT (finger_first) + LEFT SIDE (notch_first)"

        front_path = profile_paths[0]
        left_side_path = profile_paths[2]

        front_pts = parse_path_to_points(front_path)
        left_pts = parse_path_to_points(left_side_path)

        if front_pts and left_pts:
            front_xs = [p[0] for p in front_pts]
            front_ys = [p[1] for p in front_pts]
            left_xs = [p[0] for p in left_pts]
            left_ys = [p[1] for p in left_pts]

            front_right_x = max(front_xs)
            front_left_x = min(front_xs)
            left_left_x = min(left_xs)
            left_right_x = max(left_xs)

            front_y_min = min(front_ys)
            left_y_min = min(left_ys)

            front_width = front_right_x - front_left_x
            left_width = left_right_x - left_left_x

            scale = 2.5
            base_y = 30

            finger_depth = 6.0
            overlap = finger_depth * 0.25 * scale

            front_base_x = 50
            left_base_x = front_base_x + front_width * scale - overlap

            def transform_front(x, y):
                new_x = front_base_x + (x - front_left_x) * scale
                new_y = base_y + (y - front_y_min) * scale
                return new_x, new_y

            def transform_left(x, y):
                new_x = left_base_x + (x - left_left_x) * scale
                new_y = base_y + (y - left_y_min) * scale
                return new_x, new_y

            front_transformed = [transform_front(x, y) for x, y in front_pts]
            front_path_d = "M " + " L ".join(f"{x:.3f} {y:.3f}" for x, y in front_transformed) + " Z"

            left_transformed = [transform_left(x, y) for x, y in left_pts]
            left_path_d = "M " + " L ".join(f"{x:.3f} {y:.3f}" for x, y in left_transformed) + " Z"

            ET.SubElement(mating_group, "path", {"d": front_path_d, "fill": "#c4a574", "stroke": "none"})
            ET.SubElement(mating_group, "path", {"d": left_path_d, "fill": "#a08060", "stroke": "none"})

            front_center_x = front_base_x + front_width * scale / 2
            left_center_x = left_base_x + left_width * scale / 2
            label_y = base_y + 240

            front_label = ET.SubElement(
                mating_group,
                "text",
                {"x": str(front_center_x), "y": str(label_y), "class": "label", "text-anchor": "middle"},
            )
            front_label.text = "FRONT (finger_first)"

            left_label = ET.SubElement(
                mating_group,
                "text",
                {"x": str(left_center_x), "y": str(label_y), "class": "label", "text-anchor": "middle"},
            )
            left_label.text = "LEFT SIDE (notch_first)"

            gap_note = ET.SubElement(mating_group, "text", {"x": "50", "y": str(label_y + 20), "class": "label"})
            gap_note.text = "Mating edges touch - fingers interlock with notches (0.15mm clearance)"

    ET.indent(svg, space="  ")
    result = ET.tostring(svg, encoding="unicode")

    if output_path:
        output_path.write_text(result)
        print(f"Wrote diagnostic SVG to {output_path}")

    return result


def main():
    parser = argparse.ArgumentParser(description="Generate finger joint diagnostic visualization")
    parser.add_argument("--recipe", required=True, help="Path to recipe directory")
    parser.add_argument("--tool-diameter", type=float, default=3.175, help="Tool diameter in mm")
    parser.add_argument("--output", help="Output path (default: recipe/output/diagnostic.svg)")
    args = parser.parse_args()

    recipe_path = Path(args.recipe)
    if not recipe_path.exists():
        print(f"Recipe path not found: {recipe_path}", file=sys.stderr)
        sys.exit(1)

    svg_files = list((recipe_path / "output").glob("*.svg"))
    svg_files = [f for f in svg_files if "diagnostic" not in f.name]

    if not svg_files:
        print(f"No SVG files found in {recipe_path / 'output'}", file=sys.stderr)
        sys.exit(1)

    svg_path = svg_files[0]
    output_path = Path(args.output) if args.output else recipe_path / "output" / "diagnostic.svg"

    generate_diagnostic_svg(svg_path, args.tool_diameter, output_path)


if __name__ == "__main__":
    main()
