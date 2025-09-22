# name: project_store.py
# path: skills/living_truth_partner/project_store.py
# role: Manage Living Truth Partner document storage
# deps: json, datetime, pathlib, dataclasses, typing
# inputs: Config, slug, metadata
# outputs: ProjectStore dataclass

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable, List, Optional

from skills.living_truth_partner.config import Config

__all__ = ["ProjectInfo", "ProjectStore"]

_IDENTIFIER_RE = re.compile(r"[^a-z0-9-_]+")


def _timestamp() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat().replace(":", "-")


def _infer_title(doc_path: Path, summary_path: Path) -> str:
    if summary_path.exists():
        try:
            data = json.loads(summary_path.read_text(encoding="utf-8"))
            title = data.get("title")
            if isinstance(title, str) and title.strip():
                return title.strip()
        except json.JSONDecodeError:
            pass
    if doc_path.exists():
        for line in doc_path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if stripped.startswith("#"):
                value = stripped.lstrip("#").strip()
                if value:
                    return value
    return doc_path.stem


@dataclass(frozen=True)
class ProjectInfo:
    slug: str
    title: str
    updated_at: str
    owners: List[str]
    tags: List[str]


@dataclass(frozen=True)
class ProjectStore:
    config: Config
    slug: str
    title: str
    doc_path: Path
    artifact_root: Path
    history_root: Path
    exports_root: Path
    summary_path: Path
    links_path: Path
    discussion_path: Path
    prompts_path: Path
    action_items_path: Path

    @staticmethod
    def normalize_slug(raw: str) -> str:
        base = raw.strip().lower().replace(" ", "-")
        cleaned = _IDENTIFIER_RE.sub("", base)
        return cleaned or "ltp-doc"

    @classmethod
    def create(
        cls,
        config: Config,
        slug: str,
        title: str,
        owners: Iterable[str],
        tags: Iterable[str],
        *,
        body: Optional[str] = None,
    ) -> ProjectStore:
        norm = cls.normalize_slug(slug or title)
        store = cls._build(config, norm, title)
        store._ensure_dirs()
        store._write_doc(body)
        store._ensure_summary(list(owners), list(tags))
        store._ensure_links()
        store._ensure_discussion()
        store._ensure_prompts()
        store._ensure_action_items()
        return store

    @classmethod
    def open(cls, config: Config, slug: str) -> ProjectStore:
        norm = cls.normalize_slug(slug)
        base = cls._build(config, norm, "")
        title = _infer_title(base.doc_path, base.summary_path)
        store = cls._build(config, norm, title)
        if not store.doc_path.exists():
            raise FileNotFoundError(store.doc_path)
        return store

    @classmethod
    def list(cls, config: Config, *, limit: Optional[int] = None) -> List[ProjectInfo]:
        docs = sorted(
            config.docs.glob("*.ltd.md"),
            key=lambda path: path.stat().st_mtime,
            reverse=True,
        )
        if limit is not None:
            docs = docs[:limit]
        projects: List[ProjectInfo] = []
        for doc_path in docs:
            slug = doc_path.stem
            artifact_root = config.artifacts / slug
            summary_path = artifact_root / "context_summary.json"
            title = _infer_title(doc_path, summary_path)
            updated_at = datetime.utcfromtimestamp(doc_path.stat().st_mtime).isoformat() + "Z"
            owners: List[str] = []
            tags: List[str] = []
            if summary_path.exists():
                try:
                    data = json.loads(summary_path.read_text(encoding="utf-8"))
                    owners = [str(item) for item in data.get("owners", []) if str(item).strip()]
                    tags = [str(item) for item in data.get("tags", []) if str(item).strip()]
                except json.JSONDecodeError:
                    pass
            projects.append(ProjectInfo(slug, title, updated_at, owners, tags))
        return projects

    def new_history_note_path(self) -> Path:
        return self.history_root / f"{_timestamp()}_notes.md"

    def new_history_patch_path(self) -> Path:
        return self.history_root / f"{_timestamp()}_patch.json"

    def _ensure_dirs(self) -> None:
        self.config.root.mkdir(parents=True, exist_ok=True)
        self.config.docs.mkdir(parents=True, exist_ok=True)
        self.artifact_root.mkdir(parents=True, exist_ok=True)
        self.history_root.mkdir(parents=True, exist_ok=True)
        self.exports_root.mkdir(parents=True, exist_ok=True)

    def _write_doc(self, body: Optional[str]) -> None:
        if body is None:
            if self.doc_path.exists():
                return
            lines = [
                f"# {self.title or self.slug}",
                "",
                "## Discussion",
                "",
                "## Decisions",
                "",
                "## Next Steps",
                "",
            ]
            body = "\n".join(lines)
        self.doc_path.write_text(body.rstrip() + "\n", encoding="utf-8")

    def _ensure_summary(self, owners: list[str], tags: list[str]) -> None:
        if self.summary_path.exists():
            return
        data = {
            "id": self.slug,
            "title": self.title or self.slug,
            "owners": owners,
            "tags": tags,
            "high_level_context": "",
            "constraints": [],
            "acceptance_criteria": [],
            "sections": [],
            "mentions": [],
            "related": []
        }
        self.summary_path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def _ensure_links(self) -> None:
        if self.links_path.exists():
            return
        self.links_path.write_text("", encoding="utf-8")

    def _ensure_discussion(self) -> None:
        if self.discussion_path.exists():
            return
        self.discussion_path.write_text("", encoding="utf-8")

    def _ensure_prompts(self) -> None:
        if self.prompts_path.exists():
            return
        self.prompts_path.write_text(json.dumps({"prompts": []}, indent=2), encoding="utf-8")

    def _ensure_action_items(self) -> None:
        if self.action_items_path.exists():
            return
        self.action_items_path.write_text(json.dumps({"action_items": []}, indent=2), encoding="utf-8")

    @staticmethod
    def _build(config: Config, slug: str, title: str) -> ProjectStore:
        doc_path = config.docs / f"{slug}.ltd.md"
        artifact_root = config.artifacts / slug
        history_root = artifact_root / "history"
        exports_root = artifact_root / "exports"
        summary_path = artifact_root / "context_summary.json"
        links_path = artifact_root / "links.jsonl"
        discussion_path = artifact_root / "discussion.md"
        prompts_path = artifact_root / "prompts.json"
        action_items_path = artifact_root / "action_items.json"
        return ProjectStore(config, slug, title, doc_path, artifact_root, history_root, exports_root, summary_path, links_path, discussion_path, prompts_path, action_items_path)
