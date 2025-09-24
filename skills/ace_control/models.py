from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, Iterable, List, Literal, Optional

ISO_TS = "%Y-%m-%dT%H:%M:%S.%fZ"


class Mode(str, Enum):
    AUTO = "auto"
    BUILD = "build"
    OPERATE = "operate"
    IDEATE = "ideate"


class BriefPlanPreference(str, Enum):
    AUTO = "auto"
    SHOW = "show"
    SKIP = "skip"


@dataclass
class ContextOptions:
    include: bool = False
    scope: str = "auto"  # auto|all|changed
    include_code: bool = False
    include_persona: bool = True
    max_files: Optional[int] = None
    model_name: Optional[str] = None
    persona: Optional[str] = None
    persona_category: str = ""
    explicit_files: List[str] = field(default_factory=list)
    focus_files: List[str] = field(default_factory=list)


@dataclass
class Brief:
    mode: Mode
    text: str
    machines: List[str] = field(default_factory=lambda: ["skylink"])
    tags: List[str] = field(default_factory=list)
    plan_preview: BriefPlanPreference = BriefPlanPreference.AUTO
    model: Optional[str] = None
    reasoning: Optional[str] = None
    notes: Optional[str] = None
    context: Optional[ContextOptions] = None

    @staticmethod
    def from_dict(payload: Dict[str, Any]) -> "Brief":
        mode = Mode(payload.get("mode", Mode.AUTO))
        plan_raw = payload.get("plan_preview", BriefPlanPreference.AUTO)
        plan = BriefPlanPreference(plan_raw)
        machines = payload.get("machines") or ["skylink"]
        if isinstance(machines, str):
            machines = [machines]
        ctx: Optional[ContextOptions] = None
        ctx_in = payload.get("context")
        if isinstance(ctx_in, dict):
            max_files_value = ctx_in.get("max_files")
            try:
                max_files = int(max_files_value) if max_files_value is not None else None
            except (TypeError, ValueError):
                max_files = None
            model_name_value = ctx_in.get("model_name")
            model_name = str(model_name_value) if model_name_value else None
            ctx = ContextOptions(
                include=bool(ctx_in.get("include", False)),
                scope=str(ctx_in.get("scope", "auto")),
                include_code=bool(ctx_in.get("include_code", False)),
                include_persona=bool(ctx_in.get("include_persona", True)),
                max_files=max_files,
                model_name=model_name,
                persona=ctx_in.get("persona"),
                persona_category=str(ctx_in.get("persona_category", "")),
                explicit_files=[str(p).strip() for p in ctx_in.get("explicit_files", []) if str(p).strip()],
                focus_files=[str(p).strip() for p in ctx_in.get("focus_files", []) if str(p).strip()],
            )
        return Brief(
            mode=mode,
            text=str(payload.get("text", "")).strip(),
            machines=[str(m).strip() for m in machines if str(m).strip()],
            tags=[str(tag).strip() for tag in payload.get("tags", []) if str(tag).strip()],
            plan_preview=plan,
            model=payload.get("model"),
            reasoning=payload.get("reasoning"),
            notes=payload.get("notes"),
            context=ctx,
        )

    def to_dict(self) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "mode": self.mode.value,
            "text": self.text,
            "machines": self.machines,
            "tags": self.tags,
            "plan_preview": self.plan_preview.value,
        }
        if self.model:
            payload["model"] = self.model
        if self.reasoning:
            payload["reasoning"] = self.reasoning
        if self.notes:
            payload["notes"] = self.notes
        if self.context:
            payload["context"] = {
                "include": self.context.include,
                "scope": self.context.scope,
                "include_code": self.context.include_code,
                "include_persona": self.context.include_persona,
                "max_files": self.context.max_files,
                "model_name": self.context.model_name,
                "persona": self.context.persona,
                "persona_category": self.context.persona_category,
                "explicit_files": self.context.explicit_files,
                "focus_files": self.context.focus_files,
            }
        return payload


class RunStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class RunRecord:
    id: str
    brief: Brief
    mode: Mode
    machines: List[str]
    status: RunStatus
    created_at: str
    updated_at: str
    headline: Optional[str] = None
    result_summary: Optional[str] = None
    plan_summary: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    artifacts: List[str] = field(default_factory=list)
    diff_path: Optional[str] = None
    prompt_path: Optional[str] = None
    log_path: Optional[str] = None
    commands: List[str] = field(default_factory=list)
    tests: List[str] = field(default_factory=list)
    notes: Optional[str] = None
    context_requests: List[Dict[str, object]] = field(default_factory=list)

    def touch(
        self,
        status: Optional[RunStatus] = None,
        *,
        headline: Optional[str] = None,
        result_summary: Optional[str] = None,
        plan_summary: Optional[str] = None,
        artifacts: Optional[Iterable[str]] = None,
        diff_path: Optional[str] = None,
        log_path: Optional[str] = None,
    ) -> None:
        if status is not None:
            self.status = status
        if headline is not None:
            self.headline = headline
        if result_summary is not None:
            self.result_summary = result_summary
        if plan_summary is not None:
            self.plan_summary = plan_summary
        if artifacts is not None:
            self.artifacts = list(artifacts)
        if diff_path is not None:
            self.diff_path = diff_path
        if log_path is not None:
            self.log_path = log_path
        self.updated_at = now_ts()

    def to_dict(self) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "id": self.id,
            "status": self.status.value,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "mode": self.mode.value,
            "machines": self.machines,
            "tags": self.tags,
            "brief": self.brief.to_dict(),
        }
        if self.headline:
            payload["headline"] = self.headline
        if self.result_summary:
            payload["result_summary"] = self.result_summary
        if self.plan_summary:
            payload["plan_summary"] = self.plan_summary
        if self.artifacts:
            payload["artifacts"] = self.artifacts
        if self.diff_path:
            payload["diff_path"] = self.diff_path
        if self.prompt_path:
            payload["prompt_path"] = self.prompt_path
        if self.log_path:
            payload["log_path"] = self.log_path
        if self.commands:
            payload["commands"] = self.commands
        if self.tests:
            payload["tests"] = self.tests
        if self.notes:
            payload["notes"] = self.notes
        if self.context_requests:
            payload["context_requests"] = self.context_requests
        return payload


@dataclass
class PlanOutline:
    items: List[str]

    def to_text(self) -> str:
        return "\n".join(self.items)


def now_ts() -> str:
    return datetime.utcnow().strftime(ISO_TS)


def ensure_ts(value: Optional[str]) -> str:
    if value:
        return value
    return now_ts()


def path_relative_to(root: Path, target: Path) -> str:
    try:
        return str(target.relative_to(root))
    except ValueError:
        return str(target)


def prune_empty(values: Dict[str, Any]) -> Dict[str, Any]:
    return {k: v for k, v in values.items() if v is not None}
