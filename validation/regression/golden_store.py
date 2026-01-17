# validation/regression/golden_store.py - Golden metric management
#
# Manages storage and retrieval of golden baseline metrics.
# See docs/cam_validation_plan.md Section 6.1 for structure.

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass
class GoldenEntry:
    """Metadata for a single golden baseline entry."""

    recipe_name: str
    source_file: str  # e.g., "example.pml"
    created_at: str = ""
    updated_at: str = ""
    metrics_file: str = "metrics.json"  # relative to entry directory
    notes: str = ""

    def __post_init__(self) -> None:
        now = datetime.now(timezone.utc).isoformat()
        if not self.created_at:
            self.created_at = now
        if not self.updated_at:
            self.updated_at = now


@dataclass
class GoldenIndex:
    """Index of all golden baseline entries."""

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
        """Convert to JSON-serializable dict."""
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
        """Deserialize from dict."""
        index = cls(
            version=data.get("version", "1.0.0"),
            created_at=data.get("created_at", ""),
            updated_at=data.get("updated_at", ""),
        )
        for name, entry_data in data.get("entries", {}).items():
            index.entries[name] = GoldenEntry(**entry_data)
        return index


class GoldenStore:
    """
    Manages golden baseline metrics storage.

    Directory structure:
        tests/golden/
        ├── index.json              # Manifest of all golden files
        ├── 01_simple_profile/
        │   ├── metrics.json        # Full metric signature
        │   └── source.pml          # Input that generated it (optional copy)
        ├── 02_pocket_with_cleanup/
        │   ├── metrics.json
        │   └── source.pml
        └── ...
    """

    def __init__(self, base_path: str | Path) -> None:
        """Initialize store with base directory path."""
        self.base_path = Path(base_path)
        self._index: GoldenIndex | None = None

    @property
    def index_path(self) -> Path:
        """Path to the index file."""
        return self.base_path / "index.json"

    def exists(self) -> bool:
        """Check if the golden store exists."""
        return self.base_path.exists() and self.index_path.exists()

    def initialize(self) -> None:
        """Create the golden store directory and index."""
        self.base_path.mkdir(parents=True, exist_ok=True)
        if not self.index_path.exists():
            self._index = GoldenIndex()
            self._save_index()

    def load_index(self) -> GoldenIndex:
        """Load the index from disk."""
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
        """Save the index to disk."""
        if self._index is None:
            return
        self._index.updated_at = datetime.now(timezone.utc).isoformat()
        with open(self.index_path, "w") as f:
            json.dump(self._index.to_dict(), f, indent=2)

    def list_entries(self) -> list[str]:
        """List all golden entry names."""
        index = self.load_index()
        return list(index.entries.keys())

    def has_entry(self, name: str) -> bool:
        """Check if an entry exists."""
        index = self.load_index()
        return name in index.entries

    def get_entry_path(self, name: str) -> Path:
        """Get the directory path for an entry."""
        return self.base_path / name

    def get_metrics_path(self, name: str) -> Path:
        """Get the metrics file path for an entry."""
        index = self.load_index()
        entry = index.entries.get(name)
        if entry is None:
            return self.get_entry_path(name) / "metrics.json"
        return self.get_entry_path(name) / entry.metrics_file

    def load_metrics(self, name: str) -> dict[str, Any] | None:
        """Load golden metrics for an entry."""
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
        """
        Save golden metrics for an entry.

        Creates the entry directory and updates the index.
        """
        index = self.load_index()

        # Create or update entry
        entry_dir = self.get_entry_path(name)
        entry_dir.mkdir(parents=True, exist_ok=True)

        # Save metrics
        metrics_path = entry_dir / "metrics.json"
        with open(metrics_path, "w") as f:
            json.dump(metrics, f, indent=2)

        # Update index
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
        """Delete a golden entry and its files."""
        index = self.load_index()

        if name not in index.entries:
            return False

        # Delete directory
        entry_dir = self.get_entry_path(name)
        if entry_dir.exists():
            import shutil
            shutil.rmtree(entry_dir)

        # Update index
        del index.entries[name]
        self._save_index()
        return True

    def copy_source_file(self, name: str, source_path: str | Path) -> None:
        """Copy the source PML file to the entry directory."""
        source_path = Path(source_path)
        if not source_path.exists():
            return

        entry_dir = self.get_entry_path(name)
        entry_dir.mkdir(parents=True, exist_ok=True)

        dest_path = entry_dir / "source.pml"
        import shutil
        shutil.copy2(source_path, dest_path)


def get_default_golden_store() -> GoldenStore:
    """Get the default golden store (tests/golden/)."""
    # Find project root by looking for common markers
    current = Path.cwd()

    # Try to find tests/golden relative to working directory
    candidates = [
        current / "tests" / "golden",
        current.parent / "tests" / "golden",
        current.parent.parent / "tests" / "golden",
    ]

    for candidate in candidates:
        if candidate.parent.exists():  # tests/ exists
            return GoldenStore(candidate)

    # Default to working directory
    return GoldenStore(current / "tests" / "golden")


def create_golden_from_recipe(
    store: GoldenStore,
    recipe_name: str,
    metrics: dict[str, Any],
    source_pml_path: str | Path | None = None,
) -> None:
    """
    Create a golden baseline from a recipe's metrics.

    Args:
        store: The golden store to save to
        recipe_name: Name for the entry (e.g., "01_simple_profile")
        metrics: Combined metrics dict (svg, stl, gcode)
        source_pml_path: Optional path to source PML file to copy
    """
    # Add metadata wrapper if not present
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
