"""Validation and parsing for the security deposit reconciliation tool.

This module sits between the raw CSV text and the pure logic in deposit_logic.py. It
checks the header, checks each row, and turns the string fields of a good row into
typed values. It does not do any money math and it does not print; it returns clean
MoveOut records and a list of problems.

Whole-file problems raise ValidationError and stop the run. Row-level problems never
stop the run: the bad row is skipped and recorded as a RowIssue with its line number
and a plain reason. The deduction columns may be blank, which reads as 0.
"""

from datetime import datetime
from decimal import Decimal, InvalidOperation

REQUIRED_COLUMNS = [
    "unit",
    "tenant",
    "move_out_date",
    "deposit_held",
    "unpaid_rent",
    "cleaning",
    "damages",
]

# The deduction columns, all of which may be blank (read as 0).
DEDUCTION_COLUMNS = ["unpaid_rent", "cleaning", "damages"]


class ValidationError(Exception):
    """Raised for a whole-file problem that stops the run."""

    def __init__(self, problems):
        self.problems = list(problems)
        super().__init__("; ".join(self.problems))


class RowIssue(object):
    """One skipped row: its line number in the file and the reason it was skipped."""

    def __init__(self, line_number, reason):
        self.line_number = line_number
        self.reason = reason

    def __str__(self):
        return "line {0}: {1}".format(self.line_number, self.reason)


class MoveOut(object):
    """A validated move-out, with money as Decimal and the date as a date object."""

    def __init__(self, unit, tenant, move_out_date, deposit_held, unpaid_rent, cleaning, damages):
        self.unit = unit
        self.tenant = tenant
        self.move_out_date = move_out_date
        self.deposit_held = deposit_held
        self.unpaid_rent = unpaid_rent
        self.cleaning = cleaning
        self.damages = damages


def header_index(header):
    """Map each lower-cased, trimmed column name to its position in the header."""
    return {name.strip().lower(): position for position, name in enumerate(header)}


def missing_columns(header):
    """Return the required columns that are not present in the header."""
    present = set(header_index(header).keys())
    return [column for column in REQUIRED_COLUMNS if column not in present]


def parse_money(text):
    """Parse a money string like '$1,500.00' into a Decimal. Blank reads as 0."""
    cleaned = text.replace("$", "").replace(",", "").strip()
    if cleaned == "":
        return Decimal("0")
    return Decimal(cleaned)


def parse_date(text):
    """Parse a 'YYYY-MM-DD' string into a date. Blank reads as None."""
    cleaned = text.strip()
    if cleaned == "":
        return None
    return datetime.strptime(cleaned, "%Y-%m-%d").date()


def check_header(header):
    """Raise ValidationError if the header is missing any required column."""
    missing = missing_columns(header)
    if missing:
        raise ValidationError(
            ["missing required column: {0}".format(name) for name in missing]
        )


def validate_rows(header, rows):
    """Turn raw rows into MoveOut records, collecting skipped rows as RowIssues.

    rows is a list of lists of strings, as read by csv.reader (the header row is
    not included). Returns (move_outs, issues). Line numbers count the header as
    line 1, so the first data row is line 2.
    """
    index = header_index(header)
    move_outs = []
    issues = []
    seen_units = set()

    for offset, row in enumerate(rows):
        line_number = offset + 2

        if len(row) != len(header):
            issues.append(
                RowIssue(
                    line_number,
                    "expected {0} fields, found {1}".format(len(header), len(row)),
                )
            )
            continue

        unit = row[index["unit"]].strip()
        tenant = row[index["tenant"]].strip()

        if unit == "":
            issues.append(RowIssue(line_number, "unit is blank"))
            continue
        if unit in seen_units:
            issues.append(RowIssue(line_number, "duplicate unit '{0}'".format(unit)))
            continue
        if tenant == "":
            issues.append(RowIssue(line_number, "tenant is blank"))
            continue

        try:
            deposit_held = parse_money(row[index["deposit_held"]])
        except InvalidOperation:
            issues.append(RowIssue(line_number, "deposit_held is not a number"))
            continue
        if deposit_held < Decimal("0"):
            issues.append(RowIssue(line_number, "deposit_held cannot be negative"))
            continue

        deductions = {}
        bad_deduction = None
        for column in DEDUCTION_COLUMNS:
            try:
                value = parse_money(row[index[column]])
            except InvalidOperation:
                bad_deduction = "{0} is not a number".format(column)
                break
            if value < Decimal("0"):
                bad_deduction = "{0} cannot be negative".format(column)
                break
            deductions[column] = value
        if bad_deduction is not None:
            issues.append(RowIssue(line_number, bad_deduction))
            continue

        try:
            move_out_date = parse_date(row[index["move_out_date"]])
        except ValueError:
            issues.append(RowIssue(line_number, "move_out_date is not in YYYY-MM-DD form"))
            continue
        if move_out_date is None:
            issues.append(RowIssue(line_number, "move_out_date is required"))
            continue

        seen_units.add(unit)
        move_outs.append(
            MoveOut(
                unit,
                tenant,
                move_out_date,
                deposit_held,
                deductions["unpaid_rent"],
                deductions["cleaning"],
                deductions["damages"],
            )
        )

    return move_outs, issues
