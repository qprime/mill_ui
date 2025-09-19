# name: md_index.py
# path: skills/living_truth_partner/md_index.py
# role: Build Markdown section index with byte ranges
# deps: dataclasses, typing
# inputs: markdown text
# outputs: MarkdownIndex class

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List

__all__ = ["MarkdownIndex"]


def _line_offsets(lines: List[str]) -> List[int]:
    offsets = [0]
    total = 0
    for line in lines:
        total += len(line)
        offsets.append(total)
    return offsets


def _anchor(text: str) -> str:
    lowered = text.strip().lower()
    parts = [c if c.isalnum() else "-" for c in lowered]
    collapsed = []
    last_dash = False
    for c in parts:
        if c == "-":
            if not last_dash:
                collapsed.append(c)
            last_dash = True
        else:
            collapsed.append(c)
            last_dash = False
    slug = "".join(collapsed).strip("-")
    return slug or "section"


@dataclass(frozen=True)
class _Section:
    id: str
    level: int
    title: str
    start: int
    end: int


class MarkdownIndex:
    def __init__(self, sections: List[_Section], mapping: Dict[str, _Section]):
        self._sections = sections
        self._mapping = mapping

    @staticmethod
    def build(text: str) -> MarkdownIndex:
        lines = text.splitlines(True)
        offsets = _line_offsets(lines)
        found: List[_Section] = []
        for idx, line in enumerate(lines):
            if not line.startswith("#"):
                continue
            level = len(line) - len(line.lstrip("#"))
            if level <= 0 or level > 6:
                continue
            remainder = line[level:].strip()
            if not remainder:
                continue
            start_offset = offsets[idx]
            found.append(_Section("", level, remainder, start_offset, 0))
        total = len(text)
        updated: List[_Section] = []
        for idx, section in enumerate(found):
            next_start = found[idx + 1].start if idx + 1 < len(found) else total
            ident = _anchor(section.title)
            updated.append(_Section(ident, section.level, section.title, section.start, next_start))
        mapping = {s.id: s for s in updated}
        return MarkdownIndex(updated, mapping)

    def section(self, section_id: str) -> _Section | None:
        return self._mapping.get(section_id)

    def sections(self) -> List[_Section]:
        return list(self._sections)

    def slice(self, text: str, section_id: str) -> str:
        section = self.section(section_id)
        if section is None:
            return ""
        return text[section.start:section.end]

    def replace(self, text: str, section_id: str, replacement: str) -> str:
        section = self.section(section_id)
        if section is None:
            raise KeyError(section_id)
        return text[: section.start] + replacement + text[section.end :]
