# mill_ui: 3138ae4
# generated: 2026-01-25

# Waste cuts demo: single panel with waste decomposition
# Remaining sheet material is cut into usable rectangular pieces

sheet 1200mm 800mm 19mm

rect panel at 400mm,400mm size 600mm,500mm
    profile outside through tabs 4 height 3mm

waste_cuts
    min_size 150mm 150mm
    margin 15mm
    tabs 4 height 3mm
    strategy largest
