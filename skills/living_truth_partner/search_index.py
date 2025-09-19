# name: search_index.py
# path: skills/living_truth_partner/search_index.py
# role: Build and query inverted index over LTD sections
# deps: dataclasses, pathlib, typing, skills.living_truth_partner.md_index
# inputs: Config, query
# outputs: SearchIndex class

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List

from skills.living_truth_partner.config import Config
from skills.living_truth_partner.md_index import MarkdownIndex

__all__ = ["SearchIndex"]


def _tokenize(text: str) -> List[str]:
    lowered = text.lower()
    out: List[str] = []
    token = []
    for char in lowered:
        if char.isalnum():
            token.append(char)
        else:
            if token:
                out.append("".join(token))
                token = []
    if token:
        out.append("".join(token))
    return out


@dataclass(frozen=True)
class _Hit:
    doc: str
    section: str
    title: str
    snippet: str


class SearchIndex:
    @dataclass(frozen=True)
    class Hit:
        doc: str
        section: str
        title: str
        snippet: str

    def __init__(self, mapping: Dict[str, List[_Hit]]):
        self._mapping = mapping

    @staticmethod
    def build(config: Config) -> SearchIndex:
        mapping: Dict[str, List[_Hit]] = {}
        docs = sorted(config.docs.glob("*.ltd.md"))
        for doc_path in docs:
            slug = doc_path.stem
            text = doc_path.read_text(encoding="utf-8")
            index = MarkdownIndex.build(text)
            for section in index.sections():
                body = index.slice(text, section.id)
                preview_lines = [line.strip() for line in body.splitlines() if line.strip()]
                snippet = preview_lines[0] if preview_lines else ""
                tokens = set(_tokenize(section.title + " " + body))
                hit = _Hit(slug, section.id, section.title, snippet[:200])
                for token in tokens:
                    mapping.setdefault(token, []).append(hit)
        return SearchIndex(mapping)

    def search(self, query: str, limit: int = 10) -> List[Hit]:
        tokens = _tokenize(query)
        hits: List[SearchIndex.Hit] = []
        seen: set[tuple[str, str]] = set()
        for token in tokens:
            for hit in self._mapping.get(token, []):
                key = (hit.doc, hit.section)
                if key in seen:
                    continue
                seen.add(key)
                hits.append(SearchIndex.Hit(hit.doc, hit.section, hit.title, hit.snippet))
                if len(hits) >= limit:
                    return hits
        return hits

    def dump(self) -> Dict[str, List[_Hit]]:
        return self._mapping
