from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MACHINES_PATH = PROJECT_ROOT / "ace_control" / "machines.json"


@dataclass
class MachineProfile:
    name: str
    type: str = "local"
    host: Optional[str] = None
    workspace: str = "."
    codex_cmd: str = "codex run --mode=pro --stdin"
    notes: Optional[str] = None

    def to_dict(self) -> Dict[str, object]:
        payload = {
            "name": self.name,
            "type": self.type,
            "workspace": self.workspace,
            "codex_cmd": self.codex_cmd,
        }
        if self.host:
            payload["host"] = self.host
        if self.notes:
            payload["notes"] = self.notes
        return payload

    @staticmethod
    def from_dict(data: Dict[str, object]) -> "MachineProfile":
        return MachineProfile(
            name=str(data.get("name")),
            type=str(data.get("type", "local")),
            host=data.get("host") if data.get("host") else None,
            workspace=str(data.get("workspace", ".")),
            codex_cmd=str(data.get("codex_cmd", "codex run --mode=pro --stdin")),
            notes=data.get("notes") if data.get("notes") else None,
        )


_DEFAULT_MACHINES = [
    MachineProfile(
        name="skylink",
        type="local",
        workspace="/home/steve/workspaces/cliff_ai",
        codex_cmd="codex run --mode=pro --stdin",
        notes="primary build box",
    )
]


class MachineRegistry:
    def __init__(self, path: Path | None = None):
        self.path = path or DEFAULT_MACHINES_PATH
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self._write(_DEFAULT_MACHINES)
        self._machines = {m.name: m for m in self._read()}

    def _read(self) -> List[MachineProfile]:
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            raw = []
        machines: List[MachineProfile] = []
        for entry in raw:
            try:
                machines.append(MachineProfile.from_dict(entry))
            except Exception:
                continue
        if not machines:
            machines = list(_DEFAULT_MACHINES)
        return machines

    def _write(self, machines: Iterable[MachineProfile]) -> None:
        data = [m.to_dict() for m in machines]
        self.path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def all(self) -> List[MachineProfile]:
        return sorted(self._machines.values(), key=lambda m: m.name)

    def get(self, name: str) -> MachineProfile:
        if name not in self._machines:
            raise KeyError(name)
        return self._machines[name]

    def upsert(self, profile: MachineProfile) -> MachineProfile:
        self._machines[profile.name] = profile
        self._write(self._machines.values())
        return profile

    def replace_all(self, machines: Iterable[MachineProfile]) -> None:
        self._machines = {m.name: m for m in machines}
        if not self._machines:
            self._machines = {m.name: m for m in _DEFAULT_MACHINES}
        self._write(self._machines.values())

    def patch(self, name: str, patch: Dict[str, object]) -> MachineProfile:
        current = self.get(name)
        merged = current.to_dict()
        merged.update(patch)
        updated = MachineProfile.from_dict(merged)
        return self.upsert(updated)

    def delete(self, name: str) -> None:
        if name in self._machines:
            del self._machines[name]
            if not self._machines:
                self._machines = {m.name: m for m in _DEFAULT_MACHINES}
            self._write(self._machines.values())

    def to_dict(self) -> Dict[str, Dict[str, object]]:
        return {name: profile.to_dict() for name, profile in self._machines.items()}


__all__ = ["MachineProfile", "MachineRegistry", "DEFAULT_MACHINES_PATH"]
