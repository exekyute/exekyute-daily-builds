"""A small, independent evaluator for the Excel formulas in the WIP workbook.

openpyxl writes formulas but does not compute them, so it cannot tell you what a
cell would show in Excel. This module computes the formulas itself, straight from
the workbook's own cells, so the verifier can prove the live formulas reproduce
the engine's numbers to the cent without ever opening Excel.

It is a recursive-descent evaluator over decimal.Decimal, deliberately small. It
covers exactly the grammar the workbook uses: numbers, text, cell references
(optionally qualified by a sheet name), ranges, the arithmetic operators, the six
comparisons, and the functions ROUND, SUM, COUNTIF, IF, ABS, MAX, and MIN. A cell
that holds a formula is resolved by evaluating that formula in turn, so a column
that references another formula column is followed through to its inputs.
"""

import re
from decimal import Decimal, ROUND_HALF_UP

from openpyxl.utils import get_column_letter, range_boundaries

TOKEN = re.compile(
    r"""
    (?P<WS>\s+)
  | (?P<NUMBER>\d+(?:\.\d+)?)
  | (?P<STRING>"(?:[^"]|"")*")
  | (?P<REF>(?:(?:'[^']+'|[A-Za-z_][A-Za-z0-9_]*)!)?\$?[A-Z]{1,3}\$?\d+(?::\$?[A-Z]{1,3}\$?\d+)?)
  | (?P<FUNC>[A-Za-z]+)
  | (?P<OP>>=|<=|<>|[-+*/(),<>=])
    """,
    re.VERBOSE,
)


class Range:
    """A rectangular block of cells on one sheet, used only as a function arg."""

    def __init__(self, sheet, coords):
        self.sheet = sheet
        self.coords = coords


def _tokenize(text):
    tokens = []
    pos = 0
    while pos < len(text):
        match = TOKEN.match(text, pos)
        if not match:
            raise ValueError("cannot tokenize formula near %r" % text[pos:pos + 12])
        pos = match.end()
        kind = match.lastgroup
        if kind == "WS":
            continue
        tokens.append((kind, match.group()))
    tokens.append(("END", ""))
    return tokens


class Evaluator:
    def __init__(self, workbook, default_sheet):
        self.wb = workbook
        self.default_sheet = default_sheet

    # Public entry point. Strips a leading "=" and evaluates the expression.
    # Resolving a cell reference re-enters this method on that cell's own
    # formula, so the parse position is saved and restored around each call to
    # keep the outer parse intact.
    def evaluate(self, formula, sheet=None):
        saved = getattr(self, "tokens", None), getattr(self, "i", None), getattr(self, "sheet", None)
        try:
            self.sheet = sheet or self.default_sheet
            text = formula[1:] if formula.startswith("=") else formula
            self.tokens = _tokenize(text)
            self.i = 0
            value = self._comparison()
            if self._peek()[0] != "END":
                raise ValueError("trailing tokens in formula: %r" % formula)
            return value
        finally:
            self.tokens, self.i, self.sheet = saved

    def _peek(self):
        return self.tokens[self.i]

    def _next(self):
        token = self.tokens[self.i]
        self.i += 1
        return token

    def _expect(self, value):
        kind, text = self._next()
        if text != value:
            raise ValueError("expected %r, got %r" % (value, text))

    def _comparison(self):
        left = self._additive()
        kind, text = self._peek()
        if kind == "OP" and text in (">", "<", ">=", "<=", "=", "<>"):
            self._next()
            right = self._additive()
            return self._compare(text, left, right)
        return left

    @staticmethod
    def _compare(op, left, right):
        if op == "=":
            return left == right
        if op == "<>":
            return left != right
        if op == ">":
            return left > right
        if op == "<":
            return left < right
        if op == ">=":
            return left >= right
        return left <= right

    def _additive(self):
        value = self._multiplicative()
        while True:
            kind, text = self._peek()
            if kind == "OP" and text in ("+", "-"):
                self._next()
                right = self._multiplicative()
                value = value + right if text == "+" else value - right
            else:
                return value

    def _multiplicative(self):
        value = self._unary()
        while True:
            kind, text = self._peek()
            if kind == "OP" and text in ("*", "/"):
                self._next()
                right = self._unary()
                value = value * right if text == "*" else value / right
            else:
                return value

    def _unary(self):
        kind, text = self._peek()
        if kind == "OP" and text == "-":
            self._next()
            return -self._unary()
        return self._primary()

    def _primary(self):
        kind, text = self._next()
        if kind == "NUMBER":
            return Decimal(text)
        if kind == "STRING":
            return text[1:-1].replace('""', '"')
        if kind == "OP" and text == "(":
            value = self._comparison()
            self._expect(")")
            return value
        if kind == "FUNC":
            return self._call(text.upper())
        if kind == "REF":
            return self._reference(text)
        raise ValueError("unexpected token %r" % text)

    def _reference(self, text):
        sheet = self.sheet
        if "!" in text:
            prefix, text = text.split("!", 1)
            sheet = prefix.strip("'")
        if ":" in text:
            return Range(sheet, self._expand(text))
        return self._cell_value(sheet, text.replace("$", ""))

    @staticmethod
    def _expand(span):
        min_col, min_row, max_col, max_row = range_boundaries(span.replace("$", ""))
        coords = []
        for row in range(min_row, max_row + 1):
            for col in range(min_col, max_col + 1):
                coords.append("%s%d" % (get_column_letter(col), row))
        return coords

    def _cell_value(self, sheet, coord):
        cell = self.wb[sheet][coord]
        value = cell.value
        if value is None:
            return Decimal("0")
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return Decimal(str(value))
        if isinstance(value, str):
            if value.startswith("="):
                return self.evaluate(value, sheet)
            return value
        return Decimal(str(value))

    def _call(self, name):
        self._expect("(")
        args = self._args()
        self._expect(")")
        if name == "ROUND":
            value, places = args
            quant = Decimal(1).scaleb(-int(places))
            return value.quantize(quant, rounding=ROUND_HALF_UP)
        if name == "SUM":
            return sum(self._flatten(args), Decimal("0"))
        if name == "COUNTIF":
            block, criteria = args
            values = self._values(block)
            return Decimal(sum(1 for v in values if v == criteria))
        if name == "IF":
            condition, when_true, when_false = args
            return when_true if condition else when_false
        if name == "ABS":
            return abs(args[0])
        if name == "MAX":
            return max(self._flatten(args))
        if name == "MIN":
            return min(self._flatten(args))
        raise ValueError("unsupported function %s" % name)

    def _args(self):
        if self._peek()[1] == ")":
            return []
        args = [self._comparison()]
        while self._peek()[1] == ",":
            self._next()
            args.append(self._comparison())
        return args

    def _flatten(self, args):
        out = []
        for arg in args:
            out.extend(self._values(arg))
        return out

    def _values(self, arg):
        if isinstance(arg, Range):
            return [self._cell_value(arg.sheet, coord) for coord in arg.coords]
        return [arg]
