

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass
class GoldenEntry:

    recipe_name: str
    source_file: str
    created_at: str = ""
    updated_at: str = ""
    metrics_file: str = "metrics.json"
    notes: str = ""

    def __post_init__(self) -> None:
        now = datetime.now(timezone.utc).isoformat()
        if not self.created_at:
            self.created_at = now
        if not self.updated_at:
            self.updated_at = now


@dataclass
class GoldenIndex:

    version: str = "1.0.0"
    created_at: str = ""
    updated_at: str = ""
    entries: dict[str, GoldenEntry] = field(default_factory=dict)

    def __post_init__(self) -> None:
        now = datetime.now(timezone.utc).isoformat()
        if not self.created_at:
            self.created_at = now
        if not self.updated_at:
            self.updated_at = now

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "entries": {
                name: asdict(entry) for name, entry in self.entries.items()
            },
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> GoldenIndex:
        index = cls(
            version=data.get("version", "1.0.0"),
            created_at=data.get("created_at", ""),
            updated_at=data.get("updated_at", ""),
        )
        for name, entry_data in data.get("entries", {}).items():
            index.entries[name] = GoldenEntry(**entry_data)
        return index


class GoldenStore:

    def __init__(self, base_path: str | Path) -> None:
        self.base_path = Path(base_path)
        self._index: GoldenIndex | None = None

    @property
    def index_path(self) -> Path:
        return self.base_path / "index.json"

    def exists(self) -> bool:
        return self.base_path.exists() and self.index_path.exists()

    def initialize(self) -> None:
        self.base_path.mkdir(parents=True, exist_ok=True)
        if not self.index_path.exists():
            self._index = GoldenIndex()
            self._save_index()

    def load_index(self) -> GoldenIndex:
        if self._index is not None:
            return self._index

        if not self.index_path.exists():
            self._index = GoldenIndex()
            return self._index

        with open(self.index_path) as f:
            data = json.load(f)
        self._index = GoldenIndex.from_dict(data)
        return self._index

    def _save_index(self) -> None:
        if self._index is None:
            return
        self._index.updated_at = datetime.now(timezone.utc).isoformat()
        with open(self.index_path, "w") as f:
            json.dump(self._index.to_dict(), f, indent=2)

    def list_entries(self) -> list[str]:
        index = self.load_index()
        return list(index.entries.keys())

    def has_entry(self, name: str) -> bool:
        index = self.load_index()
        return name in index.entries

    def get_entry_path(self, name: str) -> Path:
        return self.base_path / name

    def get_metrics_path(self, name: str) -> Path:
        index = self.load_index()
        entry = index.entries.get(name)
        if entry is None:
            return self.get_entry_path(name) / "metrics.json"
        return self.get_entry_path(name) / entry.metrics_file

    def load_metrics(self, name: str) -> dict[str, Any] | None:
        metrics_path = self.get_metrics_path(name)
        if not metrics_path.exists():
            return None
        with open(metrics_path) as f:
            return json.load(f)

    def save_metrics(
        self,
        name: str,
        metrics: dict[str, Any],
        source_file: str = "",
        notes: str = "",
    ) -> None:
        index = self.load_index()


        entry_dir = self.get_entry_path(name)
        entry_dir.mkdir(parents=True, exist_ok=True)


        metrics_path = entry_dir / "metrics.json"
        with open(metrics_path, "w") as f:
            json.dump(metrics, f, indent=2)


        now = datetime.now(timezone.utc).isoformat()
        if name in index.entries:
            index.entries[name].updated_at = now
            if source_file:
                index.entries[name].source_file = source_file
            if notes:
                index.entries[name].notes = notes
        else:
            index.entries[name] = GoldenEntry(
                recipe_name=name,
                source_file=source_file,
                notes=notes,
            )

        self._save_index()

    def delete_entry(self, name: str) -> bool:
        index = self.load_index()

        if name not in index.entries:
            return False


        entry_dir = self.get_entry_path(name)
        if entry_dir.exists():
            import shutil
            shutil.rmtree(entry_dir)


        del index.entries[name]
        self._save_index()
        return True

    def copy_source_file(self, name: str, source_path: str | Path) -> None:
        source_path = Path(source_path)
        if not source_path.exists():
            return

        entry_dir = self.get_entry_path(name)
        entry_dir.mkdir(parents=True, exist_ok=True)

        dest_path = entry_dir / "source.pml.yml"
        import shutil
        shutil.copy2(source_path, dest_path)


def get_default_golden_store() -> GoldenStore:

    current = Path.cwd()


    candidates = [
        current / "tests" / "golden",
        current.parent / "tests" / "golden",
        current.parent.parent / "tests" / "golden",
    ]

    for candidate in candidates:
        if candidate.parent.exists():
            return GoldenStore(candidate)


    return GoldenStore(current / "tests" / "golden")


def create_golden_from_recipe(
    store: GoldenStore,
    recipe_name: str,
    metrics: dict[str, Any],
    source_pml_path: str | Path | None = None,
) -> None:

    if "golden" not in metrics:
        metrics = {
            "golden": {
                "recipe_name": recipe_name,
                "created_at": datetime.now(timezone.utc).isoformat(),
            },
            **metrics,
        }

    store.save_metrics(
        name=recipe_name,
        metrics=metrics,
        source_file=str(source_pml_path) if source_pml_path else "",
    )

    if source_pml_path:
        store.copy_source_file(recipe_name, source_pml_path)
