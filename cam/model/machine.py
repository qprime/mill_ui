from dataclasses import dataclass
from typing import Sequence


@dataclass(frozen=True)
class Machine:
    name: str = 'default_grbl'
    max_feed_xy: float = 3000.0
    max_feed_z: float = 800.0
    rapid_z: float = 1000.0
    work_coord_system: str = 'G54'
    spindle_dwell_s: float = 5.0
    preamble_codes: Sequence[str] = ()

    def build_header(
        self,
        *,
        unit: str = 'mm',
        safe_z: float = 6.0,
        prec: int = 3,
        first_rpm: float | None = None,
    ) -> list[str]:
        header = ['(begin)', 'G90', 'G20' if unit == 'inch' else 'G21', 'G17', 'G94']
        if self.work_coord_system:
            header.append(self.work_coord_system)
        for code in self.preamble_codes:
            header.append(code)
        header.append(f'G0 Z{safe_z:.{prec}f}')
        if first_rpm is not None:
            header.append(f'M3 S{int(round(first_rpm))}')
            if self.spindle_dwell_s > 0:
                header.append(f'G4 P{int(round(self.spindle_dwell_s))}')
        return header
