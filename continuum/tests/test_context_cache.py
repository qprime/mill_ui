import tempfile
from pathlib import Path

from continuum.context_cache import ContextBudget, build_all_caches, load_cache, select_context


def _write(folder: Path, relative: str, content: str) -> None:
    path = folder / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_build_all_caches_and_select_context(monkeypatch):
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        cache_dir = root / "cache"

        monkeypatch.setenv("ACE_CACHE_DIR", str(cache_dir))

        _write(root, "pkg/__init__.py", "")
        _write(
            root,
            "pkg/module.py",
            """import math\n\n\nclass Thing:\n    pass\n\n\ndef helper():\n    return math.sqrt(4)\n""",
        )
        _write(root, "docs/README.md", "Project docs")
        _write(
            root,
            "tests/test_module.py",
            """import pkg.module\n\n\ndef test_helper():\n    assert pkg.module.helper() == 2\n""",
        )

        written = build_all_caches(root)
        for name in ("file_tree", "deps_graph", "symbol_table", "doc_map", "test_map"):
            assert name in written
            assert written[name].exists()

        file_tree = load_cache("file_tree")
        paths = {entry["path"] for entry in file_tree if entry.get("type") == "file"}
        assert "pkg/module.py" in paths

        budget = ContextBudget(
            focus_history=5,
            direct_files_max=5,
            neighbors_depth=2,
            neighbors_per_file=2,
            neighbor_signature_budget=200,
            docs_tests_budget=5,
        )
        manifest = select_context(
            root,
            focus_files=["pkg/module.py"],
            change_set=[],
            explicit_files=[],
            budget=budget,
        )

        assert "pkg/module.py" in manifest["direct_files"]
        docs = manifest["docs"].get("pkg/module.py")
        if docs is not None:
            assert "docs/README.md" in docs
        tests = manifest["tests"].get("pkg/module.py")
        if tests is not None:
            assert "tests/test_module.py" in tests
