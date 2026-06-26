"""Validation and parsing for the lease renewal scheduler.

This module sits between the raw CSV text and the pure logic in renewal_logic.py.
It checks the header, checks each row, and turns the string fields of a good row
into typed values. It reads the same leases file the rent roll calculator uses, but
only needs four of its columns; any other columns are ignored.

Whole-file problems raise ValidationError and stop the run. Row-level problems never
stop the run: the bad row is skipped and recorded as a RowIssue with its line number
and a plain reason.
"""

from datetime import datetime
from decimal import Decimal, InvalidOperation

# The columns this tool needs from the leases file. Extra columns are allowed and
# ignored, so the same leases.csv the rent roll calculator reads works here too.
REQUIRED_COLUMNS = ["unit", "tenant", "monthly_rent", "lease_end"]


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


class Lease(object):
    """A validated lease, with money as Decimal and the lease end as a date."""

    def __init__(self, unit, tenant, monthly_rent, lease_end):
        self.unit = unit
        self.tenant = tenant
        self.monthly_rent = monthly_rent
        self.lease_end = lease_end


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
    """Turn raw rows into Lease records, collecting skipped rows as RowIssues.

    rows is a list of lists of strings, as read by csv.reader (the header row is
    not included). Returns (leases, issues). Line numbers count the header as
    line 1, so the first data row is line 2.
    """
    index = header_index(header)
    leases = []
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
            monthly_rent = parse_money(row[index["monthly_rent"]])
        except InvalidOperation:
            issues.append(RowIssue(line_number, "monthly_rent is not a number"))
            continue
        if monthly_rent <= Decimal("0"):
            issues.append(RowIssue(line_number, "monthly_rent must be greater than 0"))
            continue

        try:
            lease_end = parse_date(row[index["lease_end"]])
        except ValueError:
            issues.append(RowIssue(line_number, "lease_end is not in YYYY-MM-DD form"))
            continue
        if lease_end is None:
            issues.append(RowIssue(line_number, "lease_end is required"))
            continue

        seen_units.add(unit)
        leases.append(Lease(unit, tenant, monthly_rent, lease_end))

    return leases, issues
