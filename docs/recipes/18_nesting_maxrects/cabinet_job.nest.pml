# Recipe 18: Cabinet production run with MaxRects nesting
#
# This job nests 37 cabinet parts onto half sheets (48.5" x 49")
# using the MaxRects algorithm with Contact Point heuristic.
#
# MaxRects typically achieves higher utilization than guillotine
# by maintaining a list of free rectangles and packing more tightly.

nest maxrects
    sheet 1232mm 1245mm 19mm
    kerf 6.35mm
    margin 10mm

    parts
        large_door 457mm 597mm x20
            template Shaker
                stile_w 57mm
                rail_h 57mm
                panel_recess 6mm

        small_door 305mm 203mm x15

        tall_door 457mm 914mm x2
            template Shaker
                stile_w 57mm
                rail_h 57mm
                panel_recess 6mm
