
from dataclasses import dataclass
from skills.mill_ui.cam.model.tool import Tool
from skills.mill_ui.cam.model.material import Material
from skills.mill_ui.cam.model.machine import Machine
from skills.mill_ui.cam.model.stock import Stock
@dataclass(frozen=True)
class Setup:
    stock:Stock; tool:Tool; material:Material; machine:Machine; safe_z:float=5.0
