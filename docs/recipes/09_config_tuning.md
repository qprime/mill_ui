# Recipe 09: Config Tuning (Feeds/Finish/Safe Z)

**Goal:** Tune planner behavior by adjusting `cam.config.Config` fields (or overriding them via environment variables).

**Difficulty:** Intermediate  
**Time:** 10 minutes  
**Prerequisites:** Recipe 02 (pocket finish pass context)

---

## The Config Object

`cam.config.Config` controls planner-level behavior such as:
- `safe_z_mm`: clearance height for rapid moves
- `merge_epsilon_mm`: seam merge tolerance for profiles
- `cleanup_offset_mm`: pocket wall cleanup offset
- `pocket_finish_perimeter`: enable/disable pocket perimeter finish pass

---

## Example: Disable Pocket Finish Perimeter

```python
from cam.config import Config

config = Config(pocket_finish_perimeter=False)
```

In a full pipeline:

```python
from cam.config import Config
from cam.planner.passes import plan_passes
from cam.post.gcode import write_gcode

passes, _summary = plan_passes(
    hints,
    config=Config(pocket_finish_perimeter=False),
    tool_db=tool_db,
    material=material,
    machine=machine,
    stock=stock,
)

gcode = "\n".join(write_gcode(p["moves"], safe_z=6.0) for p in passes if p.get("moves"))
```

---

## Example: Raise Safe Z for Tall Workholding

```python
from cam.config import Config

config = Config(safe_z_mm=12.0)
```

---

## Environment Variable Overrides

You can overlay config from environment variables:

```bash
export CAM_SAFE_Z=12.0
export CAM_POCKET_FINISH_PERIMETER=false
```

Then, in Python:

```python
from cam.config import Config

config = Config.from_env()
```

Recognized variables use the `CAM_` prefix (see `cam/config.py`), including:
- `CAM_SAFE_Z`
- `CAM_MERGE_EPS`
- `CAM_CLEANUP_OFFSET_MM`
- `CAM_POCKET_FINISH_PERIMETER`

---

## Notes

- Config tuning changes *how* toolpaths are generated, not *what* geometry is machined; keep it in the planner layer.
- If you want “rough vs finish” as a semantic design intent, use edge intent annotations (Recipe 12).
