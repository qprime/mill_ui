from dataclasses import dataclass


@dataclass(frozen=True)
class Stock:
    width: float
    height: float
    thickness: float
    origin: str = "lower_left_top"
