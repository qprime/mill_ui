# mill_ui: d5772ab
# generated: 2026-01-26

# Recipe 36: Sparse Ruler Labels
# Demonstrates measurement rulers with only major ticks and sparse labels (20, 40, 60...)

sheet 300mm 200mm 18mm margin 10mm

frame 25mm
    rect ruler_area
        measurement_edge edges [bottom, left] unit metric minor_ticks false labels label_interval 2 label_offset 4.5mm depth 0.3mm

inset 30mm
    split_horizontal 2 gap 10mm
        rect bottom_section
            engrave_text text "SPARSE LABELS" height 6mm depth 0.3mm alignment center
        rect top_section
            engrave_text text "20, 40, 60..." height 8mm depth 0.3mm alignment center
