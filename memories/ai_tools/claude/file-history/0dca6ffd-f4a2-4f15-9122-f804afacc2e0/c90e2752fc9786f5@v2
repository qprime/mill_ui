"""Compositional PML parser: indentation-based syntax → CompositionalAST.

This parser compiles human-authored compositional PML into the CompositionalAST
defined in Stage 12. It supports hierarchical, region-relative layouts without
explicit XY coordinates.

Supported constructs:
- sheet / project (top-level metadata)
- component / use (component definition and instantiation)
- place (sheet-level multi-instance placement)
- panel / rect / inset / frame / grid / cell (layout nodes)
- Feature labels: pocket, profile, engrave, hole, edge

Explicitly NOT supported:
- Arithmetic expressions
- Conditionals or control flow
- Variables or bindings
- Imports with side effects

Error handling:
- Line/column tracking for all parse errors
- Clear error messages with expected tokens
- Strict indentation validation
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from skills.mill_ui.v2.ast.compositional import (
    Panel,
    Inset,
    Frame,
    Grid,
    Cell,
    ComponentDef,
    UseComponent,
    Place,
    Rect,
    CompositionalLayoutAST,
)
from skills.mill_ui.v2.ast.layout import Sheet, Feature


@dataclass
class Token:
    """Lexical token with position tracking."""
    type: str  # keyword, identifier, number, unit, newline, indent, dedent, eof
    value: Any
    line: int
    column: int


@dataclass
class ParseError(Exception):
    """Parse error with line/column information."""
    message: str
    line: int
    column: int

    def __str__(self) -> str:
        return f"Parse error at line {self.line}, column {self.column}: {self.message}"


class CompositionalPMLLexer:
    """Lexer for compositional PML with indentation tracking."""

    def __init__(self, text: str):
        self.text = text
        self.pos = 0
        self.line = 1
        self.column = 1
        self.indent_stack = [0]  # Stack of indentation levels

    def peek(self, offset: int = 0) -> str | None:
        """Peek at character at current position + offset."""
        pos = self.pos + offset
        return self.text[pos] if pos < len(self.text) else None

    def advance(self) -> str | None:
        """Consume and return current character."""
        if self.pos >= len(self.text):
            return None
        char = self.text[self.pos]
        self.pos += 1
        if char == '\n':
            self.line += 1
            self.column = 1
        else:
            self.column += 1
        return char

    def skip_whitespace(self, skip_newlines: bool = False) -> None:
        """Skip whitespace (excluding newlines unless skip_newlines=True)."""
        while self.peek() and self.peek() in (' ', '\t', '\r'):
            self.advance()
        if skip_newlines:
            while self.peek() == '\n':
                self.advance()

    def skip_comment(self) -> None:
        """Skip comment line (# to end of line)."""
        if self.peek() == '#':
            while self.peek() and self.peek() != '\n':
                self.advance()

    def lex_number(self) -> Token:
        """Lex a number (integer or float)."""
        start_line = self.line
        start_col = self.column
        num_str = ""
        while self.peek() and (self.peek().isdigit() or self.peek() == '.'):
            num_str += self.advance()

        # Check for unit suffix (mm)
        if self.peek() == 'm' and self.peek(1) == 'm':
            self.advance()
            self.advance()
            return Token('number_with_unit', float(num_str), start_line, start_col)

        value = float(num_str) if '.' in num_str else int(num_str)
        return Token('number', value, start_line, start_col)

    def lex_identifier(self) -> Token:
        """Lex an identifier or keyword."""
        start_line = self.line
        start_col = self.column
        ident = ""
        while self.peek() and (self.peek().isalnum() or self.peek() in ('_', '-')):
            ident += self.advance()

        # Check if it's a keyword
        keywords = {
            'sheet', 'project', 'component', 'use', 'place',
            'rect', 'inset', 'frame', 'grid', 'cell', 'gap',
            'pocket', 'profile', 'engrave', 'hole', 'edge',
            'through', 'inside', 'outside', 'on',
        }

        token_type = 'keyword' if ident in keywords else 'identifier'
        return Token(token_type, ident, start_line, start_col)

    def tokenize(self) -> list[Token]:
        """Tokenize the entire input with indentation tracking."""
        tokens = []
        at_line_start = True

        while self.pos < len(self.text):
            # Handle line start (check indentation)
            if at_line_start:
                # Count leading spaces
                indent_level = 0
                while self.peek() == ' ':
                    indent_level += 1
                    self.advance()

                # Skip empty lines and comments
                if self.peek() in ('\n', '\r', None) or self.peek() == '#':
                    self.skip_comment()
                    if self.peek() == '\n':
                        self.advance()
                    continue

                # Emit indent/dedent tokens
                current_indent = self.indent_stack[-1]
                if indent_level > current_indent:
                    self.indent_stack.append(indent_level)
                    tokens.append(Token('indent', indent_level, self.line, self.column))
                elif indent_level < current_indent:
                    while self.indent_stack and self.indent_stack[-1] > indent_level:
                        self.indent_stack.pop()
                        tokens.append(Token('dedent', indent_level, self.line, self.column))
                    if not self.indent_stack or self.indent_stack[-1] != indent_level:
                        raise ParseError(f"Invalid indentation level {indent_level}", self.line, self.column)

                at_line_start = False

            # Skip inline whitespace
            self.skip_whitespace(skip_newlines=False)

            if self.pos >= len(self.text):
                break

            char = self.peek()

            # Newline
            if char == '\n':
                tokens.append(Token('newline', '\n', self.line, self.column))
                self.advance()
                at_line_start = True
                continue

            # Comment
            if char == '#':
                self.skip_comment()
                continue

            # Number
            if char.isdigit():
                tokens.append(self.lex_number())
                continue

            # Identifier or keyword
            if char.isalpha() or char == '_':
                tokens.append(self.lex_identifier())
                continue

            # Unknown character
            raise ParseError(f"Unexpected character: {char}", self.line, self.column)

        # Emit final dedents
        while len(self.indent_stack) > 1:
            self.indent_stack.pop()
            tokens.append(Token('dedent', 0, self.line, self.column))

        tokens.append(Token('eof', None, self.line, self.column))
        return tokens


class CompositionalPMLParser:
    """Parser for compositional PML."""

    def __init__(self, tokens: list[Token]):
        self.tokens = tokens
        self.pos = 0

    def peek(self, offset: int = 0) -> Token:
        """Peek at token at current position + offset."""
        pos = self.pos + offset
        return self.tokens[pos] if pos < len(self.tokens) else self.tokens[-1]

    def advance(self) -> Token:
        """Consume and return current token."""
        token = self.peek()
        if token.type != 'eof':
            self.pos += 1
        return token

    def expect(self, token_type: str, value: Any = None) -> Token:
        """Expect a specific token type and optionally value."""
        token = self.advance()
        if token.type != token_type:
            raise ParseError(f"Expected {token_type}, got {token.type}", token.line, token.column)
        if value is not None and token.value != value:
            raise ParseError(f"Expected {value}, got {token.value}", token.line, token.column)
        return token

    def expect_line_end(self) -> None:
        """Expect line end (newline or dedent)."""
        token = self.peek()
        if token.type == 'newline':
            self.advance()
        elif token.type == 'dedent':
            # Dedent implies line end; don't consume it
            pass
        elif token.type == 'eof':
            # EOF implies line end
            pass
        else:
            raise ParseError(f"Expected end of line, got {token.type}", token.line, token.column)

    def skip_newlines(self) -> None:
        """Skip any newline tokens."""
        while self.peek().type == 'newline':
            self.advance()

    def parse(self) -> CompositionalLayoutAST:
        """Parse top-level compositional PML into CompositionalAST."""
        self.skip_newlines()

        # Parse sheet declaration (required)
        sheet = self.parse_sheet()
        self.skip_newlines()

        # Parse optional project declaration
        project = None
        if self.peek().type == 'keyword' and self.peek().value == 'project':
            project = self.parse_project()
            self.skip_newlines()

        # Parse component definitions
        components = {}
        while self.peek().type == 'keyword' and self.peek().value == 'component':
            comp_def = self.parse_component_def()
            components[comp_def.name] = comp_def
            self.skip_newlines()

        # Parse root layout (place or panel)
        if self.peek().type == 'keyword' and self.peek().value == 'place':
            root = self.parse_place()
        else:
            # Default to panel if no explicit place
            root = self.parse_panel_or_children()

        return CompositionalLayoutAST(
            sheet=sheet,
            components=components,
            root=root,
            project=project,
        )

    def parse_sheet(self) -> Sheet:
        """Parse sheet declaration: sheet <width>mm <height>mm <thickness>mm"""
        self.expect('keyword', 'sheet')
        width = self.expect('number_with_unit').value
        height = self.expect('number_with_unit').value
        thickness = self.expect('number_with_unit').value
        self.expect_line_end()
        return Sheet(width_mm=width, height_mm=height, thickness_mm=thickness)

    def parse_project(self) -> str:
        """Parse project declaration: project <name>"""
        self.expect('keyword', 'project')
        name = self.expect('identifier').value
        self.expect_line_end()
        return name

    def parse_component_def(self) -> ComponentDef:
        """Parse component definition:
        component <name>
            <body>
        """
        self.expect('keyword', 'component')
        name = self.expect('identifier').value
        self.expect_line_end()
        self.expect('indent')

        # Parse component body (single node)
        body = self.parse_node()

        self.skip_newlines()
        self.expect('dedent')

        return ComponentDef(name=name, params={}, body=body)

    def parse_place(self) -> Place:
        """Parse place statement:
        place grid <rows> <cols> gap <gap>mm
            use <component>
            ...
        """
        self.expect('keyword', 'place')
        self.expect('keyword', 'grid')
        rows = self.expect('number').value
        cols = self.expect('number').value
        self.expect('keyword', 'gap')
        gap_mm = self.expect('number_with_unit').value
        self.expect_line_end()
        self.expect('indent')

        # Parse children (use statements)
        children = []
        while self.peek().type == 'keyword' and self.peek().value == 'use':
            children.append(self.parse_use_component())
            self.skip_newlines()

        self.expect('dedent')

        layout = Grid(rows=rows, cols=cols, gap_mm=gap_mm)
        return Place(layout=layout, children=tuple(children))

    def parse_use_component(self) -> UseComponent:
        """Parse use statement: use <component_name>"""
        self.expect('keyword', 'use')
        name = self.expect('identifier').value
        self.expect_line_end()
        return UseComponent(component_name=name, args={})

    def parse_panel_or_children(self) -> Panel:
        """Parse implicit panel with children."""
        children = []
        while self.peek().type != 'eof' and self.peek().type != 'dedent':
            children.append(self.parse_node())
            self.skip_newlines()
        return Panel(children=tuple(children))

    def parse_node(self) -> Any:
        """Parse a layout node (rect, inset, frame, grid, cell, use)."""
        token = self.peek()
        if token.type != 'keyword':
            raise ParseError(f"Expected layout node keyword, got {token.type}", token.line, token.column)

        if token.value == 'rect':
            return self.parse_rect()
        elif token.value == 'inset':
            return self.parse_inset()
        elif token.value == 'frame':
            return self.parse_frame()
        elif token.value == 'grid':
            return self.parse_grid()
        elif token.value == 'cell':
            return self.parse_cell()
        elif token.value == 'use':
            return self.parse_use_component()
        else:
            raise ParseError(f"Unknown layout node: {token.value}", token.line, token.column)

    def parse_rect(self) -> Rect:
        """Parse rect:
        rect [id] [feature]
            <children>
        """
        self.expect('keyword', 'rect')

        # Parse optional id
        rect_id = None
        if self.peek().type == 'identifier':
            rect_id = self.advance().value

        # Parse optional feature
        feature = None
        if self.peek().type == 'keyword' and self.peek().value in ('pocket', 'profile', 'engrave', 'hole', 'edge'):
            feature = self.parse_feature()

        self.expect_line_end()

        # Parse optional children
        children = []
        if self.peek().type == 'indent':
            self.expect('indent')
            while self.peek().type != 'dedent':
                children.append(self.parse_node())
                self.skip_newlines()
            self.expect('dedent')

        return Rect(children=tuple(children), feature=feature, id=rect_id)

    def parse_feature(self) -> Feature:
        """Parse feature: pocket <depth>mm | profile through <side> | ..."""
        feature_type = self.expect('keyword').value

        if feature_type == 'pocket':
            depth = self.expect('number_with_unit').value
            return Feature(type='pocket', depth=str(depth), depth_mm=depth)
        elif feature_type == 'profile':
            depth = self.expect('keyword', 'through').value
            side = self.expect('keyword').value  # inside, outside, on
            return Feature(type='profile', depth=depth, side=side)
        elif feature_type in ('engrave', 'hole', 'edge'):
            # Simple feature types (extend as needed)
            return Feature(type=feature_type, depth='through')
        else:
            raise ParseError(f"Unknown feature type: {feature_type}", self.peek().line, self.peek().column)

    def parse_inset(self) -> Inset:
        """Parse inset: inset <amount>mm"""
        self.expect('keyword', 'inset')
        amount = self.expect('number_with_unit').value
        self.expect_line_end()
        self.expect('indent')

        children = []
        while self.peek().type != 'dedent':
            children.append(self.parse_node())
            self.skip_newlines()
        self.expect('dedent')

        return Inset(amount_mm=amount, children=tuple(children))

    def parse_frame(self) -> Frame:
        """Parse frame: frame <width>mm"""
        self.expect('keyword', 'frame')
        width = self.expect('number_with_unit').value
        self.expect_line_end()
        self.expect('indent')

        children = []
        while self.peek().type != 'dedent':
            children.append(self.parse_node())
            self.skip_newlines()
        self.expect('dedent')

        return Frame(width_mm=width, children=tuple(children))

    def parse_grid(self) -> Grid:
        """Parse grid: grid <rows> <cols> gap <gap>mm"""
        self.expect('keyword', 'grid')
        rows = self.expect('number').value
        cols = self.expect('number').value
        self.expect('keyword', 'gap')
        gap_mm = self.expect('number_with_unit').value
        self.expect_line_end()
        self.expect('indent')

        children = []
        while self.peek().type != 'dedent':
            children.append(self.parse_node())
            self.skip_newlines()
        self.expect('dedent')

        return Grid(rows=rows, cols=cols, gap_mm=gap_mm, children=tuple(children))

    def parse_cell(self) -> Cell:
        """Parse cell: cell"""
        self.expect('keyword', 'cell')
        self.expect_line_end()
        self.expect('indent')

        children = []
        while self.peek().type != 'dedent':
            children.append(self.parse_node())
            self.skip_newlines()
        self.expect('dedent')

        return Cell(children=tuple(children))


def parse_compositional_pml(text: str) -> CompositionalLayoutAST:
    """Parse compositional PML text into CompositionalAST.

    Args:
        text: Compositional PML source text

    Returns:
        CompositionalLayoutAST instance

    Raises:
        ParseError: On syntax error with line/column information
    """
    lexer = CompositionalPMLLexer(text)
    tokens = lexer.tokenize()
    parser = CompositionalPMLParser(tokens)
    return parser.parse()
