
from dataclasses import dataclass
@dataclass(frozen=True)
class Machine:
    name:str='default_grbl'; max_feed_xy:float=3000.0; max_feed_z:float=800.0; rapid_z:float=1000.0
