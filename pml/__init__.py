from .compositional_parser import parse_compositional_pml, ParseError as PMLParseError
from .formatter import format_pml
from resolution.layout_resolver import resolve_layout


def parse_pml(text: str):
    comp_ast = parse_compositional_pml(text)
    return resolve_layout(comp_ast)


__all__ = ["parse_pml", "parse_compositional_pml", "format_pml", "PMLParseError"]
