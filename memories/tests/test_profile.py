from __future__ import annotations

from pathlib import Path

from memories.framework import profile


def _reset(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.delenv("CLIFF_MEMORIES_PROFILE", raising=False)
    monkeypatch.delenv("CLIFF_MEMORIES_ROOT", raising=False)
    monkeypatch.setattr(profile, "STATE_DIR", tmp_path / "state", raising=False)
    monkeypatch.setattr(profile, "PROFILE_STATE_PATH", tmp_path / "state" / "memory_profile.json", raising=False)
    monkeypatch.setattr(profile, "PROFILES_ROOT", tmp_path / "profiles", raising=False)
    profile.clear_cache()
    profile.clear_root_override()


def test_set_active_profile_creates_seed_dirs(tmp_path, monkeypatch):
    _reset(monkeypatch, tmp_path)
    target = profile.set_active_profile("test", persist=True)
    assert target.exists()
    status = profile.profile_status()
    assert status["profile"] == "test"
    assert status["persisted"] is True
    assert Path(status["root"]) == target
    # baseline directories are created on demand
    for required in ("policies", "truth"):
        assert (target / required).exists()


def test_root_override_wins(tmp_path, monkeypatch):
    _reset(monkeypatch, tmp_path)
    override = tmp_path / "override"
    profile.set_root_override(override)
    assert profile.active_memories_root() == override
    profile.clear_root_override()
    assert profile.active_memories_root() == Path(profile.PROJECT_ROOT) / "memories"
