
mill_ui — clean CAD/CAM library nucleus.
Run tests: python -m skills.mill_ui.tests.run_all

## Native CAM backend
- The CAM planners now ship with a C++17 backend (`skills.mill_ui.cam.native`).
- The public Python APIs are unchanged but heavy planning/post steps execute in C++.
- The extension is required for CAM operations; build failures now surface immediately instead of silently falling back.
- See `skills/mill_ui/cam/native/README.md` for build instructions and native-specific notes.

## Native CAD exporter
- STEP/STL previews now route through `skills.mill_ui.cad.native` (C++17/pybind11).
- The Python helpers in `skills.mill_ui.cad.step_export` shim into the native module; CadQuery is no longer required.
- See `skills/mill_ui/cad/native/README.md` for the current capabilities and roadmap toward an OCCT-backed modeller.

Border template quick-start:
- Add `{ "kind": "template", "type": "Border", "params": {...} }` to a layout `items[]`.
- Required params: `outer_w_mm`, `outer_h_mm`, `inset_mm`, `band_mm`, `mode`.
- Set `track_depth_mm` (engrave depth) and optional `placement.center_xy_mm` to locate it.
- `mode:"vine"` accepts `amp_mm`, `wavelength_mm`, `step_mm`, `seed` for deterministic waves.
- Vine track width: `track_width_mm` (defaults to 3.0 mm, clamped safe for inset).
- Vine leaves: set `leaf_every_mm`, `leaf_offset_mm`, `leaf_base_d_mm`, `leaf_count`, `leaf_spacing_mm`.
- Optional leaf refinements: `leaf_taper_p`, `leaf_depth_mm`, `leaf_vein_depth_mm`, `leaf_vein_width_mm`, `alternate_side`.
- `mode:"dot"` needs `dot_d_mm` and `dot_pitch_mm` for circular pockets along the track.
- `mode:"dash"` needs `dash_len_mm`, `dash_gap_mm`, `dash_width_mm` for rectangular pockets.
- Use `band_mm` to keep clearance from the sheet edge; `inset_mm` must exceed it.
- All depths are clamped to the sheet thickness passed into the template.
- Works with existing CAM: vine emits Polyline engraves, leaves/dots/dashes emit pocket cuts.
