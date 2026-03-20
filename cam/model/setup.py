from dataclasses import dataclass

from cam.model.machine import Machine
from cam.model.stock import Stock
from cam.model.tool import Tool


@dataclass(frozen=True)
class Setup:
    stock: Stock
    tool: Tool
    machine: Machine
    safe_z: float = 5.0
    ramp_angle_deg: float = 3.0
