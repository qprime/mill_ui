
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from layout_ast.compositional import (
    Panel,
    Inset,
    Frame,
    Grid,
    Cell,
    Split,
    ComponentDef,
    UseComponent,
    Place,
    Rect,
    Circle,
    RoundedRect,
    Line,
    Polyline,
    SplinePath,
    Keepout,
    Edge,
    CompositionalLayoutAST,
)
from layout_ast.layout import Sheet, Feature


@dataclass
class Token:
    type: str
    value: Any
    line: int
    column: int


@dataclass
class ParseError(Exception):
    message: str
    line: int
    column: int

    def __str__(self) -> str:
        return f"Parse error at line {self.line}, column {self.column}: {self.message}"


class CompositionalPMLLexer:

    def __init__(self, text: str):
        self.text = text
        self.pos = 0
        self.line = 1
        self.column = 1
        self.indent_stack = [0]

    def peek(self, offset: int = 0) -> str | None:
        pos = self.pos + offset
        return self.text[pos] if pos < len(self.text) else None

    def advance(self) -> str | None:
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
        while self.peek() and self.peek() in (' ', '\t', '\r'):
            self.advance()
        if skip_newlines:
            while self.peek() == '\n':
                self.advance()

    def skip_comment(self) -> None:
        if self.peek() == '#':
            while self.peek() and self.peek() != '\n':
                self.advance()

    def lex_number(self) -> Token:
        start_line = self.line
        start_col = self.column
        num_str = ""
        while self.peek() and (self.peek().isdigit() or self.peek() == '.'):
            num_str += self.advance()


        if self.peek() == 'm' and self.peek(1) == 'm':
            self.advance()
            self.advance()
            return Token('number_with_unit', float(num_str), start_line, start_col)

        value = float(num_str) if '.' in num_str else int(num_str)
        return Token('number', value, start_line, start_col)

    def lex_identifier(self) -> Token:
        start_line = self.line
        start_col = self.column
        ident = ""
        while self.peek() and (self.peek().isalnum() or self.peek() in ('_', '-')):
            ident += self.advance()


        keywords = {
            'sheet', 'project', 'component', 'use', 'place',
            'rect', 'circle', 'rounded_rect', 'line', 'polyline', 'spline', 'keepout', 'inset', 'frame', 'grid', 'split', 'cell', 'gap', 'rail', 'mullion', 'points', 'tolerance',
            'pocket', 'profile', 'engrave', 'hole', 'edge',
            'through', 'inside', 'outside', 'on',
            'diameter', 'radius', 'fit', 'horizontal', 'vertical',
            'allowance', 'fillet', 'chamfer',
        }

        token_type = 'keyword' if ident in keywords else 'identifier'
        return Token(token_type, ident, start_line, start_col)

    def tokenize(self) -> list[Token]:
        tokens = []
        at_line_start = True

        while self.pos < len(self.text):

            if at_line_start:

                indent_level = 0
                while self.peek() == ' ':
                    indent_level += 1
                    self.advance()


                if self.peek() in ('\n', '\r', None) or self.peek() == '#':
                    self.skip_comment()
                    if self.peek() == '\n':
                        self.advance()
                    continue


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


            self.skip_whitespace(skip_newlines=False)

            if self.pos >= len(self.text):
                break

            char = self.peek()


            if char == '\n':
                tokens.append(Token('newline', '\n', self.line, self.column))
                self.advance()
                at_line_start = True
                continue


            if char == '#':
                self.skip_comment()
                continue


            if char.isdigit() or (char == '-' and self.peek(1) and self.peek(1).isdigit()):

                if char == '-':
                    start_line = self.line
                    start_col = self.column
                    self.advance()
                    num_token = self.lex_number()

                    num_token = Token(num_token.type, -num_token.value, start_line, start_col)
                    tokens.append(num_token)
                else:
                    tokens.append(self.lex_number())
                continue


            if char.isalpha() or char == '_':
                tokens.append(self.lex_identifier())
                continue


            if char in ('(', ')', ','):
                tokens.append(Token('punctuation', char, self.line, self.column))
                self.advance()
                continue


            raise ParseError(f"Unexpected character: {char}", self.line, self.column)


        while len(self.indent_stack) > 1:
            self.indent_stack.pop()
            tokens.append(Token('dedent', 0, self.line, self.column))

        tokens.append(Token('eof', None, self.line, self.column))
        return tokens


class CompositionalPMLParser:

    def __init__(self, tokens: list[Token]):
        self.tokens = tokens
        self.pos = 0
        self.in_keepout = False

    def peek(self, offset: int = 0) -> Token:
        pos = self.pos + offset
        return self.tokens[pos] if pos < len(self.tokens) else self.tokens[-1]

    def advance(self) -> Token:
        token = self.peek()
        if token.type != 'eof':
            self.pos += 1
        return token

    def expect(self, token_type: str, value: Any = None) -> Token:
        token = self.advance()
        if token.type != token_type:
            raise ParseError(f"Expected {token_type}, got {token.type}", token.line, token.column)
        if value is not None and token.value != value:
            raise ParseError(f"Expected {value}, got {token.value}", token.line, token.column)
        return token

    def expect_line_end(self) -> None:
        token = self.peek()
        if token.type == 'newline':
            self.advance()
        elif token.type == 'dedent':

            pass
        elif token.type == 'eof':

            pass
        else:
            raise ParseError(f"Expected end of line, got {token.type}", token.line, token.column)

    def skip_newlines(self) -> None:
        while self.peek().type == 'newline':
            self.advance()

    def parse(self) -> CompositionalLayoutAST:
        self.skip_newlines()


        sheet = self.parse_sheet()
        self.skip_newlines()


        project = None
        if self.peek().type == 'keyword' and self.peek().value == 'project':
            project = self.parse_project()
            self.skip_newlines()


        components = {}
        while self.peek().type == 'keyword' and self.peek().value == 'component':
            comp_def = self.parse_component_def()
            components[comp_def.name] = comp_def
            self.skip_newlines()


        if self.peek().type == 'keyword' and self.peek().value == 'place':
            root = self.parse_place()
        else:

            root = self.parse_panel_or_children()

        return CompositionalLayoutAST(
            sheet=sheet,
            components=components,
            root=root,
            project=project,
        )

    def parse_sheet(self) -> Sheet:
        self.expect('keyword', 'sheet')
        width = self.expect('number_with_unit').value
        height = self.expect('number_with_unit').value
        thickness = self.expect('number_with_unit').value
        self.expect_line_end()
        return Sheet(width_mm=width, height_mm=height, thickness_mm=thickness)

    def parse_project(self) -> str:
        self.expect('keyword', 'project')
        name = self.expect('identifier').value
        self.expect_line_end()
        return name

    def parse_component_def(self) -> ComponentDef:
        self.expect('keyword', 'component')
        name = self.expect('identifier').value
        self.expect_line_end()
        self.expect('indent')


        body = self.parse_node()

        self.skip_newlines()
        self.expect('dedent')

        return ComponentDef(name=name, params={}, body=body)

    def parse_place(self) -> Place:
        self.expect('keyword', 'place')
        self.expect('keyword', 'grid')
        rows = self.expect('number').value
        cols = self.expect('number').value
        self.expect('keyword', 'gap')
        gap_mm = self.expect('number_with_unit').value
        self.expect_line_end()
        self.expect('indent')


        children = []
        while self.peek().type == 'keyword' and self.peek().value == 'use':
            children.append(self.parse_use_component())
            self.skip_newlines()

        self.expect('dedent')

        layout = Grid(rows=rows, cols=cols, gap_mm=gap_mm)
        return Place(layout=layout, children=tuple(children))

    def parse_use_component(self) -> UseComponent:
        self.expect('keyword', 'use')
        name = self.expect('identifier').value
        self.expect_line_end()
        return UseComponent(component_name=name, args={})

    def parse_panel_or_children(self) -> Panel:
        children = []
        while self.peek().type != 'eof' and self.peek().type != 'dedent':
            children.append(self.parse_node())
            self.skip_newlines()
        return Panel(children=tuple(children))

    def parse_node(self) -> Any:
        token = self.peek()
        if token.type != 'keyword':
            raise ParseError(f"Expected layout node keyword, got {token.type}", token.line, token.column)

        if token.value == 'rect':
            return self.parse_rect()
        elif token.value == 'circle':
            return self.parse_circle()
        elif token.value == 'rounded_rect':
            return self.parse_rounded_rect()
        elif token.value == 'line':
            return self.parse_line()
        elif token.value == 'polyline':
            return self.parse_polyline()
        elif token.value == 'spline':
            return self.parse_spline()
        elif token.value == 'keepout':
            return self.parse_keepout()
        elif token.value == 'edge':
            return self.parse_edge()
        elif token.value == 'inset':
            return self.parse_inset()
        elif token.value == 'frame':
            return self.parse_frame()
        elif token.value == 'grid':
            return self.parse_grid()
        elif token.value == 'split':
            return self.parse_split()
        elif token.value == 'cell':
            return self.parse_cell()
        elif token.value == 'use':
            return self.parse_use_component()
        else:
            raise ParseError(f"Unknown layout node: {token.value}", token.line, token.column)

    def parse_rect(self) -> Rect:
        self.expect('keyword', 'rect')


        rect_id = None
        if self.peek().type == 'identifier':
            rect_id = self.advance().value


        feature = None
        if self.peek().type == 'keyword' and self.peek().value in ('pocket', 'profile', 'engrave', 'hole', 'edge'):
            feature = self.parse_feature()

        self.expect_line_end()


        children = []
        if self.peek().type == 'indent':
            self.expect('indent')
            while self.peek().type != 'dedent':
                children.append(self.parse_node())
                self.skip_newlines()
            self.expect('dedent')

        return Rect(children=tuple(children), feature=feature, id=rect_id)

    def parse_circle(self) -> Circle:
        self.expect('keyword', 'circle')


        circle_id = None
        if self.peek().type == 'identifier':
            circle_id = self.advance().value


        diameter_mm = None
        if self.peek().type == 'keyword':
            if self.peek().value == 'diameter':
                self.advance()
                diameter_mm = self.expect('number_with_unit').value
            elif self.peek().value == 'fit':
                self.advance()
                diameter_mm = None


        feature = None
        if self.peek().type == 'keyword' and self.peek().value in ('pocket', 'profile', 'engrave', 'hole', 'edge'):
            feature = self.parse_feature()

        self.expect_line_end()


        children = []
        if self.peek().type == 'indent':
            self.expect('indent')
            while self.peek().type != 'dedent':
                children.append(self.parse_node())
                self.skip_newlines()
            self.expect('dedent')

        return Circle(diameter_mm=diameter_mm, children=tuple(children), feature=feature, id=circle_id)

    def parse_rounded_rect(self) -> RoundedRect:
        self.expect('keyword', 'rounded_rect')


        rounded_rect_id = None
        if self.peek().type == 'identifier':
            rounded_rect_id = self.advance().value


        self.expect('keyword', 'radius')
        radius_mm = self.expect('number_with_unit').value


        feature = None
        if self.peek().type == 'keyword' and self.peek().value in ('pocket', 'profile', 'engrave', 'hole', 'edge'):
            feature = self.parse_feature()

        self.expect_line_end()


        children = []
        if self.peek().type == 'indent':
            self.expect('indent')
            while self.peek().type != 'dedent':
                children.append(self.parse_node())
                self.skip_newlines()
            self.expect('dedent')

        return RoundedRect(radius_mm=radius_mm, children=tuple(children), feature=feature, id=rounded_rect_id)

    def parse_line(self) -> Line:
        self.expect('keyword', 'line')


        line_id = None
        if self.peek().type == 'identifier':
            line_id = self.advance().value


        if self.peek().type == 'keyword' and self.peek().value in ('horizontal', 'vertical'):
            orientation = self.advance().value
        else:
            raise ParseError(f"Expected 'horizontal' or 'vertical', got {self.peek().value}",
                           self.peek().line, self.peek().column)


        feature = None
        if self.peek().type == 'keyword' and self.peek().value in ('pocket', 'profile', 'engrave', 'hole', 'edge'):
            feature = self.parse_feature()

        self.expect_line_end()

        return Line(orientation=orientation, feature=feature, id=line_id)

    def parse_polyline(self) -> Polyline:
        self.expect('keyword', 'polyline')


        polyline_id = None
        if self.peek().type == 'identifier':
            polyline_id = self.advance().value


        self.expect('keyword', 'points')


        points = []
        while True:
            token = self.peek()


            if token.type == 'keyword' and token.value in ('pocket', 'profile', 'engrave', 'hole', 'edge'):
                break
            if token.type in ('newline', 'eof'):
                break


            if token.type != 'punctuation' or token.value != '(':
                break
            self.advance()


            x_token = self.expect('number')
            x = x_token.value


            comma_token = self.peek()
            if comma_token.type != 'punctuation' or comma_token.value != ',':
                raise ParseError(f"Expected ',' between coordinates, got {comma_token.value}",
                               comma_token.line, comma_token.column)
            self.advance()


            y_token = self.expect('number')
            y = y_token.value


            close_token = self.peek()
            if close_token.type != 'punctuation' or close_token.value != ')':
                raise ParseError(f"Expected ')' after point, got {close_token.value}",
                               close_token.line, close_token.column)
            self.advance()

            points.append((x, y))

        if len(points) < 2:
            token = self.peek()
            raise ParseError(f"Polyline requires at least 2 points, got {len(points)}",
                           token.line, token.column)


        feature = None
        if self.peek().type == 'keyword' and self.peek().value in ('pocket', 'profile', 'engrave', 'hole', 'edge'):
            feature = self.parse_feature()

        self.expect_line_end()

        return Polyline(points=tuple(points), feature=feature, id=polyline_id)

    def parse_spline(self) -> SplinePath:
        self.expect('keyword', 'spline')


        spline_id = None
        if self.peek().type == 'identifier':
            spline_id = self.advance().value


        feature = None
        if self.peek().type == 'keyword' and self.peek().value in ('engrave', 'pocket', 'profile', 'hole'):
            feature = self.parse_feature()


        self.expect('keyword', 'points')


        points = []
        while True:
            token = self.peek()


            if token.type == 'keyword' and token.value == 'tolerance':
                break
            if token.type in ('newline', 'eof'):
                break


            if token.type != 'punctuation' or token.value != '(':
                break
            self.advance()


            x_token = self.expect('number')
            x = x_token.value


            comma_token = self.peek()
            if comma_token.type != 'punctuation' or comma_token.value != ',':
                raise ParseError(f"Expected ',' between coordinates, got {comma_token.value}",
                               comma_token.line, comma_token.column)
            self.advance()


            y_token = self.expect('number')
            y = y_token.value


            close_token = self.peek()
            if close_token.type != 'punctuation' or close_token.value != ')':
                raise ParseError(f"Expected ')' after point, got {close_token.value}",
                               close_token.line, close_token.column)
            self.advance()

            points.append((x, y))

        if len(points) < 2:
            token = self.peek()
            raise ParseError(f"SplinePath requires at least 2 control points, got {len(points)}",
                           token.line, token.column)


        tolerance_mm = 0.1
        if self.peek().type == 'keyword' and self.peek().value == 'tolerance':
            self.advance()
            tol_token = self.peek()
            if tol_token.type not in ('number', 'number_with_unit'):
                raise ParseError(f"Expected tolerance value (mm), got {tol_token.type}",
                               tol_token.line, tol_token.column)
            tolerance_mm = float(self.advance().value)

        self.expect_line_end()

        return SplinePath(points=tuple(points), feature=feature, tolerance_mm=tolerance_mm, id=spline_id)

    def parse_keepout(self) -> Keepout:
        token = self.peek()
        self.expect('keyword', 'keepout')


        if self.in_keepout:
            raise ParseError(
                "Nested keepouts are not allowed (keepout inside another keepout)",
                token.line,
                token.column
            )


        keepout_id = None
        if self.peek().type == 'identifier':
            keepout_id = self.advance().value

        self.expect_line_end()


        children = []
        if self.peek().type == 'indent':
            self.advance()


            old_in_keepout = self.in_keepout
            self.in_keepout = True

            try:
                while self.peek().type not in ('dedent', 'eof'):
                    children.append(self.parse_node())
                    self.skip_newlines()
                if self.peek().type == 'dedent':
                    self.advance()
            finally:

                self.in_keepout = old_in_keepout

        return Keepout(children=tuple(children), id=keepout_id)

    def parse_edge(self) -> Edge:
        self.expect('keyword', 'edge')


        if self.peek().type != 'keyword':
            raise ParseError(
                f"Expected edge treatment type (allowance/fillet/chamfer), got {self.peek().type}",
                self.peek().line,
                self.peek().column
            )

        treatment = self.advance().value
        if treatment not in ('allowance', 'fillet', 'chamfer'):
            raise ParseError(
                f"Invalid edge treatment type '{treatment}' (must be allowance, fillet, or chamfer)",
                self.peek().line,
                self.peek().column
            )


        rough_allowance_mm = None
        finish_allowance_mm = None
        radius_mm = None
        distance_mm = None

        if treatment == 'allowance':

            if self.peek().type not in ('number', 'number_with_unit'):
                raise ParseError(
                    f"Expected rough allowance value (mm), got {self.peek().type}",
                    self.peek().line,
                    self.peek().column
                )
            rough_allowance_mm = float(self.advance().value)

            if self.peek().type not in ('number', 'number_with_unit'):
                raise ParseError(
                    f"Expected finish allowance value (mm), got {self.peek().type}",
                    self.peek().line,
                    self.peek().column
                )
            finish_allowance_mm = float(self.advance().value)

        elif treatment == 'fillet':

            if self.peek().type not in ('number', 'number_with_unit'):
                raise ParseError(
                    f"Expected fillet radius value (mm), got {self.peek().type}",
                    self.peek().line,
                    self.peek().column
                )
            radius_mm = float(self.advance().value)

        elif treatment == 'chamfer':

            if self.peek().type not in ('number', 'number_with_unit'):
                raise ParseError(
                    f"Expected chamfer distance value (mm), got {self.peek().type}",
                    self.peek().line,
                    self.peek().column
                )
            distance_mm = float(self.advance().value)


        edge_id = None
        if self.peek().type == 'identifier':
            edge_id = self.advance().value

        self.expect_line_end()

        return Edge(
            treatment_type=treatment,
            rough_allowance_mm=rough_allowance_mm,
            finish_allowance_mm=finish_allowance_mm,
            radius_mm=radius_mm,
            distance_mm=distance_mm,
            id=edge_id
        )

    def parse_feature(self) -> Feature:
        feature_type = self.expect('keyword').value

        if feature_type == 'pocket':
            depth = self.expect('number_with_unit').value
            return Feature(type='pocket', depth=str(depth), depth_mm=depth)
        elif feature_type == 'profile':
            depth = self.expect('keyword', 'through').value
            side = self.expect('keyword').value
            return Feature(type='profile', depth=depth, side=side)
        elif feature_type == 'engrave':
            depth = self.expect('number_with_unit').value
            return Feature(type='engrave', depth=str(depth), depth_mm=depth)
        elif feature_type == 'hole':
            depth = self.expect('number_with_unit').value
            return Feature(type='hole', depth=str(depth), depth_mm=depth)
        elif feature_type in ('edge',):

            return Feature(type=feature_type, depth='through')
        else:
            raise ParseError(f"Unknown feature type: {feature_type}", self.peek().line, self.peek().column)

    def parse_inset(self) -> Inset:
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

    def parse_split(self) -> Split:
        self.expect('keyword', 'split')
        rows = self.expect('number').value
        cols = self.expect('number').value
        self.expect('keyword', 'rail')
        rail_mm = self.expect('number_with_unit').value
        self.expect('keyword', 'mullion')
        mullion_mm = self.expect('number_with_unit').value
        self.expect_line_end()
        self.expect('indent')

        children = []
        while self.peek().type != 'dedent':
            children.append(self.parse_node())
            self.skip_newlines()
        self.expect('dedent')

        return Split(rows=rows, cols=cols, rail_mm=rail_mm, mullion_mm=mullion_mm, children=tuple(children))

    def parse_cell(self) -> Cell:
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
    lexer = CompositionalPMLLexer(text)
    tokens = lexer.tokenize()
    parser = CompositionalPMLParser(tokens)
    return parser.parse()
