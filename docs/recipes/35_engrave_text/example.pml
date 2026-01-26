# mill_ui: d3abd20
# generated: 2026-01-26

sheet 300mm 200mm 18mm margin 10mm

rect label_demo
    engrave_text text "FRONT" height 10mm depth 0.5mm alignment center

inset 60mm
    rect centered_text
        engrave_text text "CENTERED" height 6mm depth 0.3mm alignment center

frame 20mm
    rect ruler_with_labels
        measurement_edge edges [bottom, left] unit metric labels depth 0.3mm
