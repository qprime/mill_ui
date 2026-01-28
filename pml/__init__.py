from .yaml_parser import parse_pml_yaml, PMLParseError
from .yaml_formatter import format_pml_yaml
from .formatter import format_pml as format_flat_pml
from resolution.layout_resolver import resolve_layout
from layout_ast.layout import LayoutAST
from layout_ast.compositional import CompositionalLayoutAST


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


__all__ = ["parse_pml", "parse_compositional_pml", "format_pml", "PMLParseError", "parse_pml_yaml", "format_pml_yaml"]
