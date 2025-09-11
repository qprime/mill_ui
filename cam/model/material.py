
from dataclasses import dataclass
@dataclass(frozen=True)
class Material:
    name:str='MDF'; chipload_min:float=0.02; chipload_max:float=0.08
