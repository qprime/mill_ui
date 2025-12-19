
from dataclasses import dataclass
from cam.model.tool import Tool
from cam.model.material import Material
from cam.model.machine import Machine
from cam.model.stock import Stock
@dataclass(frozen=True)
class Setup:
    stock:Stock; tool:Tool; material:Material; machine:Machine; safe_z:float=5.0
