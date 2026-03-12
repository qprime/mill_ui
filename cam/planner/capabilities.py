from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ir.removal_intent import RemovalIntent


class ConstraintSupport(Enum):
    HONORED = "honored"
    PARTIAL = "partial"
    VALIDATED_ONLY = "validated_only"
    NOT_IMPLEMENTED = "not_implemented"
    IGNORED = "ignored"


@dataclass(frozen=True)
class ConstraintStatus:
    support: ConstraintSupport
    safety_critical: bool = False
    note: str = ""


PLANNER_CAPABILITIES: dict[str, ConstraintStatus] = {
    "bounds": ConstraintStatus(ConstraintSupport.HONORED),
    "depth_profile.z_top": ConstraintStatus(ConstraintSupport.HONORED),
    "depth_profile.z_bottom": ConstraintStatus(ConstraintSupport.HONORED),
    "depth_profile.mode.constant": ConstraintStatus(ConstraintSupport.HONORED),
    "depth_profile.mode.v_carve": ConstraintStatus(
        ConstraintSupport.NOT_IMPLEMENTED,
        note="v_angle_deg not passed to planner",
    ),
    "depth_profile.mode.linear_gradient": ConstraintStatus(
        ConstraintSupport.NOT_IMPLEMENTED,
        note="gradient_direction_deg not passed to planner",
    ),
    "constraints.tabs": ConstraintStatus(
        ConstraintSupport.HONORED,
        note="Profiles only",
    ),
    "constraints.onion_skin_mm": ConstraintStatus(
        ConstraintSupport.HONORED,
        note="Profiles only; mutually exclusive with tabs",
    ),
    "constraints.keepouts": ConstraintStatus(
        ConstraintSupport.HONORED,
        safety_critical=True,
        note="Toolpath avoids keepout bounds",
    ),
    "constraints.islands": ConstraintStatus(
        ConstraintSupport.NOT_IMPLEMENTED,
    ),
    "constraints.edge_treatment": ConstraintStatus(
        ConstraintSupport.HONORED,
        note="Allowance type splits pocket/profile into rough+finish passes",
    ),
    "edge_feature": ConstraintStatus(
        ConstraintSupport.HONORED,
        note="Bevel/chamfer produce V-bit toolpaths; roundover uses roundover bit",
    ),
    "constraints.tolerance_mm": ConstraintStatus(
        ConstraintSupport.NOT_IMPLEMENTED,
        note="Uses global tolerance",
    ),
    "constraints.safe_z_mm": ConstraintStatus(
        ConstraintSupport.NOT_IMPLEMENTED,
        note="Uses global safe_z",
    ),
    "allowance": ConstraintStatus(
        ConstraintSupport.VALIDATED_ONLY,
        note="Applied upstream by generators or via global kerf_width_mm",
    ),
    "dogbone": ConstraintStatus(
        ConstraintSupport.HONORED,
        note="Rectangular pocket and assembly joinery internal corners",
    ),
    "corner_cleanup": ConstraintStatus(
        ConstraintSupport.HONORED,
        note="Secondary tool pass for pocket internal corners",
    ),
    "rest": ConstraintStatus(
        ConstraintSupport.HONORED,
        note="Two-tool rest pocketing: rough with large tool, finish corners with small tool",
    ),
}


@dataclass(frozen=True)
class ConstraintAuditEntry:
    constraint: str
    status: ConstraintSupport
    safety_critical: bool
    count: int
    note: str = ""


@dataclass(frozen=True)
class ConstraintAuditResult:
    entries: tuple[ConstraintAuditEntry, ...]
    errors: tuple[str, ...]
    warnings: tuple[str, ...]

    def has_errors(self) -> bool:
        return len(self.errors) > 0

    def format_summary(self) -> str:
        lines = ["Constraint Audit:"]
        for entry in self.entries:
            if entry.count == 0:
                continue
            status_str = entry.status.value.upper()
            suffix = ""
            if entry.status in (
                ConstraintSupport.NOT_IMPLEMENTED,
                ConstraintSupport.IGNORED,
                ConstraintSupport.VALIDATED_ONLY,
            ):
                suffix = " [warning]"
            if entry.safety_critical and entry.status != ConstraintSupport.HONORED:
                suffix = " [ERROR]"
            lines.append(f"  {entry.constraint}: {status_str} ({entry.count}) {suffix}".rstrip())
        return "\n".join(lines)


def audit_constraints(intents: list[RemovalIntent]) -> ConstraintAuditResult:
    counts: dict[str, int] = {
        "tabs": 0,
        "keepouts": 0,
        "islands": 0,
        "edge_treatment": 0,
        "tolerance_mm_custom": 0,
        "safe_z_mm_custom": 0,
        "v_carve": 0,
        "linear_gradient": 0,
        "allowance_nonzero": 0,
        "edge_feature": 0,
        "dogbone": 0,
        "corner_cleanup": 0,
        "rest": 0,
    }

    for intent in intents:
        if intent.constraints.tabs is not None:
            counts["tabs"] += 1
        if intent.constraints.keepouts:
            counts["keepouts"] += len(intent.constraints.keepouts)
        if intent.constraints.islands:
            counts["islands"] += len(intent.constraints.islands)
        if intent.constraints.edge_treatment is not None:
            counts["edge_treatment"] += 1
        if intent.constraints.tolerance_mm != 0.1:
            counts["tolerance_mm_custom"] += 1
        if intent.constraints.safe_z_mm != 5.0:
            counts["safe_z_mm_custom"] += 1
        if intent.depth_profile.mode == "v_carve":
            counts["v_carve"] += 1
        if intent.depth_profile.mode == "linear_gradient":
            counts["linear_gradient"] += 1
        if (
            intent.allowance.inside != 0.0
            or intent.allowance.outside != 0.0
            or intent.allowance.on != 0.0
            or intent.allowance.kerf_compensation != 0.0
        ):
            counts["allowance_nonzero"] += 1
        if intent.edge_feature is not None:
            counts["edge_feature"] += 1
        if intent.dogbone is not None:
            counts["dogbone"] += 1
        if intent.corner_cleanup_tool_diameter_mm is not None:
            counts["corner_cleanup"] += 1
        if intent.rest is not None:
            counts["rest"] += 1

    entries: list[ConstraintAuditEntry] = []
    errors: list[str] = []
    warnings: list[str] = []

    constraint_mapping = [
        ("tabs", "constraints.tabs"),
        ("keepouts", "constraints.keepouts"),
        ("islands", "constraints.islands"),
        ("edge_treatment", "constraints.edge_treatment"),
        ("tolerance_mm_custom", "constraints.tolerance_mm"),
        ("safe_z_mm_custom", "constraints.safe_z_mm"),
        ("v_carve", "depth_profile.mode.v_carve"),
        ("linear_gradient", "depth_profile.mode.linear_gradient"),
        ("allowance_nonzero", "allowance"),
        ("edge_feature", "edge_feature"),
        ("dogbone", "dogbone"),
        ("corner_cleanup", "corner_cleanup"),
        ("rest", "rest"),
    ]

    for count_key, capability_key in constraint_mapping:
        count = counts[count_key]
        cap = PLANNER_CAPABILITIES.get(capability_key)
        if cap is None:
            continue

        entry = ConstraintAuditEntry(
            constraint=count_key,
            status=cap.support,
            safety_critical=cap.safety_critical,
            count=count,
            note=cap.note,
        )
        entries.append(entry)

        if count > 0:
            if cap.safety_critical and cap.support != ConstraintSupport.HONORED:
                errors.append(
                    f"Safety-critical constraint '{count_key}' has {count} instance(s) "
                    f"but support status is {cap.support.value}. "
                    f"This would be ignored by the planner."
                )
            elif cap.support in (
                ConstraintSupport.NOT_IMPLEMENTED,
                ConstraintSupport.IGNORED,
            ):
                warnings.append(
                    f"Constraint '{count_key}' has {count} instance(s) "
                    f"but support status is {cap.support.value}. "
                    f"This will be ignored by the planner."
                )
            elif cap.support == ConstraintSupport.VALIDATED_ONLY:
                warnings.append(
                    f"Constraint '{count_key}' has {count} instance(s) "
                    f"and is validated but not passed to planner. {cap.note}"
                )

    return ConstraintAuditResult(
        entries=tuple(entries),
        errors=tuple(errors),
        warnings=tuple(warnings),
    )
