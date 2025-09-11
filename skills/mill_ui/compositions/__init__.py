# path: skills/mill_ui/compositions/__init__.py
from .base import register_template, resolve_templates, REGISTRY

# Ensure template modules import to populate REGISTRY
# (safe if modules are absent; guarded import keeps core usable)
try:
    from .cabinets import shaker as _tmpl_shaker  # noqa: F401
except Exception:
    pass
try:
    from .panels import circle_mount as _tmpl_circle_mount  # noqa: F401
except Exception:
    pass
