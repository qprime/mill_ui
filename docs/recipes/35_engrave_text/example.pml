# mill_ui: f56beea
# generated: 2026-01-26

# Recipe 35: Engrave Text
# Demonstrates single-stroke text engraving with Hershey fonts and labeled rulers

sheet 300mm 200mm 18mm margin 10mm

frame 25mm
    rect ruler_area
        measurement_edge edges [bottom, left] unit metric labels depth 0.3mm

inset 30mm
    split_horizontal 2 gap 10mm
        rect bottom_section
            engrave_text text "MILL_UI" height 8mm depth 0.3mm alignment center
        rect top_section
            engrave_text text "FRONT" height 12mm depth 0.5mm alignment center
