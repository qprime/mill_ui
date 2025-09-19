from pathlib import Path

from skills.living_truth_partner.config import Config
from skills.living_truth_partner.persona_builder import add_persona
from skills.living_truth_partner.project_store import ProjectStore


def test_persona_builder_appends(tmp_path: Path):
    root = tmp_path / "living_docs"
    config = Config(root=root, docs=root / "docs", artifacts=root / "artifacts", templates=root / "templates", whisper_url="", whisper_verify=None, prose_model="model", code_model="model")
    store = ProjectStore.create(config, "demo", "Demo", [], [])
    store.doc_path.write_text("# Demo\n\n## Market\nCurrent market notes\n", encoding="utf-8")
    ok = add_persona(store, {"name": "Alex", "role": "Ops", "goals": "Scale", "pains": "Bottlenecks"})
    assert ok is True
    content = store.doc_path.read_text(encoding="utf-8")
    assert "Alex" in content
    assert "Buyer Personas" in content
