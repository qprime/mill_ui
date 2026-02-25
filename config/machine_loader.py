from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ruamel.yaml import YAML


@dataclass(frozen=True)
class CNCMachine2D:
    name: str
    envelope_x_min: float
    envelope_x_max: float
    envelope_y_min: float
    envelope_y_max: float

    def __post_init__(self):
        if self.envelope_x_max <= self.envelope_x_min:
            raise ValueError(
                f"envelope_x_max ({self.envelope_x_max}) must be greater than envelope_x_min ({self.envelope_x_min})"
            )
        if self.envelope_y_max <= self.envelope_y_min:
            raise ValueError(
                f"envelope_y_max ({self.envelope_y_max}) must be greater than envelope_y_min ({self.envelope_y_min})"
            )

    @property
    def envelope_width(self) -> float:
        return self.envelope_x_max - self.envelope_x_min

    @property
    def envelope_height(self) -> float:
        return self.envelope_y_max - self.envelope_y_min

    @property
    def envelope_center_x(self) -> float:
        return (self.envelope_x_min + self.envelope_x_max) / 2.0

    @property
    def envelope_center_y(self) -> float:
        return (self.envelope_y_min + self.envelope_y_max) / 2.0


@dataclass(frozen=True)
class Wasteboard2D:
    width_mm: float
    height_mm: float
    offset_x: float
    offset_y: float

    def __post_init__(self):
        if self.width_mm <= 0:
            raise ValueError(f"Wasteboard width must be positive, got {self.width_mm}")
        if self.height_mm <= 0:
            raise ValueError(f"Wasteboard height must be positive, got {self.height_mm}")

    @property
    def x_min(self) -> float:
        return self.offset_x

    @property
    def x_max(self) -> float:
        return self.offset_x + self.width_mm

    @property
    def y_min(self) -> float:
        return self.offset_y

    @property
    def y_max(self) -> float:
        return self.offset_y + self.height_mm

    @property
    def center_x(self) -> float:
        return self.offset_x + self.width_mm / 2.0

    @property
    def center_y(self) -> float:
        return self.offset_y + self.height_mm / 2.0


@dataclass(frozen=True)
class MachineDefaults:
    safe_z_mm: float = 5.0
    feed_rate_mm_min: float = 1500.0
    plunge_rate_mm_min: float = 500.0


@dataclass(frozen=True)
class MachineConfig:
    machine: CNCMachine2D
    wasteboard: Wasteboard2D | None = None
    defaults: MachineDefaults = field(default_factory=MachineDefaults)

    def __post_init__(self):
        if self.wasteboard is not None:
            wb = self.wasteboard
            m = self.machine
            if wb.x_min < m.envelope_x_min - 0.001:
                raise ValueError(f"Wasteboard x_min ({wb.x_min}) is outside envelope x_min ({m.envelope_x_min})")
            if wb.x_max > m.envelope_x_max + 0.001:
                raise ValueError(f"Wasteboard x_max ({wb.x_max}) exceeds envelope x_max ({m.envelope_x_max})")
            if wb.y_min < m.envelope_y_min - 0.001:
                raise ValueError(f"Wasteboard y_min ({wb.y_min}) is outside envelope y_min ({m.envelope_y_min})")
            if wb.y_max > m.envelope_y_max + 0.001:
                raise ValueError(f"Wasteboard y_max ({wb.y_max}) exceeds envelope y_max ({m.envelope_y_max})")

    def compute_margins(self) -> dict[str, float]:
        if self.wasteboard is None:
            return {"left": 0, "right": 0, "top": 0, "bottom": 0}

        wb = self.wasteboard
        m = self.machine
        return {
            "left": wb.x_min - m.envelope_x_min,
            "right": m.envelope_x_max - wb.x_max,
            "top": m.envelope_y_max - wb.y_max,
            "bottom": wb.y_min - m.envelope_y_min,
        }

    def effective_envelope(self, bit_radius: float = 0.0) -> tuple[float, float, float, float]:
        m = self.machine
        return (
            m.envelope_x_min + bit_radius,
            m.envelope_y_min + bit_radius,
            m.envelope_x_max - bit_radius,
            m.envelope_y_max - bit_radius,
        )


@dataclass(frozen=True)
class Endmill:
    name: str
    diameter_mm: float
    flute_length_mm: float
    shank_diameter_mm: float
    flutes: int
    type: str
    v_angle_deg: float | None = None

    def __post_init__(self):
        if self.diameter_mm <= 0:
            raise ValueError(f"Endmill diameter must be positive, got {self.diameter_mm}")
        if self.flute_length_mm <= 0:
            raise ValueError(f"Endmill flute_length must be positive, got {self.flute_length_mm}")
        if self.flutes <= 0:
            raise ValueError(f"Endmill flutes must be positive, got {self.flutes}")

    @property
    def radius_mm(self) -> float:
        return self.diameter_mm / 2.0


@dataclass(frozen=True)
class Spindle:
    name: str
    rpm_min: int
    rpm_max: int

    def __post_init__(self):
        if self.rpm_min >= self.rpm_max:
            raise ValueError(f"Spindle rpm_min ({self.rpm_min}) must be less than rpm_max ({self.rpm_max})")
        if self.rpm_min <= 0:
            raise ValueError(f"Spindle rpm_min must be positive, got {self.rpm_min}")


@dataclass(frozen=True)
class FeedsEntry:
    endmill: str
    material: str
    chipload: float
    rpm: float
    depth_per_pass: float
    plunge_factor: float
    stepover_percent: float | None = None

    def __post_init__(self):
        if self.chipload <= 0:
            raise ValueError(f"Chipload must be positive, got {self.chipload}")
        if self.rpm <= 0:
            raise ValueError(f"RPM must be positive, got {self.rpm}")
        if self.depth_per_pass <= 0:
            raise ValueError(f"depth_per_pass must be positive, got {self.depth_per_pass}")
        if self.plunge_factor <= 0 or self.plunge_factor > 1.0:
            raise ValueError(f"plunge_factor must be in (0, 1.0], got {self.plunge_factor}")


_ENDMILL_TYPE_TO_KIND: dict[str, str] = {
    "upcut_spiral": "flat",
    "downcut_spiral": "flat",
    "compression": "flat",
    "straight": "flat",
    "v_bit": "v",
    "ball": "ball",
    "engraving": "ball",
}

_ENDMILL_TYPE_TO_ROTATION: dict[str, str | None] = {
    "upcut_spiral": "upcut",
    "downcut_spiral": "downcut",
    "compression": "compression",
    "straight": None,
    "v_bit": None,
    "ball": None,
    "engraving": None,
}


def resolve_tool_selection(endmill: Endmill, feeds: FeedsEntry) -> dict[str, Any]:
    feed_xy = feeds.rpm * endmill.flutes * feeds.chipload
    feed_z = feed_xy * feeds.plunge_factor
    kind = _ENDMILL_TYPE_TO_KIND.get(endmill.type, "flat")
    rotation = _ENDMILL_TYPE_TO_ROTATION.get(endmill.type)

    result: dict[str, Any] = {
        "name": endmill.name,
        "diameter": endmill.diameter_mm,
        "kind": kind,
        "rpm": feeds.rpm,
        "feed_xy": feed_xy,
        "feed_z": feed_z,
        "depth_per_pass": feeds.depth_per_pass,
        "rotation": rotation,
    }
    if feeds.stepover_percent is not None:
        result["stepover_percent"] = feeds.stepover_percent
    if endmill.v_angle_deg is not None:
        result["v_angle_deg"] = endmill.v_angle_deg
    return result


def build_tool_db(
    endmills: list[Endmill],
    feeds: list[FeedsEntry],
    material: str,
) -> list[dict[str, Any]]:
    feeds_by_key = {(f.endmill, f.material.lower()): f for f in feeds}
    mat = material.lower()

    result: list[dict[str, Any]] = []
    for em in endmills:
        entry = feeds_by_key.get((em.name, mat))
        if entry is not None:
            result.append(resolve_tool_selection(em, entry))

    if not result:
        available = sorted({f.material for f in feeds})
        raise ValueError(
            f"No endmills have feeds entries for material {material!r}. Available materials in feeds: {available}"
        )
    return result


def load_cnc_machine(path: Path | str) -> MachineConfig:
    path = Path(path)
    yaml = YAML(typ="safe")
    with path.open() as f:
        data = yaml.load(f)

    name = data.get("name", path.stem)
    envelope = data.get("envelope", {})
    wasteboard_data = data.get("wasteboard")
    defaults_data = data.get("defaults", {})

    machine = CNCMachine2D(
        name=name,
        envelope_x_min=float(envelope.get("x_min", 0)),
        envelope_x_max=float(envelope.get("x_max", 0)),
        envelope_y_min=float(envelope.get("y_min", 0)),
        envelope_y_max=float(envelope.get("y_max", 0)),
    )

    wasteboard = None
    if wasteboard_data:
        wasteboard = Wasteboard2D(
            width_mm=float(wasteboard_data.get("width_mm", 0)),
            height_mm=float(wasteboard_data.get("height_mm", 0)),
            offset_x=float(wasteboard_data.get("offset_x", 0)),
            offset_y=float(wasteboard_data.get("offset_y", 0)),
        )

    defaults = MachineDefaults(
        safe_z_mm=float(defaults_data.get("safe_z_mm", 5.0)),
        feed_rate_mm_min=float(defaults_data.get("feed_rate_mm_min", 1500.0)),
        plunge_rate_mm_min=float(defaults_data.get("plunge_rate_mm_min", 500.0)),
    )

    return MachineConfig(machine=machine, wasteboard=wasteboard, defaults=defaults)


def load_endmills(path: Path | str) -> list[Endmill]:
    path = Path(path)
    yaml = YAML(typ="safe")
    with path.open() as f:
        data = yaml.load(f)

    endmills = []
    for item in data.get("endmills", []):
        endmill = Endmill(
            name=item.get("name", ""),
            diameter_mm=float(item.get("diameter_mm", 0)),
            flute_length_mm=float(item.get("flute_length_mm", 0)),
            shank_diameter_mm=float(item.get("shank_diameter_mm", 0)),
            flutes=int(item.get("flutes", 1)),
            type=item.get("type", "unknown"),
            v_angle_deg=float(item["v_angle_deg"]) if "v_angle_deg" in item else None,
        )
        endmills.append(endmill)

    return endmills


def load_spindles(path: Path | str) -> list[Spindle]:
    path = Path(path)
    yaml = YAML(typ="safe")
    with path.open() as f:
        data = yaml.load(f)

    spindles = []
    for item in data.get("spindles", []):
        spindle = Spindle(
            name=item.get("name", ""),
            rpm_min=int(item.get("rpm_min", 0)),
            rpm_max=int(item.get("rpm_max", 0)),
        )
        spindles.append(spindle)

    return spindles


def load_feeds(path: Path | str) -> list[FeedsEntry]:
    path = Path(path)
    yaml = YAML(typ="safe")
    with path.open() as f:
        data = yaml.load(f)

    entries = []
    for item in data.get("feeds", []):
        entry = FeedsEntry(
            endmill=item.get("endmill", ""),
            material=item.get("material", ""),
            chipload=float(item.get("chipload", 0)),
            rpm=float(item.get("rpm", 0)),
            depth_per_pass=float(item.get("depth_per_pass", 0)),
            plunge_factor=float(item.get("plunge_factor", 0)),
            stepover_percent=float(item["stepover_percent"]) if "stepover_percent" in item else None,
        )
        entries.append(entry)

    return entries


def get_machines_dir() -> Path:
    return Path(__file__).parent.parent / "machines"


def list_available_machines() -> list[str]:
    machines_dir = get_machines_dir() / "cnc"
    if not machines_dir.exists():
        return []
    return [p.stem for p in machines_dir.glob("*.yml")]


def load_machine_by_name(name: str) -> MachineConfig:
    machines_dir = get_machines_dir() / "cnc"
    path = machines_dir / f"{name}.yml"
    if not path.exists():
        raise FileNotFoundError(f"Machine config not found: {path}")
    return load_cnc_machine(path)


__all__ = [
    "CNCMachine2D",
    "Endmill",
    "FeedsEntry",
    "MachineConfig",
    "MachineDefaults",
    "Spindle",
    "Wasteboard2D",
    "build_tool_db",
    "get_machines_dir",
    "list_available_machines",
    "load_cnc_machine",
    "load_endmills",
    "load_feeds",
    "load_machine_by_name",
    "load_spindles",
    "resolve_tool_selection",
]
