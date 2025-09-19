# name: registry.py
# path: services/registry.py
# role: Load service registry definitions for system control commands
# deps: json, pathlib, dataclasses, typing
# inputs: services/service_registry.json
# outputs: Registry dataclasses

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List

PROJECT_ROOT = Path(__file__).resolve().parents[1]
REGISTRY_PATH = PROJECT_ROOT / "services/service_registry.json"


@dataclass(frozen=True)
class Service:
    id: str
    description: str
    unit: str
    unit_file: Path | None
    scope: str


class ServiceRegistry:
    def __init__(self, services: Iterable[Service]):
        self._services: Dict[str, Service] = {svc.id: svc for svc in services}

    def all(self) -> List[Service]:
        return sorted(self._services.values(), key=lambda svc: svc.id)

    def get(self, service_id: str) -> Service:
        if service_id not in self._services:
            raise KeyError(service_id)
        return self._services[service_id]


def load(path: Path | None = None) -> ServiceRegistry:
    cfg_path = path or REGISTRY_PATH
    if not cfg_path.exists():
        raise FileNotFoundError(cfg_path)
    data = json.loads(cfg_path.read_text(encoding="utf-8"))
    entries = data.get("services", [])
    services: List[Service] = []
    for entry in entries:
        unit_file = entry.get("unit_file")
        resolved = None
        if unit_file:
            resolved = (PROJECT_ROOT / unit_file).resolve()
        services.append(
            Service(
                id=entry["id"],
                description=entry.get("description", ""),
                unit=entry["unit"],
                unit_file=resolved,
                scope=entry.get("scope", "user"),
            )
        )
    return ServiceRegistry(services)
