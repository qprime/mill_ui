from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

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
                f"envelope_x_max ({self.envelope_x_max}) must be greater than "
                f"envelope_x_min ({self.envelope_x_min})"
            )
        if self.envelope_y_max <= self.envelope_y_min:
            raise ValueError(
                f"envelope_y_max ({self.envelope_y_max}) must be greater than "
                f"envelope_y_min ({self.envelope_y_min})"
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
                raise ValueError(
                    f"Wasteboard x_min ({wb.x_min}) is outside envelope x_min ({m.envelope_x_min})"
                )
            if wb.x_max > m.envelope_x_max + 0.001:
                raise ValueError(
                    f"Wasteboard x_max ({wb.x_max}) exceeds envelope x_max ({m.envelope_x_max})"
                )
            if wb.y_min < m.envelope_y_min - 0.001:
                raise ValueError(
                    f"Wasteboard y_min ({wb.y_min}) is outside envelope y_min ({m.envelope_y_min})"
                )
            if wb.y_max > m.envelope_y_max + 0.001:
                raise ValueError(
                    f"Wasteboard y_max ({wb.y_max}) exceeds envelope y_max ({m.envelope_y_max})"
                )

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
            raise ValueError(
                f"Spindle rpm_min ({self.rpm_min}) must be less than rpm_max ({self.rpm_max})"
            )
        if self.rpm_min <= 0:
            raise ValueError(f"Spindle rpm_min must be positive, got {self.rpm_min}")


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
    "Wasteboard2D",
    "MachineDefaults",
    "MachineConfig",
    "Endmill",
    "Spindle",
    "load_cnc_machine",
    "load_endmills",
    "load_spindles",
    "get_machines_dir",
    "list_available_machines",
    "load_machine_by_name",
]
