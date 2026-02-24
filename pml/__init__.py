from layout_ast.compositional import CompositionalLayoutAST
from layout_ast.layout import LayoutAST
from resolution.layout_resolver import resolve_layout

from .formatter import format_pml as format_flat_pml
from .yaml_formatter import format_pml_yaml
from .yaml_parser import PMLParseError, parse_pml_yaml


def parse_compositional_pml(text: str):
    return parse_pml_yaml(text)


def parse_pml(text: str):
    comp_ast = parse_pml_yaml(text)
    return resolve_layout(comp_ast)


def format_pml(ast) -> str:
    if isinstance(ast, LayoutAST):
        return format_flat_pml(ast)
    elif isinstance(ast, CompositionalLayoutAST):
        return format_pml_yaml(ast)
    else:
        raise TypeError(f"Expected LayoutAST or CompositionalLayoutAST, got {type(ast)}")


__all__ = ["PMLParseError", "format_pml", "format_pml_yaml", "parse_compositional_pml", "parse_pml", "parse_pml_yaml"]
