Got it 👍 — thanks for catching that.
Here’s a **full rewritten spec from the ground up**, with *all* the changes merged in (hinge cups on backside, multi-pass, multi-tool strategy, corner anchors, split G-code files). No “same as previous” shortcuts — this is standalone and copy-ready.

---

# Spec: Parametric Cabinet Door CAM Generator (Python, Linux)

Goal:
Generate **deterministic, production-ready G-code** for MDF cabinet doors from simple parameters — no STL modeling. The pipeline supports **multi-pass machining**, **multi-tool strategies** (½″ rougher, ¼″ finisher, boring bit for hinges), and optional **corner anchor pockets** for magnets/washers. Output is split into **separate G-code files per tool/job** for clarity and reliability in gSender.

---

## 0) Scope (v1)

* Styles: start with **faux-Shaker recessed panel**.
* Supported tools: ½″ flat, ¼″ flat, optional 35 mm boring bit.
* Supported ops: pocket border, panel raster, corner anchors, profile cut, backside hinge cups.
* Outputs: 2–3 G-code files per door.
* Excludes: CAD model generation, GUI, single-file tool changes (M6).

---

## 1) Inputs and Outputs

### Inputs

* **Style template (JSON)** — rules for geometry, ratios, and op defaults.
* **Order (JSON/CLI)** — specific door dimensions + options (hinges, anchors).
* **Packs (JSON)** — material, tool, and machine definitions, versioned separately.

### Outputs

* **front\_rough.gcode** — hog out panel + border with ½″ tool.
* **front\_finish.gcode** — finish panel + border, cut anchors, cut outside profile with ¼″ tool.
* **back\_hinges.gcode** — (if enabled) cut hinge cups on backside with 35 mm boring bit.
* **merged.json** — frozen config with resolved values + derived fields.
* **summary.txt** — human-readable run sheet.

Each run is hashed for traceability:

```
out/{style_id}.v{style_version}/W{width}_H{height}_T{thickness}/hash_{hash}/
```

---

## 2) Config Structures

### Style Template

* **Border rules**: target ratio of min(W,H), with min/max clamps and clearance.
* **Panel depth rules**: target % of thickness, clamped, with floor safety.
* **Corner anchors**: enabled by default; face (front/back), placement mode (xy/diagonal), inset values, diameter, depth, clearance.
* **Hinge bores**: diameter, depth, offsets from top/bottom, side, spacing check.
* **Multi-tool stages**: roughing (½″), finishing (¼″), profiling (¼″), hinges (35 mm).
* **Defaults**: tabs (count, size), onion skin, tool strategy.
* **Constraints**: e.g. min feature ≥ 2×tool diameter.

### Order

* `width_mm`, `height_mm`, `thickness_mm`
* Optional `panel_depth_mm` override
* `hinge_bores` true/false, hinge side (left/right), hinge offsets
* `corner_anchors` block with overrides (enabled, placement, diameter, depth, inset)
* `tool_strategy` = single | multi
* `use_back_hinge_job` true/false

### Packs

* **Material pack**: feeds, stepdown, stepover, finish feeds.
* **Tool packs**: each tool’s diameter, rpm, feeds, ramping, stepdown.
* **Machine pack**: work origin, safe-Z, max feeds, post dialect, flip strategy, tool change mode.

---

## 3) Geometry Computations

* **Border width** = clamp(round(ratio × min(W,H)), min, max); must be ≥ (2×tool\_diam + clearance).
* **Panel depth** = clamp(thickness × ratio, min, max); must be ≤ (thickness – safety\_floor).
* **Inner panel rect** = \[border, width–border] × \[border, height–border].
* **Corner anchors**:

  * XY mode → inset `dx,dy` from each corner.
  * Diagonal mode → inset along 45° diagonal by given distance.
  * Must fit fully inside inner panel rect – clearance.
* **Hinge cups**:

  * XY = border + (diameter/2 + clearance), Y = offsets from top/bottom.
  * Face = backside.
  * Flip strategy = flip about Y with left fence fixed (XY unchanged).

---

## 4) Toolpath Planning

### Front Rough (½″ flat)

* Pocket border → rough, leave stock\_to\_leave (e.g. 0.6 mm).
* Raster panel → rough, stepdown passes ≤ material.max\_stepdown.
* Onion skin left untouched.

### Front Finish (¼″ flat)

* Pocket border → cleanup to full depth.
* Raster panel → cleanup to full depth.
* Corner anchors → circular pockets, stepdown ≤ tool.max\_stepdown.
* Profile cut → multi-pass contour: leave onion skin, add tabs, finish full-depth contour.

### Back Hinges (35 mm boring)

* Circular pockets to depth, stepdown loop.
* Separate job file; Z re-zero on backside.
* XY unchanged if flipped about Y-axis with left fence fixed.

---

## 5) Multi-Pass Behavior

* **All deep ops** use Z stepdown increments ≤ `material.depths.max_stepdown_mm`.
* **Rough passes** stop short of target depth by `stock_to_leave_mm`.
* **Finish passes** cut to final depth + dimension.
* **Profile cut**: rough pass optional with ½″, final cut with ¼″.
* **Onion skin**: leave \~0.6 mm, then final pass removes it.
* **Tabs**: inserted evenly, sized per style/order.

---

## 6) Validation Rules

* Borders ≥ (2×tool\_diameter + clearance).
* Panel depth ≤ thickness – safety floor.
* Anchors fully inside inner panel area.
* Hinge cups inside door area, ≥ min spacing.
* Stepdown, stepover, feeds within pack limits.
* If multi-tool: rough tool ≥ finish tool in diameter.
* Abort if any violation; log errors in `.errors.txt`.

---

## 7) File Outputs

Example door: 600 × 800 × 19 mm, hash 9f2a4d1c

```
out/mdf_faux_shaker_recessed.v1/W600_H800_T19/hash_9f2a4d1c/
  front_rough.gcode
  front_finish.gcode
  back_hinges.gcode       # only if hinge_bores=true
  merged.json
  summary.txt
```

---

## 8) Summary Example (summary.txt)

```
Style: mdf_faux_shaker_recessed v1
Door: 600 × 800 × 19 mm
Border: 60.0 mm
Panel depth: 11.5 mm

Tools:
- Rough: ½″ flat (12.7 mm) | stock leave 0.6 | stepover 45% | stepdown 3.0 mm
- Finish: ¼″ flat (6.35 mm) | to final | stepover 45% | stepdown 2.5 mm
- Profile: ¼″ flat | onion skin 0.6 mm, tabs 6×(10×2 mm)
- Hinges: 35 mm boring bit | backside | depth 13 mm @ offsets [100, 700]

Anchors: 4 × Ø12 × 2 mm (front) | inset 18×18 mm | xy mode
Flip strategy: flip_about_Y_keep_left_fence
Hash: 9f2a4d1c
```

---

## 9) Roadmap

* **v1.0**: Shaker recessed, multi-tool split files, optional hinge bores (¼″ fallback).
* **v1.1**: dedicated boring bit support, raised panel style.
* **v1.2**: registration pin ops.
* **v1.3**: 2D previews (SVG/PNG).
* **v2.0**: optional FreeCAD/STEP previews for marketing.

---

✅ This is the complete, standalone spec.
The JSON examples you already have slot straight into this.

Do you want me to also generate a **formal JSON Schema (Draft-07)** for the `order` and `style` files so they’re machine-validated, or is the concrete example set enough for your first cut?
