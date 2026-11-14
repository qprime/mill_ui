from resolution.layout_resolver import resolve_layout

from .yaml_formatter import format_pml_yaml
from .yaml_parser import PMLParseError, parse_pml_yaml


def parse_compositional_pml(text: str):
    return parse_pml_yaml(text)


def parse_pml(text: str):
    comp_ast = parse_pml_yaml(text)
    return resolve_layout(comp_ast)


def format_pml(ast) -> str:
    return format_pml_yaml(ast)


__all__ = ["PMLParseError", "format_pml", "format_pml_yaml", "parse_compositional_pml", "parse_pml", "parse_pml_yaml"]
