"""Parsing of structured ACE marker output."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional


_MARKER_RE = re.compile(r"^===\s*([A-Z_]+)\s*===\s*$")


@dataclass
class ContextRequest:
    path: str
    start: Optional[int] = None
    end: Optional[int] = None
    summary: bool = False


@dataclass
class MarkerSections:
    plan: Optional[str] = None
    patch: Optional[str] = None
    commands: List[str] = field(default_factory=list)
    tests: List[str] = field(default_factory=list)
    artifacts: List[str] = field(default_factory=list)
    notes: Optional[str] = None
    context_requests: List[ContextRequest] = field(default_factory=list)
    fixplan: Optional[str] = None
    extras: Dict[str, str] = field(default_factory=dict)


def parse_markers(text: str) -> MarkerSections:
    current: Optional[str] = None
    buckets: Dict[str, List[str]] = {}

    for raw_line in text.splitlines():
        match = _MARKER_RE.match(raw_line.strip())
        if match:
            current = match.group(1)
            buckets.setdefault(current, [])
            continue
        if current is None:
            continue
        buckets.setdefault(current, []).append(raw_line)

    sections = MarkerSections()

    def _join(marker: str) -> Optional[str]:
        lines = buckets.get(marker)
        if not lines:
            return None
        body = "\n".join(line.rstrip() for line in lines).strip()
        return body or None

    sections.plan = _join("PLAN")
    sections.patch = _join("PATCH")
    sections.notes = _join("NOTES")
    sections.fixplan = _join("FIXPLAN")

    def _collect_lines(marker: str) -> List[str]:
        lines = buckets.get(marker)
        if not lines:
            return []
        return [line.strip() for line in lines if line.strip()]

    sections.commands = _collect_lines("COMMANDS")
    sections.tests = _collect_lines("TESTS")
    sections.artifacts = _collect_lines("ARTIFACTS")

    req_lines = _collect_lines("CONTEXT_REQUESTS")
    for line in req_lines:
        request = _parse_context_request(line)
        if request:
            sections.context_requests.append(request)

    for marker, lines in buckets.items():
        if marker in {
            "PLAN",
            "PATCH",
            "COMMANDS",
            "TESTS",
            "ARTIFACTS",
            "NOTES",
            "CONTEXT_REQUESTS",
            "FIXPLAN",
        }:
            continue
        sections.extras[marker] = "\n".join(lines)

    return sections


_REQ_RE = re.compile(
    r"READ\s+"  # command
    r"(?P<path>[^\s]+)"  # file path
    r"(?:\s+lines=(?P<start>\d+)-(?:"  # line start-end
    r"(?P<end>\d+)"  # end
    r"))?"  # optional lines
    r"(?:\s+summary)?"  # summary flag
    ,
    re.IGNORECASE,
)


def _parse_context_request(line: str) -> Optional[ContextRequest]:
    tokens = line.strip()
    if not tokens:
        return None
    summary = tokens.lower().endswith(" summary")
    if summary:
        tokens = tokens[: -len(" summary")].strip()
    match = _REQ_RE.match(tokens)
    if not match:
        return None
    path = match.group("path")
    start = match.group("start")
    end = match.group("end")
    try:
        start_val = int(start) if start else None
    except ValueError:
        start_val = None
    try:
        end_val = int(end) if end else None
    except ValueError:
        end_val = None
    return ContextRequest(path=path, start=start_val, end=end_val, summary=summary)

