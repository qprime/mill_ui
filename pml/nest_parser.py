
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any


@dataclass
class NestPart:
    name: str
    width_mm: float
    height_mm: float
    quantity: int = 1
    template: str | None = None
    template_params: dict[str, float] = field(default_factory=dict)


@dataclass
class NestJob:
    algorithm: str
    sheet_width_mm: float
    sheet_height_mm: float
    sheet_thickness_mm: float
    kerf_mm: float = 6.35
    margin_mm: float = 10.0
    parts: list[NestPart] = field(default_factory=list)


class NestParseError(Exception):
    def __init__(self, message: str, line: int = 0):
        self.message = message
        self.line = line
        super().__init__(f"Line {line}: {message}" if line else message)


def parse_nest_pml(source: str) -> NestJob:
    lines = source.split('\n')


    algorithm: str | None = None
    sheet_width: float | None = None
    sheet_height: float | None = None
    sheet_thickness: float | None = None
    kerf_mm: float = 6.35
    margin_mm: float = 10.0
    parts: list[NestPart] = []


    current_part: NestPart | None = None
    in_template: bool = False
    in_parts_block: bool = False


    base_indent = 0

    for line_num, line in enumerate(lines, 1):

        stripped = line.strip()
        if not stripped or stripped.startswith('#'):
            continue


        indent = len(line) - len(line.lstrip())


        if stripped.startswith('nest '):
            match = re.match(r'nest\s+(\w+)', stripped)
            if match:
                algorithm = match.group(1)
                base_indent = indent
                continue
            else:
                raise NestParseError(f"Invalid nest directive: {stripped}", line_num)


        if algorithm is None:
            raise NestParseError("Expected 'nest <algorithm>' directive", line_num)


        if stripped.startswith('sheet '):
            match = re.match(r'sheet\s+([\d.]+)mm\s+([\d.]+)mm\s+([\d.]+)mm', stripped)
            if match:
                sheet_width = float(match.group(1))
                sheet_height = float(match.group(2))
                sheet_thickness = float(match.group(3))
                continue
            else:
                raise NestParseError(f"Invalid sheet directive: {stripped}", line_num)


        if stripped.startswith('kerf '):
            match = re.match(r'kerf\s+([\d.]+)mm', stripped)
            if match:
                kerf_mm = float(match.group(1))
                continue
            else:
                raise NestParseError(f"Invalid kerf directive: {stripped}", line_num)


        if stripped.startswith('margin '):
            match = re.match(r'margin\s+([\d.]+)mm', stripped)
            if match:
                margin_mm = float(match.group(1))
                continue
            else:
                raise NestParseError(f"Invalid margin directive: {stripped}", line_num)


        if stripped == 'parts':
            in_parts_block = True
            continue


        if in_parts_block:


            part_match = re.match(r'(\w+)\s+([\d.]+)mm\s+([\d.]+)mm(?:\s+x(\d+))?$', stripped)
            if part_match:

                if current_part is not None:
                    parts.append(current_part)

                name = part_match.group(1)
                width = float(part_match.group(2))
                height = float(part_match.group(3))
                quantity = int(part_match.group(4)) if part_match.group(4) else 1

                current_part = NestPart(
                    name=name,
                    width_mm=width,
                    height_mm=height,
                    quantity=quantity,
                )
                in_template = False
                continue


            if stripped.startswith('template '):
                if current_part is None:
                    raise NestParseError("Template outside of part definition", line_num)
                match = re.match(r'template\s+(\w+)', stripped)
                if match:
                    current_part.template = match.group(1)
                    in_template = True
                    continue
                else:
                    raise NestParseError(f"Invalid template directive: {stripped}", line_num)


            if in_template and current_part is not None:


                match = re.match(r'(\w+)\s+([\d.]+)(?:mm)?$', stripped)
                if match:
                    param_name = match.group(1)
                    param_value = float(match.group(2))
                    current_part.template_params[param_name] = param_value
                    continue


            in_template = False


    if current_part is not None:
        parts.append(current_part)


    if algorithm is None:
        raise NestParseError("Missing 'nest <algorithm>' directive")
    if sheet_width is None or sheet_height is None or sheet_thickness is None:
        raise NestParseError("Missing 'sheet' directive")
    if not parts:
        raise NestParseError("No parts defined")

    return NestJob(
        algorithm=algorithm,
        sheet_width_mm=sheet_width,
        sheet_height_mm=sheet_height,
        sheet_thickness_mm=sheet_thickness,
        kerf_mm=kerf_mm,
        margin_mm=margin_mm,
        parts=parts,
    )


def nest_job_to_api_params(job: NestJob) -> dict[str, Any]:
    parts = []
    for part in job.parts:
        part_dict: dict[str, Any] = {
            "name": part.name,
            "width_mm": part.width_mm,
            "height_mm": part.height_mm,
            "quantity": part.quantity,
        }
        if part.template:
            part_dict["template"] = part.template
            part_dict["template_params"] = part.template_params
        parts.append(part_dict)

    return {
        "parts": parts,
        "sheet_width_mm": job.sheet_width_mm,
        "sheet_height_mm": job.sheet_height_mm,
        "sheet_thickness_mm": job.sheet_thickness_mm,
        "kerf_mm": job.kerf_mm,
        "margin_mm": job.margin_mm,
        "algorithm": job.algorithm,
    }


__all__ = [
    "NestPart",
    "NestJob",
    "NestParseError",
    "parse_nest_pml",
    "nest_job_to_api_params",
]
