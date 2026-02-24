from __future__ import annotations

from pathlib import Path

from layout_ast.compositional import (
    CompositionalLayoutAST,
    TemplateDef,
)
from layout_ast.layout import Item, Sheet
from pml.yaml_parser import parse_template_yaml, substitute_params
from resolution.layout_resolver import LayoutResolver

TEMPLATE_SEARCH_PATHS = [
    Path(__file__).parent,
]

_template_cache: dict[str, tuple[TemplateDef, str]] = {}


def find_template_file(name: str) -> Path | None:
    filename = f"{name.lower()}.pml.yml"
    for search_path in TEMPLATE_SEARCH_PATHS:
        candidate = search_path / filename
        if candidate.exists():
            return candidate
    return None


def load_pml_template(name: str) -> tuple[TemplateDef, str]:
    if name in _template_cache:
        return _template_cache[name]

    path = find_template_file(name)
    if path is None:
        raise ValueError(f"Template not found: {name}")

    text = path.read_text()
    template_def = parse_template_yaml(text)
    _template_cache[name] = (template_def, text)
    return template_def, text


def expand_template(
    template_name: str,
    params: dict[str, float],
    region_width: float,
    region_height: float,
    sheet_thickness: float,
) -> list[Item]:
    template_def, raw_text = load_pml_template(template_name)

    resolved_params = {**template_def.params, **params}
    resolved_params["outer_w"] = region_width
    resolved_params["outer_h"] = region_height

    substituted_text = substitute_params(raw_text, resolved_params)
    substituted_def = parse_template_yaml(substituted_text, parse_body=True)

    if substituted_def.body is None:
        return []

    synthetic_sheet = Sheet(
        width_mm=region_width,
        height_mm=region_height,
        thickness_mm=sheet_thickness,
        margin_mm=0.0,
    )

    synthetic_ast = CompositionalLayoutAST(
        sheet=synthetic_sheet,
        components={},
        root=substituted_def.body,
    )

    resolver = LayoutResolver(synthetic_ast)
    resolved_ast = resolver.resolve()

    return list(resolved_ast.items)


def clear_template_cache() -> None:
    _template_cache.clear()


__all__ = [
    "clear_template_cache",
    "expand_template",
    "find_template_file",
    "load_pml_template",
]
