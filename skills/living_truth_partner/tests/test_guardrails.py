from pathlib import Path

from skills.living_truth_partner.config import Config
from skills.living_truth_partner.guardrails import analyze
from skills.living_truth_partner.project_store import ProjectStore


def test_guardrails_detects_length(tmp_path: Path):
    root = tmp_path / "living_docs"
    config = Config(root=root, docs=root / "docs", artifacts=root / "artifacts", templates=root / "templates", whisper_url="", whisper_verify=None, prose_model="model", code_model="model")
    store = ProjectStore.create(config, "demo", "Demo", [], [])
    store.doc_path.write_text("# Demo\n\n## Long\n" + ("word " * 400), encoding="utf-8")
    insights = analyze(store)
    long_section = next((i for i in insights if i.title == "Long"), None)
    assert long_section is not None
    assert any("trim" in issue["message"].lower() for issue in long_section.issues)
