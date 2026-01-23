template shaker
    params
        stile_w 57mm
        rail_h 57mm
        panel_recess 6mm
        panel_style pocket

    rect door
        profile outside through
        frame ${stile_w}
            ${panel_style} ${panel_recess}
