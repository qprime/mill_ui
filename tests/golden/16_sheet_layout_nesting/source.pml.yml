# mill_ui: 866253f
# generated: 2026-01-25

# Sheet Layout: Nested Shaker Cabinet Doors and Drawer Fronts
# Half-sheet MDF: 1245mm x 1232mm (49" x 48.5") x 19mm (3/4")
# 10mm no-carve margin on all sides for workholding
# 6mm kerf gap between parts
#
# Layout:
#   - 4 shaker cabinet doors (457mm x 597mm / 18" x 23.5") in a 2x2 grid
#   - Drawer fronts (254mm x 152mm / 10" x 6") in right waste strip
#
# Shaker style: 57mm (2.25") stile/rail width, 6mm panel recess

sheet 1245mm 1232mm 19mm margin 0mm

# === Layout Constants ===
# Margin: 10mm
# Kerf: 6mm
# Door: 457mm x 597mm (18" x 23.5")
# Panel: 343mm x 483mm (door - 2*57mm frame)
# Drawer: 254mm x 152mm (10" x 6")
# Drawer panel: 178mm x 76mm (drawer - 2*38mm frame)

# === ROW 1 (bottom): Two cabinet doors ===
# y_center = margin + door_h/2 = 10 + 298.5 = 308.5

# Door 1 (bottom-left): x_center = 10 + 228.5 = 238.5
rect door1_panel at 238.5mm,308.5mm size 343mm,483mm pocket 6mm
rect door1 at 238.5mm,308.5mm size 457mm,597mm profile through outside tabs 6 height 3mm width 12mm

# Door 2 (bottom-right): x_center = 10 + 457 + 6 + 228.5 = 701.5
rect door2_panel at 701.5mm,308.5mm size 343mm,483mm pocket 6mm
rect door2 at 701.5mm,308.5mm size 457mm,597mm profile through outside tabs 6 height 3mm width 12mm

# === ROW 2 (top): Two cabinet doors ===
# y_center = 10 + 597 + 6 + 298.5 = 911.5

# Door 3 (top-left)
rect door3_panel at 238.5mm,911.5mm size 343mm,483mm pocket 6mm
rect door3 at 238.5mm,911.5mm size 457mm,597mm profile through outside tabs 6 height 3mm width 12mm

# Door 4 (top-right)
rect door4_panel at 701.5mm,911.5mm size 343mm,483mm pocket 6mm
rect door4 at 701.5mm,911.5mm size 457mm,597mm profile through outside tabs 6 height 3mm width 12mm

# === DRAWER FRONTS in right waste strip ===
# Right waste strip: x from 930 to 1235 (305mm wide, enough for 254mm drawers)
# Usable height: 1212mm, drawer height 152mm + 6mm kerf = 158mm
# Can fit: floor(1212 / 158) = 7 drawers vertically
# x_center = 930 + 6 + 127 = 1063

# Drawer column (7 drawers stacked)
rect drawer1_panel at 1063mm,86mm size 178mm,76mm pocket 4mm
rect drawer1 at 1063mm,86mm size 254mm,152mm profile through outside tabs 4 height 3mm width 10mm

rect drawer2_panel at 1063mm,244mm size 178mm,76mm pocket 4mm
rect drawer2 at 1063mm,244mm size 254mm,152mm profile through outside tabs 4 height 3mm width 10mm

rect drawer3_panel at 1063mm,402mm size 178mm,76mm pocket 4mm
rect drawer3 at 1063mm,402mm size 254mm,152mm profile through outside tabs 4 height 3mm width 10mm

rect drawer4_panel at 1063mm,560mm size 178mm,76mm pocket 4mm
rect drawer4 at 1063mm,560mm size 254mm,152mm profile through outside tabs 4 height 3mm width 10mm

rect drawer5_panel at 1063mm,718mm size 178mm,76mm pocket 4mm
rect drawer5 at 1063mm,718mm size 254mm,152mm profile through outside tabs 4 height 3mm width 10mm

rect drawer6_panel at 1063mm,876mm size 178mm,76mm pocket 4mm
rect drawer6 at 1063mm,876mm size 254mm,152mm profile through outside tabs 4 height 3mm width 10mm

rect drawer7_panel at 1063mm,1034mm size 178mm,76mm pocket 4mm
rect drawer7 at 1063mm,1034mm size 254mm,152mm profile through outside tabs 4 height 3mm width 10mm
