# mill_ui: 7f436d3
# generated: 2026-01-26

# Waste cuts demo: single panel with waste decomposition
# Remaining sheet material is cut into usable rectangular pieces
# The sheet margin (15mm) is inherited by waste_cuts automatically

sheet 1200mm 800mm 19mm margin 15mm

rect panel at 400mm,400mm size 600mm,500mm
    profile outside through tabs 4 height 3mm

waste_cuts
    min_size 150mm 150mm
    tabs 4 height 3mm
    strategy largest
