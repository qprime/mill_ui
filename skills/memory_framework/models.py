from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any, Dict, Iterable, List, Literal, Optional

MemoryType = Literal[
    "narrative",
    "truth",
    "artifact",
    "action",
    "brief",
    "decision",
    "note",
    "persona",
    "policy",
]

MemoryState = Literal["draft", "active", "review", "done", "archived"]
RegistryStatus = Literal["staged", "registered", "referenced", "archived"]
Visibility = Literal["internal", "external"]
Sensitivity = Literal["low", "medium", "high", "safety", "pii"]
ActorType = Literal["human", "ai", "service"]
ActionStatus = Literal[
    "proposed",
    "auto_checked",
    "ready",
    "needs_human",
    "applied",
    "failed",
]
EscalationReason = Literal[
    "guardrail_fail",
    "risk_flag",
    "confidence_gap",
    "policy_required",
]


@dataclass(frozen=True)
class Actor:
    actor_id: str
    actor_type: ActorType

    def to_dict(self) -> Dict[str, str]:
        return {"actor_id": self.actor_id, "actor_type": self.actor_type}

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "Actor":
        return Actor(actor_id=data["actor_id"], actor_type=data["actor_type"])


@dataclass
class Relations:
    thread_of: Optional[str] = None
    derived_from: List[str] = field(default_factory=list)
    produces: List[str] = field(default_factory=list)
    links: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "derived_from": list(self.derived_from),
            "produces": list(self.produces),
            "links": list(self.links),
        }
        if self.thread_of:
            payload["thread_of"] = self.thread_of
        return payload

    @staticmethod
    def from_dict(data: Optional[Dict[str, Any]]) -> "Relations":
        if not data:
            return Relations()
        return Relations(
            thread_of=data.get("thread_of"),
            derived_from=list(data.get("derived_from", [])),
            produces=list(data.get("produces", [])),
            links=list(data.get("links", [])),
        )


@dataclass
class MemoryContent:
    path: Optional[str] = None
    bytes: Optional[str] = None
    sha256: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        payload: Dict[str, Any] = {}
        if self.path is not None:
            payload["path"] = self.path
        if self.bytes is not None:
            payload["bytes"] = self.bytes
        if self.sha256 is not None:
            payload["sha256"] = self.sha256
        return payload

    @staticmethod
    def from_dict(data: Optional[Dict[str, Any]]) -> "MemoryContent":
        if not data:
            return MemoryContent()
        return MemoryContent(
            path=data.get("path"),
            bytes=data.get("bytes"),
            sha256=data.get("sha256"),
        )


@dataclass
class MemoryMetadata:
    owners: List[str] = field(default_factory=list)
    constraints: Dict[str, Any] = field(default_factory=dict)
    acceptance_criteria: List[str] = field(default_factory=list)
    visibility: Visibility = "internal"
    sensitivity: Sensitivity = "low"
    policy_refs: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "owners": list(self.owners),
            "constraints": dict(self.constraints),
            "acceptance_criteria": list(self.acceptance_criteria),
            "visibility": self.visibility,
            "sensitivity": self.sensitivity,
            "policy_refs": list(self.policy_refs),
        }

    @staticmethod
    def from_dict(data: Optional[Dict[str, Any]]) -> "MemoryMetadata":
        if not data:
            return MemoryMetadata()
        return MemoryMetadata(
            owners=list(data.get("owners", [])),
            constraints=dict(data.get("constraints", {})),
            acceptance_criteria=list(data.get("acceptance_criteria", [])),
            visibility=data.get("visibility", "internal"),
            sensitivity=data.get("sensitivity", "low"),
            policy_refs=list(data.get("policy_refs", [])),
        )


@dataclass
class Memory:
    id: str
    type: MemoryType
    purpose: str
    handle: Optional[str]
    title: str
    tags: List[str]
    state: MemoryState
    registry_status: RegistryStatus
    relations: Relations
    content: MemoryContent
    metadata: MemoryMetadata
    actor: Actor
    created_at: str
    updated_at: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "type": self.type,
            "purpose": self.purpose,
            "handle": self.handle,
            "title": self.title,
            "tags": list(self.tags),
            "state": self.state,
            "registry_status": self.registry_status,
            "relations": self.relations.to_dict(),
            "content": self.content.to_dict(),
            "metadata": self.metadata.to_dict(),
            "actor": self.actor.to_dict(),
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "Memory":
        return Memory(
            id=data["id"],
            type=data["type"],
            purpose=data["purpose"],
            handle=data.get("handle"),
            title=data["title"],
            tags=list(data.get("tags", [])),
            state=data.get("state", "draft"),
            registry_status=data.get("registry_status", "staged"),
            relations=Relations.from_dict(data.get("relations")),
            content=MemoryContent.from_dict(data.get("content")),
            metadata=MemoryMetadata.from_dict(data.get("metadata")),
            actor=Actor.from_dict(data.get("actor", {})),
            created_at=data.get("created_at", ""),
            updated_at=data.get("updated_at", ""),
        )

    def with_registry_status(self, status: RegistryStatus, *, updated_at: str) -> "Memory":
        clone = replace(self)
        clone.registry_status = status
        clone.updated_at = updated_at
        return clone

    def with_state(self, state: MemoryState, *, updated_at: str) -> "Memory":
        clone = replace(self)
        clone.state = state
        clone.updated_at = updated_at
        return clone


@dataclass
class ArtifactMeta:
    id: str
    type: str
    purpose: str
    title: str
    produced_by_action_id: Optional[str]
    lineage_inputs: List[str]
    hashes: Dict[str, str]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "type": self.type,
            "purpose": self.purpose,
            "title": self.title,
            "produced_by": {"action_id": self.produced_by_action_id},
            "lineage": {"inputs": list(self.lineage_inputs)},
            "hashes": dict(self.hashes),
        }

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "ArtifactMeta":
        produced = data.get("produced_by", {})
        lineage = data.get("lineage", {})
        return ArtifactMeta(
            id=data["id"],
            type=data.get("type", "artifact"),
            purpose=data.get("purpose", "artifact"),
            title=data.get("title", ""),
            produced_by_action_id=produced.get("action_id"),
            lineage_inputs=list(lineage.get("inputs", [])),
            hashes=dict(data.get("hashes", {})),
        )


@dataclass
class Action:
    id: str
    title: str
    intent: str
    thread: Optional[str]
    truth_ref: Optional[str]
    requirements: List[str]
    constraints: Dict[str, Any]
    context_scope: Dict[str, Any]
    executor: Dict[str, Any]
    status: ActionStatus
    escalation_reasons: List[EscalationReason]
    actor: Actor
    created_at: str
    updated_at: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "intent": self.intent,
            "thread": self.thread,
            "truth_ref": self.truth_ref,
            "requirements": list(self.requirements),
            "constraints": dict(self.constraints),
            "context_scope": dict(self.context_scope),
            "executor": dict(self.executor),
            "status": self.status,
            "escalation_reasons": list(self.escalation_reasons),
            "actor": self.actor.to_dict(),
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    def to_memory(self, *, purpose: str, state: MemoryState, registry_status: RegistryStatus) -> Memory:
        memory = Memory(
            id=self.id,
            type="action",
            purpose=purpose,
            handle=self.thread,
            title=self.title,
            tags=[self.intent],
            state=state,
            registry_status=registry_status,
            relations=Relations(thread_of=self.thread),
            content=MemoryContent(bytes=None, path=None, sha256=None),
            metadata=MemoryMetadata(constraints=self.constraints, acceptance_criteria=[]),
            actor=self.actor,
            created_at=self.created_at,
            updated_at=self.updated_at,
        )
        # attach struct payload inside metadata constraints for deterministic capture
        payload = memory.metadata.constraints
        payload["action"] = self.to_dict()
        return memory

    @staticmethod
    def from_memory(memory: Memory) -> "Action":
        data = dict(memory.metadata.constraints.get("action", {}))
        actor = memory.actor
        return Action(
            id=data.get("id", memory.id),
            title=data.get("title", memory.title),
            intent=data.get("intent", memory.purpose),
            thread=data.get("thread"),
            truth_ref=data.get("truth_ref"),
            requirements=list(data.get("requirements", [])),
            constraints=dict(data.get("constraints", {})),
            context_scope=dict(data.get("context_scope", {})),
            executor=dict(data.get("executor", {})),
            status=data.get("status", "proposed"),
            escalation_reasons=list(data.get("escalation_reasons", [])),
            actor=actor,
            created_at=data.get("created_at", memory.created_at),
            updated_at=data.get("updated_at", memory.updated_at),
        )

    def with_status(
        self,
        status: ActionStatus,
        *,
        updated_at: str,
        escalation_reasons: Optional[Iterable[EscalationReason]] = None,
        constraints: Optional[Dict[str, Any]] = None,
        executor: Optional[Dict[str, Any]] = None,
    ) -> "Action":
        clone = replace(self)
        clone.status = status
        clone.updated_at = updated_at
        if escalation_reasons is not None:
            clone.escalation_reasons = list(escalation_reasons)
        if constraints is not None:
            clone.constraints = dict(constraints)
        if executor is not None:
            clone.executor = dict(executor)
        return clone


@dataclass
class Brief:
    id: str
    inputs: Dict[str, Any]
    budgets: Dict[str, Any]
    drops: List[Dict[str, Any]]
    prompt_path: str
    prompt_sha256: str
    timestamp: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "inputs": dict(self.inputs),
            "budgets": dict(self.budgets),
            "drops": list(self.drops),
            "prompt_path": self.prompt_path,
            "prompt_sha256": self.prompt_sha256,
            "timestamp": self.timestamp,
        }

    def to_memory(self, *, actor: Actor, title: str, registry_status: RegistryStatus, state: MemoryState, created_at: str, updated_at: str) -> Memory:
        memory = Memory(
            id=self.id,
            type="brief",
            purpose="brief.prompt",
            handle=None,
            title=title,
            tags=[],
            state=state,
            registry_status=registry_status,
            relations=Relations(),
            content=MemoryContent(path=self.prompt_path, sha256=self.prompt_sha256),
            metadata=MemoryMetadata(constraints={}, acceptance_criteria=list(self.inputs.get("acceptance_criteria", []))),
            actor=actor,
            created_at=created_at,
            updated_at=updated_at,
        )
        memory.metadata.constraints["brief"] = self.to_dict()
        return memory


@dataclass
class Decision:
    id: str
    action_id: str
    approver: Actor
    signature: str
    reason: str
    timestamp: str
    policy_check_path: Optional[str]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "action_id": self.action_id,
            "approver": self.approver.to_dict(),
            "signature": self.signature,
            "reason": self.reason,
            "timestamp": self.timestamp,
            "policy_check_path": self.policy_check_path,
        }

    def to_memory(self, *, state: MemoryState, registry_status: RegistryStatus, title: str) -> Memory:
        return Memory(
            id=self.id,
            type="decision",
            purpose="decision.record",
            handle=self.action_id,
            title=title,
            tags=["decision"],
            state=state,
            registry_status=registry_status,
            relations=Relations(thread_of=self.action_id),
            content=MemoryContent(path=self.policy_check_path),
            metadata=MemoryMetadata(constraints={"decision": self.to_dict()}),
            actor=self.approver,
            created_at=self.timestamp,
            updated_at=self.timestamp,
        )


__all__ = [
    "Actor",
    "ActorType",
    "Action",
    "ActionStatus",
    "ArtifactMeta",
    "Brief",
    "Decision",
    "EscalationReason",
    "Memory",
    "MemoryContent",
    "MemoryMetadata",
    "MemoryState",
    "MemoryType",
    "Relations",
    "RegistryStatus",
    "Sensitivity",
    "Visibility",
]
