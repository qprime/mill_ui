from __future__ import annotations

import json

import pytest

from cli.introspect import dump_removal_intent

pytestmark = pytest.mark.usefixtures("machining_config")


@pytest.mark.parametrize("role,depth", [("profile", "through"), ("pocket", "6mm"), ("hole", "12mm")])
def test_introspection_derives_intents_from_authored_source(tmp_path, role, depth):
    source = tmp_path / "part.pml.yml"
    source.write_text(f"""Sheet: {{width: 200mm, height: 200mm, thickness: 19mm}}
children:
- Circle:
    id: part
    diameter: 40mm
    at: {{x: 100mm, y: 100mm}}
    feature: {{type: {role}, depth: {depth}}}
""")
    (intents,) = json.loads(dump_removal_intent(str(source)))
    assert len(intents) == 1
    assert intents[0]["hint_type"] == role
    assert intents[0]["depth_mm"] == (19 if depth == "through" else int(depth[:-2]))
