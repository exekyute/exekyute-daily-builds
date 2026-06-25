"""Load budget and actuals files for the variance analysis tool.

Both files share a `department,category,amount` header. Amounts are parsed with
decimal.Decimal so the comparison is exact. Duplicate department/category rows
within a file are summed and counted; blank or unreadable rows are skipped and
counted.
"""

import csv
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation
from pathlib import Path

REQUIRED_COLUMNS = ("department", "category", "amount")
CENTS = Decimal("0.01")


class LedgerError(Exception):
    """Raised when a file is missing or is missing a required column."""


def parse_amount(raw):
    """Parse a raw amount into a Decimal rounded to cents, or None if unreadable."""
    cleaned = raw.replace("$", "").replace(",", "").strip()
    if cleaned == "":
        return None
    try:
        value = Decimal(cleaned)
    except InvalidOperation:
        return None
    return value.quantize(CENTS, rounding=ROUND_HALF_UP)


class LoadResult:
    """Loaded line items keyed by (department, category), plus row counts."""

    def __init__(self):
        self.items = {}
        self.duplicates = 0
        self.skipped = 0


def load_amounts(path, label):
    """Read a department/category/amount file into a LoadResult.

    `label` is used in error messages (for example 'budget' or 'actuals').
    """
    path = Path(path)
    if not path.is_file():
        raise LedgerError(f"{label} file not found: {path}")

    result = LoadResult()
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        header = reader.fieldnames or []
        lookup = {name.strip().lower(): name for name in header}
        for column in REQUIRED_COLUMNS:
            if column not in lookup:
                found = ", ".join(header) if header else "(no columns)"
                raise LedgerError(
                    f"{path.name} is missing the required '{column}' column. "
                    f"Found: {found}."
                )
        dept_key = lookup["department"]
        cat_key = lookup["category"]
        amount_key = lookup["amount"]
        for raw in reader:
            department = (raw.get(dept_key) or "").strip()
            category = (raw.get(cat_key) or "").strip()
            amount = parse_amount(raw.get(amount_key) or "")
            if department == "" or category == "" or amount is None:
                result.skipped += 1
                continue
            key = (department, category)
            if key in result.items:
                result.items[key] += amount
                result.duplicates += 1
            else:
                result.items[key] = amount
    return result
