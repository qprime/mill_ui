from pathlib import Path

from skills.living_truth_partner.config import Config
from skills.living_truth_partner.project_store import ProjectStore
from skills.living_truth_partner.search_index import SearchIndex


def test_search_index(tmp_path: Path, monkeypatch):
    root = tmp_path / "living_docs"
    config = Config(root=root, docs=root / "docs", artifacts=root / "artifacts", templates=root / "templates", whisper_url="", whisper_verify=None, prose_model="model", code_model="model")
    store = ProjectStore.create(config, "demo", "Demo Title", ["owner"], ["tag"])
    store.doc_path.write_text("# Demo Title\n\n## Focus\nBody text about clamps and fixtures.\n", encoding="utf-8")
    index = SearchIndex.build(config)
    hits = index.search("fixtures")
    assert hits
    assert hits[0].doc == "demo"
