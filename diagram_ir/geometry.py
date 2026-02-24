from __future__ import annotations


def rounded_rect_path(
    x: float, y: float, w: float, h: float, radius_tl: float, radius_tr: float, radius_br: float, radius_bl: float
) -> str:
    rtl = min(radius_tl, w / 2, h / 2)
    rtr = min(radius_tr, w / 2, h / 2)
    rbr = min(radius_br, w / 2, h / 2)
    rbl = min(radius_bl, w / 2, h / 2)

    parts = [f"M {x + rtl:.3f} {y:.3f}"]
    parts.append(f"L {x + w - rtr:.3f} {y:.3f}")
    if rtr > 0:
        parts.append(f"A {rtr:.3f} {rtr:.3f} 0 0 1 {x + w:.3f} {y + rtr:.3f}")
    parts.append(f"L {x + w:.3f} {y + h - rbr:.3f}")
    if rbr > 0:
        parts.append(f"A {rbr:.3f} {rbr:.3f} 0 0 1 {x + w - rbr:.3f} {y + h:.3f}")
    parts.append(f"L {x + rbl:.3f} {y + h:.3f}")
    if rbl > 0:
        parts.append(f"A {rbl:.3f} {rbl:.3f} 0 0 1 {x:.3f} {y + h - rbl:.3f}")
    parts.append(f"L {x:.3f} {y + rtl:.3f}")
    if rtl > 0:
        parts.append(f"A {rtl:.3f} {rtl:.3f} 0 0 1 {x + rtl:.3f} {y:.3f}")
    parts.append("Z")
    return " ".join(parts)


__all__ = ["rounded_rect_path"]
