
from dataclasses import dataclass
@dataclass(frozen=True)
class Panel:
    width: float; height: float; thickness: float; safe_z: float=5.0
