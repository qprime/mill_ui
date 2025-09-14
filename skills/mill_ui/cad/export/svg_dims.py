# path: skills/mill_ui/cad/export/svg_dims.py
from __future__ import annotations
from typing import List, Dict, Any, Tuple, Optional
from collections import Counter

# ===== Public API =========================================================

def render_svg_with_dims(
    panel_w: float,
    panel_h: float,
    panel_t: float,
    placements: List[Dict[str, Any]],
    hints: Dict[str, Any] | None = None,
    *,
    show_gaps: bool = True,
    show_sizes: bool = True,
    show_depths: bool = True,
    tol_mm: float = 0.25,
    circle_label_threshold: int = 8,
) -> str:
    """
    Drafting-like SVG of 2.5D sheet work:
      - Panel outline, placed items
      - All CAM features: profiles, pockets, regions, anchors, holes
      - Shared seams (merged edges) drawn once, labeled 'Shared'
      - Size labels (W/H, ⌀), depth labels, stile/rail thickness
      - Legend rendered to the RIGHT, outside the panel
    """
    body: List[str] = []
    legend_lines: List[str] = []

    # Panel
    body.append(_rect(0, 0, panel_w, panel_h, cls="panel"))

    # Placed outer items and size labels
    rects_bb: List[Tuple[float,float,float,float]] = []
    for pl in placements or []:
        it = pl.get("item", {})
        cx, cy = _xy(pl.get("center_xy_mm", (0.0,0.0)))
        if it.get("kind") == "shape":
            t = str(it.get("type","")).lower()
            g = it.get("geometry") or {}
            if t == "rect":
                w, h = float(g.get("w_mm",0.0)), float(g.get("h_mm",0.0))
                minx, miny = cx - w/2, cy - h/2
                rects_bb.append((minx,miny,minx+w,miny+h))
                body.append(_rect(minx,miny,w,h,cls="item"))
                if show_sizes and w>0 and h>0:
                    body.append(_box_labels(minx,miny,w,h))
            elif t == "circle":
                d = float(g.get("diameter_mm",0.0)); r=d/2
                body.append(_circ(cx,cy,r,cls="item"))
        elif it.get("kind") == "template" and str(it.get("type","")).lower()=="shaker":
            p=it.get("params",{}) or {}
            w,h=float(p.get("outer_w",0.0)), float(p.get("outer_h",0.0))
            minx, miny = cx - w/2, cy - h/2
            rects_bb.append((minx,miny,minx+w,miny+h))
            body.append(_rect(minx,miny,w,h,cls="item"))
            if show_sizes and w>0 and h>0:
                body.append(_box_labels(minx,miny,w,h))

    # Features
    circle_diams: List[float] = []
    outer_rects: List[Dict[str,Any]] = []
    inner_rects: List[Dict[str,Any]] = []

    if hints:
        # profiles
        for rec in (hints.get("profiles") or []):
            _draw_rect_or_circle(body, rec, "feature-profile")
            _label_depth_if_any(body, rec)
            _size_label_if_rect(body, rec)
            if _is_rect(rec): outer_rects.append(rec)
        # pockets
        for rec in (hints.get("pockets") or []):
            t = str(rec.get("shape","")).lower()
            if t=="region":
                _draw_region(body, rec, circle_diams)
                _label_depth_if_any(body, rec)
            elif t=="rect":
                _draw_rect_or_circle(body, rec, "feature-pocket")
                _label_depth_if_any(body, rec)
                _size_label_if_rect(body, rec)
                inner_rects.append(rec)
            elif t=="circle":
                _draw_rect_or_circle(body, rec, "feature-anchor")
                _label_depth_if_any(body, rec)
                d=float((rec.get("geometry") or {}).get("diameter_mm",0.0))
                if d>0: circle_diams.append(round(d,1))
        # holes
        for rec in (hints.get("holes") or []):
            _draw_rect_or_circle(body, rec, "feature-hole")
            _label_depth_if_any(body, rec)
            d=float((rec.get("geometry") or {}).get("diameter_mm",0.0))
            if d>0: circle_diams.append(round(d,1))

        # stile/rail labels (outer vs inner rect match)
        _label_stile_rail(body, outer_rects, inner_rects)

        # shared seams (from outer rects only, tolerance-based)
        body.extend(_draw_shared_seams(outer_rects, tol=tol_mm))

    # circle labeling vs legend grouping
    if hints and circle_diams:
        if len(circle_diams) <= circle_label_threshold:
            _label_circle_diams_per_feature(body, hints)
        else:
            counts = Counter(circle_diams)
            legend_lines.append("Anchors and holes: " + ", ".join(f"⌀ {k:.1f} mm × {v}" for k,v in sorted(counts.items())))

    # global dims and gaps
    if show_sizes:
        body.extend(_dim_linear_h(0, panel_h+10, 0, panel_w, f"W {panel_w:.1f} mm"))
        body.extend(_dim_linear_v(panel_w+10, 0, 0, panel_h, f"H {panel_h:.1f} mm"))
    if rects_bb:
        body.extend(_render_gaps(rects_bb, panel_w, panel_h, tol=tol_mm))

    # legend lines
    legend_lines.insert(0, f"Sheet {panel_t:.1f} mm")
    if show_depths and hints:
        depths = sorted({float(p.get("depth_mm",0.0)) for p in (hints.get("pockets") or []) if "depth_mm" in p})
        if depths:
            legend_lines.append("Pocket depths: " + ", ".join(f"{d:.1f} mm" for d in depths))

    # assemble final svg with legend to the right
    legend_w, legend_h = _legend_box_size(legend_lines)
    margin = 16.0
    svg_w = panel_w + legend_w + margin*2
    svg_h = panel_h

    out: List[str] = []
    out.append(_svg_header(svg_w, svg_h))
    out.append(f'  <g transform="scale(1,-1) translate(0,-{panel_h})">\n')
    out.extend(body)
    out.append('  </g>\n')
    legend_x = panel_w + margin
    legend_y = panel_h - margin
    out.append(_legend_upright(legend_x, legend_y, legend_lines, legend_w, legend_h))
    out.append(_svg_footer())
    return "".join(out)

# ===== helpers ============================================================

def _is_rect(rec: Dict[str, Any]) -> bool:
    return str(rec.get("shape","")).lower() == "rect"

def _xy(v) -> Tuple[float,float]:
    if isinstance(v,(list,tuple)) and len(v)==2:
        return float(v[0]), float(v[1])
    return 0.0, 0.0

def _svg_header(w,h):
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">\n'
        f'    <style>\n'
        f'      .panel {{ fill:none; stroke:#888; stroke-width:0.7; }}\n'
        f'      .item  {{ fill:none; stroke:#444; stroke-width:0.5; }}\n'
        f'      .feature-profile {{ fill:none; stroke:#000; stroke-width:0.9; }}\n'
        f'      .feature-pocket  {{ fill:none; stroke:#0a0; stroke-width:0.7; stroke-dasharray:3 2; }}\n'
        f'      .feature-anchor  {{ fill:none; stroke:#a60; stroke-width:0.7; stroke-dasharray:2 2; }}\n'
        f'      .feature-hole    {{ fill:none; stroke:#c00; stroke-width:0.9; }}\n'
        f'      .shared-edge     {{ stroke:#06c; stroke-width:1.2; stroke-dasharray:4 2; }}\n'
        f'      .dim {{ stroke:#06c; stroke-width:0.7; fill:none; }}\n'
        f'      .text {{ fill:#06c; font-size:6px; font-family:monospace; }}\n'
        f'      .label {{ fill:#333; font-size:6px; font-family:monospace; }}\n'
        f'      .legend-bg {{ fill:#f7f7f7; stroke:#aaa; }}\n'
        f'    </style>\n'
    )

def _svg_footer(): return "</svg>\n"

def _rect(x,y,w,h,cls="item"): return f'    <rect class="{cls}" x="{x:.3f}" y="{y:.3f}" width="{w:.3f}" height="{h:.3f}" />\n'
def _circ(cx,cy,r,cls="item"): return f'    <circle class="{cls}" cx="{cx:.3f}" cy="{cy:.3f}" r="{r:.3f}" />\n'
def _text(x,y,s,cls="label"):  return f'    <text class="{cls}" x="{x:.3f}" y="{y:.3f}" transform="scale(1,-1) translate(0,{-(2*y):.3f})">{s}</text>\n'

def _arrow_head(x,y,dx,dy,size=3.0):
    s=size
    return (f'    <path class="dim" d="M {x:.3f} {y:.3f} l { -0.6*dx*s:.3f} { -0.6*dy*s:.3f} M {x:.3f} {y:.3f} l { 0.6*dx*s:.3f} { 0.6*dy*s:.3f}" />\n')

def _dim_linear_h(x_text,y,xa,xb,label):
    xa,xb=float(xa),float(xb); dx=1.0 if xb>=xa else -1.0
    return [f'    <line class="dim" x1="{xa:.3f}" y1="{y:.3f}" x2="{xb:.3f}" y2="{y:.3f}" />\n',
            _arrow_head(xa,y,+dx,0), _arrow_head(xb,y,-dx,0),
            _text(x_text,y+3,label,cls="text")]

def _dim_linear_v(x,y_text,ya,yb,label):
    ya,yb=float(ya),float(yb); dy=1.0 if yb>=ya else -1.0
    return [f'    <line class="dim" x1="{x:.3f}" y1="{ya:.3f}" x2="{x:.3f}" y2="{yb:.3f}" />\n',
            _arrow_head(x,ya,0,+dy), _arrow_head(x,yb,0,-dy),
            _text(x+2,y_text+3,label,cls="text")]

def _legend_box_size(lines: List[str]) -> Tuple[float,float]:
    pad_x,pad_y=3.0,3.0; line_h=8.0
    est = max((len(s) for s in lines), default=0)*4.0
    return max(180.0, est+2*pad_x), line_h*max(1,len(lines))+2*pad_y

def _legend_upright(x: float, y_top: float, lines: List[str], legend_w: float, legend_h: float) -> str:
    out=[]; pad_x,pad_y=3.0,3.0; x_bg=x-pad_x; y_bg=y_top-legend_h+pad_y
    out.append('  <g>\n')
    out.append(f'    <rect class="legend-bg" x="{x_bg:.1f}" y="{y_bg:.1f}" width="{legend_w:.1f}" height="{legend_h:.1f}" />\n')
    line_h=8.0
    for i,t in enumerate(lines):
        out.append(f'    <text class="label" x="{x:.1f}" y="{y_top-(i*line_h):.1f}">{t}</text>\n')
    out.append('  </g>\n')
    return "".join(out)

# draw features
def _draw_rect_or_circle(body: List[str], rec: Dict[str, Any], style: str):
    t=str(rec.get("shape","")).lower(); cx,cy=_xy(rec.get("center_xy_mm")); g=rec.get("geometry") or {}
    if t=="rect":
        w,h=float(g.get("w_mm",0.0)), float(g.get("h_mm",0.0))
        body.append(_rect(cx-w/2, cy-h/2, w, h, cls=style))
    elif t=="circle":
        d=float(g.get("diameter_mm",0.0)); body.append(_circ(cx,cy,d/2.0, cls=style))

def _draw_region(body: List[str], rec: Dict[str, Any], circle_diams: List[float]):
    geom=rec.get("geometry") or {}; center=_xy(rec.get("center_xy_mm"))
    outer=geom.get("outer") or {}; holes=geom.get("holes") or []
    oc=_xy(outer.get("center_xy_mm", center)); og=outer.get("geometry") or {}
    if str(outer.get("type","")).lower()=="rect":
        w,h=float(og.get("w_mm",0.0)), float(og.get("h_mm",0.0))
        body.append(_rect(oc[0]-w/2, oc[1]-h/2, w, h, cls="feature-pocket"))
        body.append(_box_labels(oc[0]-w/2, oc[1]-h/2, w, h))
    elif str(outer.get("type","")).lower()=="circle":
        d=float(og.get("diameter_mm",0.0)); body.append(_circ(oc[0], oc[1], d/2.0, cls="feature-pocket"))
        circle_diams.append(round(d,1))
    for hr in holes:
        hc=_xy(hr.get("center_xy_mm", center)); hg=hr.get("geometry") or {}
        if str(hr.get("type","")).lower()=="rect":
            w,h=float(hg.get("w_mm",0.0)), float(hg.get("h_mm",0.0))
            body.append(_rect(hc[0]-w/2, hc[1]-h/2, w, h, cls="feature-pocket"))
            body.append(_box_labels(hc[0]-w/2, hc[1]-h/2, w, h))
        elif str(hr.get("type","")).lower()=="circle":
            d=float(hg.get("diameter_mm",0.0)); body.append(_circ(hc[0], hc[1], d/2.0, cls="feature-pocket"))
            circle_diams.append(round(d,1))

def _label_depth_if_any(body: List[str], rec: Dict[str, Any]):
    d = rec.get("depth_mm")
    if d is None:
        return
    val = float(d)
    if val <= 0:
        return
    t = str(rec.get("shape","")).lower()
    cx, cy = _xy(rec.get("center_xy_mm"))
    g = rec.get("geometry") or {}
    label = f"d={val:.1f}mm"
    if t == "rect":
        w, h = float(g.get("w_mm", 0.0)), float(g.get("h_mm", 0.0))
        body.append(_text(cx - w/2 + 2, cy + h/2 - 7, label))
    elif t == "circle":
        r = float(g.get("diameter_mm", 0.0)) / 2.0
        body.append(_text(cx + r + 2, cy, label))

def _size_label_if_rect(body: List[str], rec: Dict[str, Any]):
    if str(rec.get("shape","")).lower()!="rect": return
    cx,cy=_xy(rec.get("center_xy_mm")); g=rec.get("geometry") or {}
    w,h=float(g.get("w_mm",0.0)), float(g.get("h_mm",0.0))
    if w<=0 or h<=0: return
    body.append(_text(cx - w/2 + 2, cy - h/2 + 7, f"W={w:.1f}mm  H={h:.1f}mm"))

def _label_circle_diams_per_feature(body: List[str], hints: Dict[str, Any]):
    for bucket in ("pockets","holes"):
        for rec in (hints.get(bucket) or []):
            if str(rec.get("shape","")).lower()!="circle": continue
            cx,cy=_xy(rec.get("center_xy_mm"))
            d=float((rec.get("geometry") or {}).get("diameter_mm",0.0))
            if d<=0: continue
            body.append(_text(cx - d*0.5, cy + 6, f"⌀={d:.1f}mm"))

# stile/rail
def _label_stile_rail(body: List[str], outers: List[Dict[str,Any]], inners: List[Dict[str,Any]], tol: float=0.5):
    imap: Dict[Tuple[int,int], List[Tuple[float,float]]] = {}
    def _k(cx,cy): return (int(round(cx*1000)), int(round(cy*1000)))
    for rec in inners:
        if str(rec.get("shape","")).lower()!="rect": continue
        cx,cy=_xy(rec.get("center_xy_mm")); g=rec.get("geometry") or {}
        imap.setdefault(_k(cx,cy), []).append((float(g.get("w_mm",0.0)), float(g.get("h_mm",0.0))))
    for rec in outers:
        if str(rec.get("shape","")).lower()!="rect": continue
        cx,cy=_xy(rec.get("center_xy_mm")); key=_k(cx,cy)
        if key not in imap: continue
        g=rec.get("geometry") or {}; w_out,h_out=float(g.get("w_mm",0.0)), float(g.get("h_mm",0.0))
        w_in,h_in=max(imap[key], key=lambda wh: wh[0]*wh[1])
        stile=max(0.0, 0.5*(w_out - w_in)); rail=max(0.0, 0.5*(h_out - h_in))
        body.append(_text(cx - w_out/2 + 4, cy, f"Stile={stile:.1f}mm"))
        body.append(_text(cx, cy + h_out/2 - 6, f"Rail={rail:.1f}mm"))

# shared seams (from profile rects)
def _draw_shared_seams(outer_rects: List[Dict[str,Any]], tol: float=0.1) -> List[str]:
    out: List[str] = []
    # Build list of edges
    edges = []
    for rec in outer_rects:
        cx,cy=_xy(rec.get("center_xy_mm")); g=rec.get("geometry") or {}
        w,h=float(g.get("w_mm",0.0)), float(g.get("h_mm",0.0))
        minx, miny = cx - w/2, cy - h/2; maxx, maxy = cx + w/2, cy + h/2
        rid = rec.get("id") or f"R@{len(edges)}"
        edges += [
            ("v", minx, miny, maxy, rid),
            ("v", maxx, miny, maxy, rid),
            ("h", miny, minx, maxx, rid),
            ("h", maxy, minx, maxx, rid),
        ]
    # Index by rounded coord
    def K(o,c): return (o, int(round(c/tol)))
    buckets: Dict[Tuple[str,int], List[Tuple[str,float,float,float,str]]] = {}
    for e in edges:
        buckets.setdefault(K(e[0],e[1]), []).append(e)
    # draw seams where two rects share same coord with overlap
    for key, lst in buckets.items():
        if len(lst) < 2: continue
        n=len(lst)
        for i in range(n):
            for j in range(i+1,n):
                o, c, a1, b1, r1 = lst[i]
                _o, _c, a2, b2, r2 = lst[j]
                if r1==r2 or abs(c-_c)>tol or o!=_o: continue
                lo=max(min(a1,b1), min(a2,b2)); hi=min(max(a1,b1), max(a2,b2))
                if hi-lo <= 0: continue
                if o=="v":
                    out.append(f'    <line class="shared-edge" x1="{c:.3f}" y1="{lo:.3f}" x2="{c:.3f}" y2="{hi:.3f}" />\n')
                    out.append(_text(c+2, (lo+hi)/2, "Shared", cls="text"))
                else:
                    out.append(f'    <line class="shared-edge" x1="{lo:.3f}" y1="{c:.3f}" x2="{hi:.3f}" y2="{c:.3f}" />\n')
                    out.append(_text((lo+hi)/2, c+2, "Shared", cls="text"))
    return out

# gaps & legend helpers
def _legend_box_size(lines: List[str]) -> Tuple[float,float]:
    pad_x,pad_y=3.0,3.0; line_h=8.0
    est = max((len(s) for s in lines), default=0)*4.0
    return max(180.0, est+2*pad_x), line_h*max(1,len(lines))+2*pad_y

def _legend_upright(x: float, y_top: float, lines: List[str], legend_w: float, legend_h: float) -> str:
    out=[]; pad_x,pad_y=3.0,3.0; x_bg=x-pad_x; y_bg=y_top-legend_h+pad_y
    out.append('  <g>\n')
    out.append(f'    <rect class="legend-bg" x="{x_bg:.1f}" y="{y_bg:.1f}" width="{legend_w:.1f}" height="{legend_h:.1f}" />\n')
    line_h=8.0
    for i,t in enumerate(lines):
        out.append(f'    <text class="label" x="{x:.1f}" y="{y_top-(i*line_h):.1f}">{t}</text>\n')
        out.append('  </g>\n')
    return "".join(out)

def _render_gaps(rects, panel_w, panel_h, tol):
    out=[]
    xs=sorted({a for (a,_,_,_) in rects}|{b for (_,_,b,_) in rects})
    ys=sorted({a for (_,a,_,_) in rects}|{b for (_,_,_,b) in rects})
    for i in range(1,len(xs)):
        a,b=xs[i-1],xs[i]; gap=b-a
        if gap>tol and _column_is_open(rects,a,b,tol):
            y=panel_h*0.5+12; out.extend(_dim_linear_h(a,y,a,b,f"{gap:.1f} mm"))
    for j in range(1,len(ys)):
        a,b=ys[j-1],ys[j]; gap=b-a
        if gap>tol and _row_is_open(rects,a,b,tol):
            x=panel_w*0.5+12; out.extend(_dim_linear_v(x,a,a,b,f"{gap:.1f} mm"))
    return out

def _column_is_open(rects,x0,x1,tol):
    midx=0.5*(x0+x1)
    for (minx,miny,maxx,maxy) in rects:
        if minx-tol<midx<maxx+tol: return False
    return True

def _row_is_open(rects,y0,y1,tol):
    midy=0.5*(y0+y1)
    for (minx,miny,maxx,maxy) in rects:
        if miny-tol<midy<maxy+tol: return False
    return True

def _box_labels(minx,miny,w,h): return _text(minx+2, miny+7, f"W={w:.1f}mm  H={h:.1f}mm")
