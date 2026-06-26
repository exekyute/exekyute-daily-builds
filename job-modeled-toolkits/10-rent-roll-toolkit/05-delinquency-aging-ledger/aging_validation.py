"""Validation and parsing for the delinquency and aging ledger.

This module sits between the raw CSV text and the pure logic in aging_logic.py. It
checks the header, checks each row, and turns the string fields of a good row into
typed values. It does not compute balances or fees and it does not print; it returns
clean Charge records and a list of problems.

Whole-file problems raise ValidationError and stop the run. Row-level problems never
stop the run: the bad row is skipped and recorded as a RowIssue with its line number
and a plain reason. A charge that is well formed but fully paid is not a problem here;
it is carried through and the business rule in the CLI decides to leave it off the
delinquency report.
"""

from datetime import datetime
from decimal import Decimal, InvalidOperation

REQUIRED_COLUMNS = [
    "unit",
    "tenant",
    "charge_type",
    "due_date",
    "amount_charged",
    "amount_paid",
]


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


class Charge(object):
    """A validated charge, with money as Decimal and the due date as a date."""

    def __init__(self, unit, tenant, charge_type, due_date, amount_charged, amount_paid):
        self.unit = unit
        self.tenant = tenant
        self.charge_type = charge_type
        self.due_date = due_date
        self.amount_charged = amount_charged
        self.amount_paid = amount_paid


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
    """Turn raw rows into Charge records, collecting skipped rows as RowIssues.

    rows is a list of lists of strings, as read by csv.reader (the header row is
    not included). Returns (charges, issues). Line numbers count the header as
    line 1, so the first data row is line 2.
    """
    index = header_index(header)
    charges = []
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
        charge_type = row[index["charge_type"]].strip()

        if unit == "":
            issues.append(RowIssue(line_number, "unit is blank"))
            continue
        if unit in seen_units:
            issues.append(RowIssue(line_number, "duplicate unit '{0}'".format(unit)))
            continue
        if tenant == "":
            issues.append(RowIssue(line_number, "tenant is blank"))
            continue
        if charge_type == "":
            issues.append(RowIssue(line_number, "charge_type is blank"))
            continue

        try:
            amount_charged = parse_money(row[index["amount_charged"]])
        except InvalidOperation:
            issues.append(RowIssue(line_number, "amount_charged is not a number"))
            continue
        if amount_charged <= Decimal("0"):
            issues.append(RowIssue(line_number, "amount_charged must be greater than 0"))
            continue

        try:
            amount_paid = parse_money(row[index["amount_paid"]])
        except InvalidOperation:
            issues.append(RowIssue(line_number, "amount_paid is not a number"))
            continue
        if amount_paid < Decimal("0"):
            issues.append(RowIssue(line_number, "amount_paid cannot be negative"))
            continue

        try:
            due_date = parse_date(row[index["due_date"]])
        except ValueError:
            issues.append(RowIssue(line_number, "due_date is not in YYYY-MM-DD form"))
            continue
        if due_date is None:
            issues.append(RowIssue(line_number, "due_date is required"))
            continue

        seen_units.add(unit)
        charges.append(
            Charge(unit, tenant, charge_type, due_date, amount_charged, amount_paid)
        )

    return charges, issues
