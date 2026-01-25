# mill_ui: b93206f
# generated: 2026-01-25

# Simple rectangular cutout with holding tabs
# Tabs prevent the part from moving during cutting

sheet 600mm 400mm 19mm

# Main cutout: 400mm x 250mm rectangle with 4 tabs
# Tabs are 3mm high and 12mm wide
rect cutout at 300mm,200mm size 400mm,250mm profile through outside tabs 4 height 3mm width 12mm
