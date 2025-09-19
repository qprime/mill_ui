from __future__ import annotations

import json
from pathlib import Path
from random import Random
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from skills.memory_framework.executors import codex_cli, ops_shell, prose_llm
from skills.memory_framework.models import Action
from skills.memory_framework.registry import MemoryRegistry
from skills.memory_framework.utils import MEMORIES_ROOT, sha256_text


def find_manifests() -> list[Path]:
    return sorted(MEMORIES_ROOT.glob("actions/*/**/manifest.json"))


def _load_action(registry: MemoryRegistry, action_id: str) -> Action:
    memory = registry.latest(action_id)
    if not memory:
        raise RuntimeError(f"Missing action {action_id} in registry")
    return Action.from_memory(memory)


def _expected_artifacts(executor: str, action: Action):
    if executor == "prose_llm":
        return prose_llm.simulate_artifacts(action)
    if executor == "codex_cli":
        return codex_cli.simulate_artifacts(action)
    if executor == "ops_shell":
        artifacts, _summary = ops_shell.simulate_artifacts(action)
        return artifacts
    raise RuntimeError(f"Executor {executor} is not supported for dry replay")


def verify_manifest(manifest_path: Path, registry: MemoryRegistry) -> bool:
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    executor = data.get("executor")
    if not executor:
        print(f"{manifest_path}: missing executor field; skipping")
        return True

    action = _load_action(registry, data["action_id"])
    expected = _expected_artifacts(executor, action)
    recorded = {item["path"]: item["sha256"] for item in data.get("artifact_hashes", [])}

    if set(expected) != set(recorded):
        print(f"{manifest_path}: artifact set mismatch")
        return False

    for rel_path, text in expected.items():
        expected_hash = sha256_text(text)
        if expected_hash != recorded[rel_path]:
            print(f"{manifest_path}: dry run hash mismatch for {rel_path}")
            return False
        artifact_path = MEMORIES_ROOT / Path(rel_path)
        if not artifact_path.exists():
            print(f"{manifest_path}: artifact {rel_path} missing on disk")
            return False
        actual_text = artifact_path.read_text(encoding="utf-8")
        actual_hash = sha256_text(actual_text)
        if actual_hash != recorded[rel_path]:
            print(f"{manifest_path}: disk hash mismatch for {rel_path}")
            return False
    return True


def main() -> int:
    manifests = find_manifests()
    if not manifests:
        print("no manifests found; skipping")
        return 0
    rng = Random(42)
    candidates: list[Path] = []
    for manifest in manifests:
        try:
            data = json.loads(manifest.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        if data.get("executor"):
            candidates.append(manifest)
    sample_pool = candidates or manifests
    sample = rng.choice(sample_pool)
    registry = MemoryRegistry()
    if verify_manifest(sample, registry):
        print(f"reproduce ok for {sample}")
        return 0
    print(f"failed to reproduce manifest {sample}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
