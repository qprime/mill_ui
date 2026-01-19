# Technical Debt: CLI and Workflow Gaps

Identified during wall_mount_planter project build (2026-01-19). Issues that caused unnecessary friction when using the system via AI chat interface.

**Priority Order:**
1. ~~TD-1: Quick CLI Reference (documentation)~~ ✅ Completed 2026-01-19
2. ~~TD-2: CLI .nest ingestion (feature)~~ ✅ Completed 2026-01-19
3. ~~TD-3: SVG part labels (feature)~~ ✅ Completed 2026-01-19
4. ~~TD-4: Test CLI consistency (cleanup)~~ ✅ Completed 2026-01-19

---

## TD-1: Quick CLI Reference in CLAUDE.md ✅

**Status:** Completed 2026-01-19

**Problem:** AI had to explore the codebase to discover how to run exports. No quick reference exists.

**Solution:** Add a "Quick Commands" section to CLAUDE.md with the most common CLI invocations.

**Proposed Addition:**

```markdown
## Quick Commands

Common CLI operations (all from mill_ui root):

```bash
# Parse and validate PML
python -m cli.convert_layout --from pml --to json input.pml output.json

# Export STL (3D model)
python -m cli.export_cad --input layout.pml --out output/ --kerf 6.35 --quality high

# Export SVG blueprint
python -m cli.export_blueprint --input layout.pml --out output/ --theme dark

# Validate CAM outputs
python -m cli.validate_cam --recipe docs/recipes/01_simple_profile --summary

# Run nesting (currently in tools/, see TD-2)
python tools/nest.py job.nest -o output/ -v
```

For compositional PML (frame/inset/grid syntax), add `--compositional` flag.
```

**Implementation:**
- Edit `CLAUDE.md`
- Add section after "Project Directory"

**Effort:** 5 minutes

---

## TD-2: CLI Should Ingest .nest Files ✅

**Status:** Completed 2026-01-19 — Created `cli/nest.py` with `--export-stl` and `--export-svg` flags.

**Problem:** `.nest` files require `tools/nest.py`, which is not in `cli/`. The CLI modules only accept `.pml` and `.json`. This creates confusion and inconsistency.

**Current State:**
- `tools/nest.py` — Standalone script, outputs PML files
- `cli/export_cad.py` — Only accepts `.pml` or `.json`
- `cli/export_blueprint.py` — Only accepts `.pml` or `.json`

**Solution Options:**

### Option A: Move nest.py to cli/ (Recommended)

Move `tools/nest.py` → `cli/nest.py` and add export flags:

```bash
# Basic nesting (outputs PML)
python -m cli.nest job.nest -o output/

# Nesting with automatic exports
python -m cli.nest job.nest -o output/ --export-stl --export-svg
```

**Implementation:**
1. Move `tools/nest.py` → `cli/nest.py`
2. Add `--export-stl` and `--export-svg` flags
3. Chain to `export_cad` and `export_blueprint` internally
4. Update any tests that import from `tools.nest`

### Option B: Add .nest support to export CLIs

Extend `export_cad.py` and `export_blueprint.py` to accept `.nest`:

```bash
python -m cli.export_cad --input job.nest --out output/
```

**Implementation:**
1. Add `.nest` extension detection in both CLI modules
2. Call nesting internally, then export each sheet
3. More complex: need to handle multi-sheet output naming

### Recommendation

Option A is cleaner. The nesting step is logically separate (placement) from export (rendering). Chaining via flags keeps it modular.

**Effort:** 1-2 hours

---

## TD-3: SVG Blueprint Missing Part Labels ✅

**Status:** Completed 2026-01-19 — Added `_render_label()`, `label_text` theme color, and part inventory in notes.

**Problem:** The SVG output shows shapes but doesn't label them. The `shape_id` field exists in LayoutAST but isn't rendered. For the planter project, the SVG showed shapes but no way to identify "rounded_panel_0" vs "triangle_2".

**Current State:**
- `Item.shape_id` exists and is populated
- `export/blueprint_svg.py` renders shapes but ignores `shape_id`
- Notes section shows counts ("7 profiles, 9 engraves") but no part inventory

**Solution:**

Add part label rendering to `_render_profile()`, `_render_pocket()`, etc.:

```python
def _render_profile(group: ET.Element, item: Item, offset_x: float, offset_y: float, theme: Theme) -> None:
    # ... existing shape rendering ...

    # Add label if shape_id exists
    if item.shape_id:
        cx, cy = item.placement.center_xy_mm
        label = ET.SubElement(
            group,
            "text",
            {
                "x": str(offset_x + cx),
                "y": str(offset_y + cy),
                "class": "part-label",
                "text-anchor": "middle",
                "dominant-baseline": "middle",
            },
        )
        label.text = item.shape_id
```

**Additional Enhancements:**
1. Add `.part-label` style to stylesheet
2. Add part inventory to notes section
3. Optional: Add `--no-labels` flag to suppress for clean exports

**Implementation:**
- Modify `export/blueprint_svg.py`
- Add tests for label rendering

**Effort:** 1-2 hours

---

## TD-4: Test System Should Use CLI Modules ✅

**Status:** Completed 2026-01-19 — Created `tests/test_cli_integration.py` with 6 CLI tests.

**Problem:** Some tests may bypass CLI and call internal APIs directly. Tests should exercise the same code paths users do.

**Audit Status:** ✅ **Completed 2026-01-19**

**Audit Results:**

| File | API Type | Verdict |
|------|----------|---------|
| `tests/run_edge_tests.py` | Internal | ✅ Appropriate (unit tests for IR semantics) |
| `tests/run_gcode_equivalence_tests.py` | Internal | ✅ Appropriate (adapter equivalence tests) |
| `docs/recipes/15_profile_with_tabs/example.py` | Internal | ✅ Appropriate (feature demonstration) |
| `docs/recipes/17_nesting_guillotine/example.py` | Internal | ✅ Appropriate (pipeline demonstration) |
| `docs/recipes/18_nesting_maxrects/example.py` | Internal | ✅ Appropriate (pipeline demonstration) |
| `docs/recipes/20_multi_panel_doors/example.py` | Internal | ✅ Appropriate (domain/generator demo) |
| Imports from `tools/` | N/A | ✅ None found |

**Conclusion:** Existing tests are **appropriate for their purpose**:
- Unit tests should use internal APIs to test specific layers
- Equivalence tests verify internal pipeline consistency
- Recipe examples demonstrate API usage patterns

**What's Missing:** No **CLI integration tests** exist. The system lacks tests that exercise CLI entry points the way users do.

**Recommendation:** Add a new `tests/test_cli_integration.py` that:
1. Runs CLI commands via `subprocess`
2. Validates output file existence and basic structure
3. Catches regressions in CLI argument parsing and file handling

**Example CLI Integration Test:**

```python
import subprocess
import sys
import tempfile
from pathlib import Path

def test_export_cad_from_pml():
    """Test CLI export_cad produces expected outputs."""
    recipe_dir = Path("docs/recipes/01_simple_profile")
    pml_file = recipe_dir / "layout.pml"

    with tempfile.TemporaryDirectory() as tmpdir:
        result = subprocess.run(
            [sys.executable, "-m", "cli.export_cad",
             "--input", str(pml_file),
             "--out", tmpdir,
             "--kerf", "6.35",
             "--quality", "high"],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0, f"CLI failed: {result.stderr}"

        output_path = Path(tmpdir)
        stl_files = list(output_path.glob("*.stl"))
        assert len(stl_files) > 0, "No STL files generated"

def test_export_blueprint_from_pml():
    """Test CLI export_blueprint produces SVG."""
    recipe_dir = Path("docs/recipes/01_simple_profile")
    pml_file = recipe_dir / "layout.pml"

    with tempfile.TemporaryDirectory() as tmpdir:
        result = subprocess.run(
            [sys.executable, "-m", "cli.export_blueprint",
             "--input", str(pml_file),
             "--out", tmpdir,
             "--theme", "dark"],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0, f"CLI failed: {result.stderr}"

        svg_files = list(Path(tmpdir).glob("*.svg"))
        assert len(svg_files) > 0, "No SVG files generated"

def test_convert_layout_pml_to_json():
    """Test CLI convert_layout round-trips correctly."""
    recipe_dir = Path("docs/recipes/01_simple_profile")
    pml_file = recipe_dir / "layout.pml"

    with tempfile.TemporaryDirectory() as tmpdir:
        json_file = Path(tmpdir) / "output.json"

        result = subprocess.run(
            [sys.executable, "-m", "cli.convert_layout",
             "--from", "pml",
             "--to", "json",
             str(pml_file),
             str(json_file)],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0, f"CLI failed: {result.stderr}"
        assert json_file.exists(), "JSON file not created"

        import json
        with open(json_file) as f:
            data = json.load(f)
        assert "sheet" in data, "JSON missing sheet key"
        assert "items" in data, "JSON missing items key"
```

**Effort:** 1-2 hours (create new test file with 3-5 CLI tests)

**Priority:** Low — existing coverage is good, CLI integration tests are a quality improvement

---

## TD-5: PML Lacks Custom Shape Primitives

**Problem:** PML supports `rect` and `circle` but not `rounded_rect`, `polygon`, or `equilateral_triangle`. The planter project needed a build script to generate these shapes.

**Current State:**
- `.nest` files define rectangular bounding boxes only
- `tools/nest.py` outputs PML with `rect` at computed positions
- Custom shapes require Python code

**Solution Options:**

### Option A: Extend PML Shape Syntax

Add shape primitives to PML:

```pml
# Rounded rectangle
rounded_rect door 400mm 600mm corner_radius 25mm center 200mm 300mm
    profile outside through

# Polygon (inline points)
polygon triangle points (0,0) (73,126.6) (146,0) center 500mm 500mm
    profile outside through

# Equilateral triangle (computed from side length)
equilateral_triangle bracket 146mm center 500mm 500mm
    profile outside through
```

### Option B: Document Build Script Pattern

Keep PML simple. Document that custom shapes require a build script that:
1. Parses `.nest` for placements
2. Substitutes actual shapes at those positions
3. Outputs JSON for CLI consumption

### Recommendation

Option B for now. Custom shapes are project-specific. A generic `polygon` primitive would help, but `equilateral_triangle` is too specialized. The build script pattern is documented in the planter project.

**Effort:** Option A: 4-8 hours. Option B: 30 minutes (documentation only).

---

## Implementation Order

1. **TD-1** — Quick win, immediate AI usability improvement
2. **TD-3** — High value for visual validation
3. **TD-2** — Consolidates CLI, reduces confusion
4. **TD-4** — Quality improvement, catches integration bugs
5. **TD-5** — Low priority, build script pattern works

---

## How to Implement

Use this prompt in a new Claude Code session:

```
Read CLAUDE.md, then read docs/dev_docs/2026-01-19_technical_debt.md and implement TD-N.
```

Each item has:
- Problem description
- Solution approach
- Implementation guidance
- Effort estimate

---

## Related Documents

- [CLAUDE.md](../../CLAUDE.md) — Development guide (will be updated by TD-1)
- [domain_generator_enhancements.md](domain_generator_enhancements.md) — Future generator work
- [README.md](../../README.md) — Architecture overview
