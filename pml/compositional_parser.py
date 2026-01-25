
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
    # Generator AST nodes (Stage 12)
    ProfileGen,
    PocketGen,
    RaisedPanelGen,
    ChamferGen,
    WaveGen,
    SplitHorizontal,
    SplitVertical,
    SplitGrid,
    LinesGen,
    ConcentricBorderGen,
    # Stage 14 additions
    SplitHorizontalGaps,
    AtPosition,
    Subtract,
    Arch,
    # Stage 15 additions (polygon/triangle)
    Polygon,
    Triangle,
    # Stage 16 additions (x_panel generator)
    XPanelGen,
    # Stage 18 additions (hole_grid generator)
    HoleGridGen,
    # Stage 19 additions (PML templates)
    TemplateDef,
    # Waste cuts directive
    WasteCuts,
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
        while self.peek() and (self.peek().isalnum() or self.peek() in ('_', '-', ':')):
            ident += self.advance()


        keywords = {
            'sheet', 'project', 'component', 'use', 'place',
            'rect', 'circle', 'rounded_rect', 'roundedrect', 'line', 'polyline', 'spline', 'keepout', 'inset', 'frame', 'grid', 'split', 'cell', 'gap', 'rail', 'mullion', 'points', 'tolerance',
            'pocket', 'profile', 'engrave', 'hole', 'edge',
            'through', 'inside', 'outside', 'on',
            'diameter', 'radius', 'fit', 'horizontal', 'vertical',
            'allowance', 'fillet', 'chamfer',
            # Generator keywords (Stage 12)
            'raised_panel', 'border', 'border_depth', 'field_depth',
            'wave', 'count', 'amplitude', 'wavelength', 'groove', 'depth',
            'split_horizontal', 'split_vertical', 'split_grid',
            # Stage 13 generator keywords
            'lines', 'angle', 'spacing', 'width',
            'concentric_border', 'insets',
            # Stage 14 keywords
            'split_horizontal_gaps', 'at', 'subtract', 'inner',
            'arch', 'height',
            # Stage 15 keywords (polygon/triangle)
            'polygon', 'triangle', 'base',
            # Stage 16 keywords (x_panel generator)
            'x_panel', 'bar_width',
            # Stage 17 keywords (selective corner rounding)
            'corners', 'tl', 'tr', 'bl', 'br',
            # Absolute positioning keywords
            'size', 'corner_cleanup', 'tabs', 'kerf',
            # Stage 18 keywords (hole_grid generator)
            'hole_grid', 'pattern', 'rectangular', 'hexagonal', 'offset', 'align', 'center', 'corner',
            # Stage 19 keywords (PML templates)
            'template', 'params',
            # Waste cuts directive
            'waste_cuts', 'min_size', 'margin', 'strategy',
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

            if char == '$' and self.peek(1) == '{':
                start_line = self.line
                start_col = self.column
                self.advance()
                self.advance()
                param_name = ""
                while self.pos < len(self.text) and self.peek() != '}':
                    param_name += self.advance()
                if self.peek() == '}':
                    self.advance()
                tokens.append(Token('param_ref', param_name, start_line, start_col))
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

        project = None
        kerf_width_mm = None
        sheet = None

        while self.peek().type == 'keyword' and self.peek().value in ('project', 'kerf', 'sheet'):
            if self.peek().value == 'project':
                project = self.parse_project()
            elif self.peek().value == 'kerf':
                kerf_width_mm = self.parse_kerf()
            elif self.peek().value == 'sheet':
                sheet = self.parse_sheet()
            self.skip_newlines()

        if sheet is None:
            raise ParseError("Missing required 'sheet' declaration", self.peek().line, self.peek().column)

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
            kerf_width_mm=kerf_width_mm,
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

    def parse_kerf(self) -> float:
        self.expect('keyword', 'kerf')
        value = self.expect('number_with_unit').value
        self.expect_line_end()
        return value

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
        elif token.value in ('rounded_rect', 'roundedrect'):
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
        # Generator keywords (Stage 12)
        elif token.value == 'profile':
            return self.parse_profile_gen()
        elif token.value == 'pocket':
            return self.parse_pocket_gen()
        elif token.value == 'raised_panel':
            return self.parse_raised_panel_gen()
        elif token.value == 'chamfer':
            return self.parse_chamfer_gen()
        elif token.value == 'wave':
            return self.parse_wave_gen()
        elif token.value == 'split_horizontal':
            return self.parse_split_horizontal()
        elif token.value == 'split_vertical':
            return self.parse_split_vertical()
        elif token.value == 'split_grid':
            return self.parse_split_grid_gen()
        elif token.value == 'lines':
            return self.parse_lines_gen()
        elif token.value == 'concentric_border':
            return self.parse_concentric_border_gen()
        # Stage 14 keywords
        elif token.value == 'split_horizontal_gaps':
            return self.parse_split_horizontal_gaps()
        elif token.value == 'at':
            return self.parse_at_position()
        elif token.value == 'subtract':
            return self.parse_subtract()
        elif token.value == 'arch':
            return self.parse_arch()
        # Stage 15 keywords (polygon/triangle)
        elif token.value == 'polygon':
            return self.parse_polygon()
        elif token.value == 'triangle':
            return self.parse_triangle()
        # Stage 16 keywords (x_panel generator)
        elif token.value == 'x_panel':
            return self.parse_x_panel_gen()
        # Stage 18 keywords (hole_grid generator)
        elif token.value == 'hole_grid':
            return self.parse_hole_grid_gen()
        # Waste cuts directive
        elif token.value == 'waste_cuts':
            return self.parse_waste_cuts()
        else:
            raise ParseError(f"Unknown layout node: {token.value}", token.line, token.column)

    def _is_valid_id_token(self, token: Token) -> bool:
        """Check if token can be used as a shape ID (identifier or non-feature keyword)."""
        if token.type == 'identifier':
            return True
        if token.type == 'keyword':
            feature_keywords = ('pocket', 'profile', 'engrave', 'hole', 'edge')
            return token.value not in feature_keywords
        return False

    def parse_rect(self) -> Rect | AtPosition:
        self.expect('keyword', 'rect')

        rect_id = None
        token = self.peek()
        if self._is_valid_id_token(token) and token.value not in ('pocket', 'profile', 'engrave', 'hole', 'edge', 'at'):
            if token.type in ('identifier', 'keyword'):
                next_token = self.peek(1)
                if next_token.type in ('newline', 'eof', 'keyword', 'dedent', 'indent'):
                    if next_token.type == 'keyword' and next_token.value in ('pocket', 'profile', 'engrave', 'hole', 'edge', 'at'):
                        rect_id = self.advance().value
                    elif next_token.type in ('newline', 'eof', 'dedent', 'indent'):
                        rect_id = self.advance().value

        x_mm = None
        y_mm = None
        w_mm = None
        h_mm = None
        if self.peek().type == 'keyword' and self.peek().value == 'at':
            self.advance()
            x_mm = self.expect('number_with_unit').value
            if self.peek().type == 'punctuation' and self.peek().value == ',':
                self.advance()
            y_mm = self.expect('number_with_unit').value
            self.expect('keyword', 'size')
            w_mm = self.expect('number_with_unit').value
            if self.peek().type == 'punctuation' and self.peek().value == ',':
                self.advance()
            h_mm = self.expect('number_with_unit').value

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

        rect = Rect(children=tuple(children), feature=feature, id=rect_id)

        if x_mm is not None:
            return AtPosition(x_mm=x_mm, y_mm=y_mm, width_mm=w_mm, height_mm=h_mm, child=rect)
        return rect

    def parse_circle(self) -> Circle | AtPosition:
        self.expect('keyword', 'circle')

        circle_id = None
        if self.peek().type == 'identifier':
            circle_id = self.advance().value
        elif self.peek().type == 'keyword' and self.peek().value not in ('at', 'diameter', 'radius', 'fit', 'pocket', 'profile', 'engrave', 'hole', 'edge'):
            circle_id = self.advance().value

        x_mm = None
        y_mm = None
        if self.peek().type == 'keyword' and self.peek().value == 'at':
            self.advance()
            x_mm = self.expect('number_with_unit').value
            if self.peek().type == 'punctuation' and self.peek().value == ',':
                self.advance()
            y_mm = self.expect('number_with_unit').value

        diameter_mm = None
        radius_mm = None
        if self.peek().type == 'keyword':
            if self.peek().value == 'diameter':
                self.advance()
                diameter_mm = self.expect('number_with_unit').value
            elif self.peek().value == 'radius':
                self.advance()
                radius_mm = self.expect('number_with_unit').value
            elif self.peek().value == 'fit':
                self.advance()

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

        circle = Circle(diameter_mm=diameter_mm, radius_mm=radius_mm, children=tuple(children), feature=feature, id=circle_id)

        if x_mm is not None:
            size = diameter_mm if diameter_mm is not None else (radius_mm * 2 if radius_mm is not None else None)
            return AtPosition(x_mm=x_mm, y_mm=y_mm, width_mm=size, height_mm=size, child=circle)
        return circle

    def parse_rounded_rect(self) -> RoundedRect | AtPosition:
        token = self.advance()

        rounded_rect_id = None
        if self.peek().type == 'identifier':
            rounded_rect_id = self.advance().value
        elif self.peek().type == 'keyword' and self.peek().value not in ('at', 'radius', 'pocket', 'profile', 'engrave', 'hole', 'edge', 'corners'):
            rounded_rect_id = self.advance().value

        x_mm = None
        y_mm = None
        w_mm = None
        h_mm = None
        if self.peek().type == 'keyword' and self.peek().value == 'at':
            self.advance()
            x_mm = self.expect('number_with_unit').value
            if self.peek().type == 'punctuation' and self.peek().value == ',':
                self.advance()
            y_mm = self.expect('number_with_unit').value
            self.expect('keyword', 'size')
            w_mm = self.expect('number_with_unit').value
            if self.peek().type == 'punctuation' and self.peek().value == ',':
                self.advance()
            h_mm = self.expect('number_with_unit').value

        self.expect('keyword', 'radius')
        radius_mm = self.expect('number_with_unit').value

        corners = None
        if self.peek().type == 'keyword' and self.peek().value == 'corners':
            self.advance()
            corner_set = set()
            valid_corners = {'tl', 'tr', 'bl', 'br'}
            while self.peek().type == 'keyword' and self.peek().value in valid_corners:
                corner_set.add(self.advance().value)
            if not corner_set:
                raise ParseError(
                    "corners keyword requires at least one corner (tl, tr, bl, br)",
                    self.peek().line, self.peek().column
                )
            corners = frozenset(corner_set)

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

        rounded_rect = RoundedRect(radius_mm=radius_mm, children=tuple(children), feature=feature, id=rounded_rect_id, corners=corners)

        if x_mm is not None:
            return AtPosition(x_mm=x_mm, y_mm=y_mm, width_mm=w_mm, height_mm=h_mm, child=rounded_rect)
        return rounded_rect

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
        feature_keywords = ('engrave', 'pocket', 'profile', 'hole', 'edge')
        token = self.peek()
        if token.type == 'identifier':
            spline_id = self.advance().value
        elif token.type == 'keyword' and token.value not in feature_keywords and token.value != 'points':
            spline_id = self.advance().value

        feature = None
        if self.peek().type == 'keyword' and self.peek().value in feature_keywords:
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
            depth_token = self.peek()
            if depth_token.type == 'keyword' and depth_token.value == 'through':
                self.advance()
                depth = 'through'
                depth_mm = None
            else:
                depth_mm = self.expect('number_with_unit').value
                depth = str(depth_mm)
            corner_cleanup_tool_diameter_mm = None
            if self.peek().type == 'keyword' and self.peek().value == 'corner_cleanup':
                self.advance()
                corner_cleanup_tool_diameter_mm = self.expect('number_with_unit').value
            return Feature(type='pocket', depth=depth, depth_mm=depth_mm, corner_cleanup_tool_diameter_mm=corner_cleanup_tool_diameter_mm)
        elif feature_type == 'profile':
            depth_token = self.peek()
            if depth_token.type == 'keyword' and depth_token.value == 'through':
                self.advance()
                depth = 'through'
                depth_mm = None
            elif depth_token.type == 'number_with_unit':
                depth_mm = self.advance().value
                depth = str(depth_mm)
            else:
                raise ParseError(f"Expected 'through' or depth in mm, got {depth_token.value}", depth_token.line, depth_token.column)
            side = self.expect('keyword').value
            tab_count = None
            tab_height_mm = None
            tab_width_mm = None
            if self.peek().type == 'keyword' and self.peek().value == 'tabs':
                self.advance()
                tab_count = int(self.expect('number').value)
                self.expect('keyword', 'height')
                tab_height_mm = self.expect('number_with_unit').value
                if self.peek().type == 'keyword' and self.peek().value == 'width':
                    self.advance()
                    tab_width_mm = self.expect('number_with_unit').value
            return Feature(type='profile', depth=depth, side=side, depth_mm=depth_mm, tab_count=tab_count, tab_height_mm=tab_height_mm, tab_width_mm=tab_width_mm)
        elif feature_type == 'engrave':
            depth = self.expect('number_with_unit').value
            return Feature(type='engrave', depth=str(depth), depth_mm=depth)
        elif feature_type == 'hole':
            depth_token = self.peek()
            if depth_token.type == 'keyword' and depth_token.value == 'through':
                self.advance()
                return Feature(type='hole', depth='through', depth_mm=None)
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

    # =========================================================================
    # Generator Parsers (Stage 12: PML Generator Syntax)
    # =========================================================================

    def parse_profile_gen(self) -> ProfileGen:
        """Parse: profile <side> <depth>

        Examples:
            profile outside through
            profile inside 10mm
        """
        self.expect('keyword', 'profile')

        # Parse side: outside, inside, or on
        side_token = self.peek()
        if side_token.type != 'keyword' or side_token.value not in ('outside', 'inside', 'on'):
            raise ParseError(
                f"Expected profile side (outside/inside/on), got {side_token.value}",
                side_token.line, side_token.column
            )
        side = self.advance().value

        depth_token = self.peek()
        if depth_token.type == 'keyword' and depth_token.value == 'through':
            self.advance()
            depth = "through"
        elif depth_token.type == 'number_with_unit':
            depth = self.advance().value
        else:
            raise ParseError(
                f"Expected 'through' or depth in mm, got {depth_token.value}",
                depth_token.line, depth_token.column
            )

        tab_count = None
        tab_height_mm = None
        tab_width_mm = None
        if self.peek().type == 'keyword' and self.peek().value == 'tabs':
            self.advance()
            tab_count = int(self.expect('number').value)
            self.expect('keyword', 'height')
            tab_height_mm = self.expect('number_with_unit').value
            if self.peek().type == 'keyword' and self.peek().value == 'width':
                self.advance()
                tab_width_mm = self.expect('number_with_unit').value

        self.expect_line_end()
        return ProfileGen(
            side=side,
            depth=depth,
            tab_count=tab_count,
            tab_height_mm=tab_height_mm,
            tab_width_mm=tab_width_mm,
        )

    def parse_pocket_gen(self) -> PocketGen:
        """Parse: pocket <depth>

        Example:
            pocket 6mm
        """
        self.expect('keyword', 'pocket')
        depth_mm = self.expect('number_with_unit').value
        self.expect_line_end()
        return PocketGen(depth_mm=depth_mm)

    def parse_raised_panel_gen(self) -> RaisedPanelGen:
        """Parse: raised_panel border <width> border_depth <depth> field_depth <depth>

        Example:
            raised_panel border 25mm border_depth 6mm field_depth 2mm
        """
        self.expect('keyword', 'raised_panel')
        self.expect('keyword', 'border')
        border_width = self.expect('number_with_unit').value
        self.expect('keyword', 'border_depth')
        border_depth = self.expect('number_with_unit').value
        self.expect('keyword', 'field_depth')
        field_depth = self.expect('number_with_unit').value
        self.expect_line_end()
        return RaisedPanelGen(
            border_width_mm=border_width,
            border_depth_mm=border_depth,
            field_depth_mm=field_depth,
        )

    def parse_chamfer_gen(self) -> ChamferGen:
        """Parse: chamfer <width> <depth>

        Example:
            chamfer 5mm 3mm
        """
        self.expect('keyword', 'chamfer')
        width = self.expect('number_with_unit').value
        depth = self.expect('number_with_unit').value
        self.expect_line_end()
        return ChamferGen(width_mm=width, depth_mm=depth)

    def parse_wave_gen(self) -> WaveGen:
        """Parse: wave count <n> amplitude <mm> wavelength <mm> groove <mm> depth <mm>

        Example:
            wave count 5 amplitude 10mm wavelength 60mm groove 3mm depth 2mm
        """
        self.expect('keyword', 'wave')
        self.expect('keyword', 'count')
        wave_count = self.expect('number').value
        self.expect('keyword', 'amplitude')
        amplitude = self.expect('number_with_unit').value
        self.expect('keyword', 'wavelength')
        wavelength = self.expect('number_with_unit').value
        self.expect('keyword', 'groove')
        groove = self.expect('number_with_unit').value
        self.expect('keyword', 'depth')
        depth = self.expect('number_with_unit').value
        self.expect_line_end()
        return WaveGen(
            wave_count=int(wave_count),
            amplitude_mm=amplitude,
            wavelength_mm=wavelength,
            groove_width_mm=groove,
            depth_mm=depth,
        )

    def parse_x_panel_gen(self) -> XPanelGen:
        """Parse: x_panel bar_width <mm> depth <mm>

        Example:
            x_panel bar_width 50mm depth 6mm
        """
        self.expect('keyword', 'x_panel')
        self.expect('keyword', 'bar_width')
        bar_width = self.expect('number_with_unit').value
        self.expect('keyword', 'depth')
        depth = self.expect('number_with_unit').value
        self.expect_line_end()
        return XPanelGen(bar_width_mm=bar_width, depth_mm=depth)

    def parse_hole_grid_gen(self) -> HoleGridGen:
        """Parse: hole_grid spacing <mm> diameter <mm> depth <mm>|through [pattern rectangular|hexagonal|offset] [inset <mm>] [align center|corner]

        Example:
            hole_grid spacing 50mm diameter 6.35mm depth through pattern rectangular inset 50mm align center
        """
        self.expect('keyword', 'hole_grid')
        self.expect('keyword', 'spacing')
        spacing = self.expect('number_with_unit').value
        self.expect('keyword', 'diameter')
        diameter = self.expect('number_with_unit').value
        self.expect('keyword', 'depth')

        depth_token = self.peek()
        if depth_token.type == 'keyword' and depth_token.value == 'through':
            self.advance()
            depth: str | float = "through"
        elif depth_token.type == 'number_with_unit':
            depth = self.advance().value
        else:
            raise ParseError(
                f"Expected 'through' or depth in mm, got {depth_token.value}",
                depth_token.line, depth_token.column
            )

        pattern = "rectangular"
        if self.peek().type == 'keyword' and self.peek().value == 'pattern':
            self.advance()
            pattern_token = self.peek()
            if pattern_token.type == 'keyword' and pattern_token.value in ('rectangular', 'hexagonal', 'offset'):
                pattern = self.advance().value
            else:
                raise ParseError(
                    f"Expected pattern type (rectangular/hexagonal/offset), got {pattern_token.value}",
                    pattern_token.line, pattern_token.column
                )

        inset = 0.0
        if self.peek().type == 'keyword' and self.peek().value == 'inset':
            self.advance()
            inset = self.expect('number_with_unit').value

        align = "center"
        if self.peek().type == 'keyword' and self.peek().value == 'align':
            self.advance()
            align_token = self.peek()
            if align_token.type == 'keyword' and align_token.value in ('center', 'corner'):
                align = self.advance().value
            else:
                raise ParseError(
                    f"Expected alignment (center/corner), got {align_token.value}",
                    align_token.line, align_token.column
                )

        self.expect_line_end()
        return HoleGridGen(
            spacing_mm=spacing,
            diameter_mm=diameter,
            depth=depth,
            pattern=pattern,
            inset_mm=inset,
            align=align,
        )

    def parse_split_horizontal(self) -> SplitHorizontal:
        """Parse: split_horizontal <n> gap <mm>

        Example:
            split_horizontal 3 gap 20mm
                pocket 6mm
        """
        self.expect('keyword', 'split_horizontal')
        n = self.expect('number').value
        self.expect('keyword', 'gap')
        gap_mm = self.expect('number_with_unit').value
        self.expect_line_end()

        children = []
        if self.peek().type == 'indent':
            self.expect('indent')
            while self.peek().type != 'dedent':
                children.append(self.parse_node())
                self.skip_newlines()
            self.expect('dedent')

        return SplitHorizontal(n=int(n), gap_mm=gap_mm, children=tuple(children))

    def parse_split_vertical(self) -> SplitVertical:
        """Parse: split_vertical <n> gap <mm>

        Example:
            split_vertical 2 gap 20mm
                pocket 6mm
        """
        self.expect('keyword', 'split_vertical')
        n = self.expect('number').value
        self.expect('keyword', 'gap')
        gap_mm = self.expect('number_with_unit').value
        self.expect_line_end()

        children = []
        if self.peek().type == 'indent':
            self.expect('indent')
            while self.peek().type != 'dedent':
                children.append(self.parse_node())
                self.skip_newlines()
            self.expect('dedent')

        return SplitVertical(n=int(n), gap_mm=gap_mm, children=tuple(children))

    def parse_split_grid_gen(self) -> SplitGrid:
        """Parse: split_grid <rows> <cols> gap <mm>

        Example:
            split_grid 2 2 gap 35mm
                raised_panel border 25mm border_depth 6mm field_depth 2mm
        """
        self.expect('keyword', 'split_grid')
        rows = self.expect('number').value
        cols = self.expect('number').value
        self.expect('keyword', 'gap')
        gap_mm = self.expect('number_with_unit').value
        self.expect_line_end()

        children = []
        if self.peek().type == 'indent':
            self.expect('indent')
            while self.peek().type != 'dedent':
                children.append(self.parse_node())
                self.skip_newlines()
            self.expect('dedent')

        return SplitGrid(rows=int(rows), cols=int(cols), gap_mm=gap_mm, children=tuple(children))

    def parse_lines_gen(self) -> LinesGen:
        """Parse: lines angle <deg> spacing <mm> width <mm> depth <mm>

        Example:
            lines angle 45 spacing 25mm width 4mm depth 3mm
        """
        self.expect('keyword', 'lines')
        self.expect('keyword', 'angle')
        angle = self.expect('number').value
        self.expect('keyword', 'spacing')
        spacing = self.expect('number_with_unit').value
        self.expect('keyword', 'width')
        width = self.expect('number_with_unit').value
        self.expect('keyword', 'depth')
        depth = self.expect('number_with_unit').value
        self.expect_line_end()
        return LinesGen(
            angle_deg=float(angle),
            spacing_mm=spacing,
            line_width_mm=width,
            depth_mm=depth,
        )

    def parse_concentric_border_gen(self) -> ConcentricBorderGen:
        """Parse: concentric_border insets <mm> <mm> ... groove <mm> depth <mm>

        Example:
            concentric_border insets 15mm 30mm 45mm groove 3mm depth 2mm
        """
        self.expect('keyword', 'concentric_border')
        self.expect('keyword', 'insets')

        insets = []
        while self.peek().type == 'number_with_unit':
            insets.append(self.advance().value)

        if not insets:
            raise ParseError(
                "concentric_border requires at least one inset value",
                self.peek().line, self.peek().column
            )

        self.expect('keyword', 'groove')
        groove = self.expect('number_with_unit').value
        self.expect('keyword', 'depth')
        depth = self.expect('number_with_unit').value
        self.expect_line_end()
        return ConcentricBorderGen(
            insets_mm=tuple(insets),
            groove_width_mm=groove,
            depth_mm=depth,
        )

    # =========================================================================
    # Stage 14 Parsers: Additional PML features for remaining recipes
    # =========================================================================

    def parse_split_horizontal_gaps(self) -> SplitHorizontalGaps:
        """Parse: split_horizontal_gaps <n> gap <mm>

        Splits region into n+1 segments, applies children to the n gaps.
        Used for louver/dado patterns where gaps are machined.

        Example:
            split_horizontal_gaps 12 gap 12mm
                pocket 8mm
                chamfer 4mm 2mm
        """
        self.expect('keyword', 'split_horizontal_gaps')
        n = self.expect('number').value
        self.expect('keyword', 'gap')
        gap_mm = self.expect('number_with_unit').value
        self.expect_line_end()

        children = []
        if self.peek().type == 'indent':
            self.expect('indent')
            while self.peek().type != 'dedent':
                children.append(self.parse_node())
                self.skip_newlines()
            self.expect('dedent')

        return SplitHorizontalGaps(n=int(n), gap_mm=gap_mm, children=tuple(children))

    def parse_at_position(self) -> AtPosition:
        """Parse: at <x>mm <y>mm [width <w>mm height <h>mm]

        Positions the child at explicit coordinates within the current region.
        Optional width/height specify the region size (uses parent size if omitted).

        Examples:
            at 300mm 150mm width 600mm height 19mm
                pocket 10mm

            at 300mm 150mm
                pocket 10mm
        """
        self.expect('keyword', 'at')
        x_mm = self.expect('number_with_unit').value
        y_mm = self.expect('number_with_unit').value

        width_mm = None
        height_mm = None
        if self.peek().type == 'keyword' and self.peek().value == 'width':
            self.advance()
            width_mm = self.expect('number_with_unit').value
            self.expect('keyword', 'height')
            height_mm = self.expect('number_with_unit').value

        self.expect_line_end()

        child = None
        if self.peek().type == 'indent':
            self.expect('indent')
            child = self.parse_node()
            self.skip_newlines()
            self.expect('dedent')

        return AtPosition(x_mm=x_mm, y_mm=y_mm, width_mm=width_mm, height_mm=height_mm, child=child)

    def parse_subtract(self) -> Subtract:
        """Parse: subtract inner <mm>

        Creates a ring by subtracting inner region from outer.
        Children are applied to the resulting ring domain.

        Example:
            subtract inner 50mm
                pocket 5mm
        """
        self.expect('keyword', 'subtract')
        self.expect('keyword', 'inner')
        inner_inset_mm = self.expect('number_with_unit').value
        self.expect_line_end()

        children = []
        if self.peek().type == 'indent':
            self.expect('indent')
            while self.peek().type != 'dedent':
                children.append(self.parse_node())
                self.skip_newlines()
            self.expect('dedent')

        return Subtract(inner_inset_mm=inner_inset_mm, children=tuple(children))

    def parse_arch(self) -> Arch:
        """Parse: arch [id] width <mm> height <mm> radius <mm> [feature]

        Creates an arch shape (rectangle with semicircular top).

        Example:
            arch door width 500mm height 800mm radius 250mm
                profile outside through
                frame 60mm
                    raised_panel border 25mm border_depth 6mm field_depth 2mm
        """
        self.expect('keyword', 'arch')

        arch_id = None
        if self.peek().type == 'identifier':
            arch_id = self.advance().value

        self.expect('keyword', 'width')
        width_mm = self.expect('number_with_unit').value
        self.expect('keyword', 'height')
        height_mm = self.expect('number_with_unit').value
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

        return Arch(
            width_mm=width_mm,
            height_mm=height_mm,
            radius_mm=radius_mm,
            children=tuple(children),
            feature=feature,
            id=arch_id,
        )

    def parse_polygon(self) -> Polygon:
        self.expect('keyword', 'polygon')

        polygon_id = None
        if self.peek().type == 'identifier':
            polygon_id = self.advance().value

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

            x_token = self.expect('number_with_unit')
            x = x_token.value

            comma_token = self.peek()
            if comma_token.type != 'punctuation' or comma_token.value != ',':
                raise ParseError(f"Expected ',' between coordinates, got {comma_token.value}",
                               comma_token.line, comma_token.column)
            self.advance()

            y_token = self.expect('number_with_unit')
            y = y_token.value

            close_token = self.peek()
            if close_token.type != 'punctuation' or close_token.value != ')':
                raise ParseError(f"Expected ')' after point, got {close_token.value}",
                               close_token.line, close_token.column)
            self.advance()

            points.append((x, y))

        if len(points) < 3:
            token = self.peek()
            raise ParseError(f"Polygon requires at least 3 points, got {len(points)}",
                           token.line, token.column)

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

        return Polygon(points=tuple(points), children=tuple(children), feature=feature, id=polygon_id)

    def parse_triangle(self) -> Triangle:
        self.expect('keyword', 'triangle')

        triangle_id = None
        token = self.peek()
        if self._is_valid_id_token(token) and token.value not in ('base', 'pocket', 'profile', 'engrave', 'hole', 'edge'):
            triangle_id = self.advance().value

        self.expect('keyword', 'base')
        base_mm = self.expect('number_with_unit').value
        self.expect('keyword', 'height')
        height_mm = self.expect('number_with_unit').value

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

        return Triangle(
            base_mm=base_mm,
            height_mm=height_mm,
            children=tuple(children),
            feature=feature,
            id=triangle_id,
        )

    def parse_waste_cuts(self) -> WasteCuts:
        self.expect('keyword', 'waste_cuts')
        self.expect_line_end()

        min_width_mm = 200.0
        min_height_mm = 200.0
        margin_mm = 15.0
        tab_count = None
        tab_height_mm = None
        strategy = "largest"

        if self.peek().type == 'indent':
            self.expect('indent')
            while self.peek().type != 'dedent' and self.peek().type != 'eof':
                token = self.peek()
                if token.type == 'keyword' and token.value == 'min_size':
                    self.advance()
                    min_width_mm = self.expect('number_with_unit').value
                    min_height_mm = self.expect('number_with_unit').value
                    self.expect_line_end()
                elif token.type == 'keyword' and token.value == 'margin':
                    self.advance()
                    margin_mm = self.expect('number_with_unit').value
                    self.expect_line_end()
                elif token.type == 'keyword' and token.value == 'tabs':
                    self.advance()
                    tab_count = self.expect('number').value
                    self.expect('keyword', 'height')
                    tab_height_mm = self.expect('number_with_unit').value
                    self.expect_line_end()
                elif token.type == 'keyword' and token.value == 'strategy':
                    self.advance()
                    strat_token = self.peek()
                    if strat_token.type in ('keyword', 'identifier') and strat_token.value in ('largest', 'simple'):
                        strategy = self.advance().value
                    else:
                        raise ParseError(
                            f"Expected 'largest' or 'simple' for strategy, got {strat_token.value}",
                            strat_token.line, strat_token.column
                        )
                    self.expect_line_end()
                else:
                    raise ParseError(
                        f"Unknown waste_cuts parameter: {token.value}",
                        token.line, token.column
                    )
                self.skip_newlines()
            if self.peek().type == 'dedent':
                self.expect('dedent')

        if tab_count is None or tab_height_mm is None:
            raise ParseError(
                "waste_cuts requires 'tabs N height Hmm' parameter",
                self.peek().line, self.peek().column
            )

        return WasteCuts(
            min_width_mm=min_width_mm,
            min_height_mm=min_height_mm,
            margin_mm=margin_mm,
            tab_count=tab_count,
            tab_height_mm=tab_height_mm,
            strategy=strategy,
        )


def parse_compositional_pml(text: str) -> CompositionalLayoutAST:
    lexer = CompositionalPMLLexer(text)
    tokens = lexer.tokenize()
    parser = CompositionalPMLParser(tokens)
    return parser.parse()


def substitute_params(text: str, params: dict[str, float | str]) -> str:
    import re

    def replace_match(m: re.Match[str]) -> str:
        param_name = m.group(1)
        if param_name not in params:
            raise ParseError(f"Unknown parameter: ${{{param_name}}}", 0, 0)
        value = params[param_name]
        if isinstance(value, str):
            return value
        return f"{value}mm"

    return re.sub(r'\$\{(\w+)\}', replace_match, text)


def parse_template_file(text: str, parse_body: bool = False) -> TemplateDef:
    lexer = CompositionalPMLLexer(text)
    tokens = lexer.tokenize()
    parser = TemplateFileParser(tokens)
    return parser.parse_template(parse_body=parse_body)


class TemplateFileParser(CompositionalPMLParser):

    def parse_template(self, parse_body: bool = True) -> TemplateDef:
        self.skip_newlines()

        if self.peek().type != 'keyword' or self.peek().value != 'template':
            raise ParseError("Template file must start with 'template <name>'", self.peek().line, self.peek().column)

        self.expect('keyword', 'template')
        name = self.expect('identifier').value
        self.expect_line_end()

        params: dict[str, float] = {}
        body = None

        if self.peek().type == 'indent':
            self.expect('indent')

            if self.peek().type == 'keyword' and self.peek().value == 'params':
                self.advance()
                self.expect_line_end()

                if self.peek().type == 'indent':
                    self.expect('indent')
                    while self.peek().type != 'dedent':
                        token = self.peek()
                        if token.type == 'identifier':
                            param_name = self.advance().value
                        elif token.type == 'keyword':
                            param_name = self.advance().value
                        else:
                            raise ParseError(f"Expected parameter name, got {token.type}", token.line, token.column)
                        token = self.peek()
                        if token.type == 'number_with_unit':
                            param_value = self.advance().value
                        elif token.type in ('identifier', 'keyword'):
                            param_value = self.advance().value
                        else:
                            raise ParseError(f"Expected parameter value, got {token.type}", token.line, token.column)
                        params[param_name] = param_value
                        self.expect_line_end()
                        self.skip_newlines()
                    self.expect('dedent')
                self.skip_newlines()

            if parse_body and self.peek().type != 'dedent' and self.peek().type != 'eof':
                body = self.parse_node()

            self.skip_newlines()
            if self.peek().type == 'dedent':
                self.expect('dedent')

        return TemplateDef(name=name, params=params, body=body)
