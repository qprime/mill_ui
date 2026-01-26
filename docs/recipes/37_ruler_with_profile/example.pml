# mill_ui: d5772ab
# generated: 2026-01-26

# Recipe 37: Ruler Variations on Cut Parts
# Three 200x200mm parts cut from a sheet, each with different ruler styles
# Note: 'at' specifies center coordinates

sheet 700mm 250mm 18mm margin 10mm

# Part centers: Y = 125mm (centered on 250mm sheet)
# X positions: 120mm, 350mm, 580mm (200mm parts with 30mm gaps)

# Part 1: Small and large ticks, no labels
rect part_a at 120mm,125mm size 200mm,200mm profile through outside
    frame 12mm
        rect ruler_a
            measurement_edge edges [bottom, left] unit metric depth 0.3mm

# Part 2: Small and large ticks, sparse labels (0, 20, 40...)
rect part_b at 350mm,125mm size 200mm,200mm profile through outside
    frame 12mm
        rect ruler_b
            measurement_edge edges [bottom, left] unit metric labels label_interval 2 label_offset 4.5mm depth 0.3mm

# Part 3: Large ticks only, all labels
rect part_c at 580mm,125mm size 200mm,200mm profile through outside
    frame 12mm
        rect ruler_c
            measurement_edge edges [bottom, left] unit metric minor_ticks false labels label_offset 4.5mm depth 0.3mm
