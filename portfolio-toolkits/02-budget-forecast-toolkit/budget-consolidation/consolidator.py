"""Standardize departmental rows and merge them into a master budget.

All money is handled with decimal.Decimal and rounded half up to cents, so the
output is exact and printed in plain fixed-point notation.
"""

from decimal import Decimal, ROUND_HALF_UP, InvalidOperation

CENTS = Decimal("0.01")


def standardize_amount(raw):
    """Parse a raw amount string into a Decimal rounded to cents.

    Strips dollar signs, thousands commas, and surrounding whitespace. Returns
    None when the value is blank or cannot be read as a number, so the caller
    can skip and count it instead of crashing.
    """
    cleaned = raw.replace("$", "").replace(",", "").strip()
    if cleaned == "":
        return None
    try:
        value = Decimal(cleaned)
    except InvalidOperation:
        return None
    return value.quantize(CENTS, rounding=ROUND_HALF_UP)


def standardize_category(raw):
    """Normalize a category label to Title Case with single spaces."""
    return " ".join(raw.split()).title()


def format_amount(value):
    """Return a fixed-point string for a Decimal, never scientific notation."""
    return f"{value.quantize(CENTS, rounding=ROUND_HALF_UP):f}"


class ConsolidationResult:
    """The merged master rows plus counts of what happened along the way."""

    def __init__(self):
        self.rows = []
        self.departments = 0
        self.line_items = 0
        self.duplicates_merged = 0
        self.skipped_blank_category = 0
        self.skipped_bad_amount = 0


def consolidate(departments):
    """Merge standardized department rows into one sorted master budget.

    `departments` is an iterable of (department_name, rows) pairs, where each
    row is a dict with raw 'category' and 'amount' strings. Duplicate categories
    within a department are summed into a single line. Returns a
    ConsolidationResult with rows sorted by department then category.
    """
    result = ConsolidationResult()
    merged = {}
    for department, rows in departments:
        result.departments += 1
        for row in rows:
            category = standardize_category(row["category"])
            if category == "":
                result.skipped_blank_category += 1
                continue
            amount = standardize_amount(row["amount"])
            if amount is None:
                result.skipped_bad_amount += 1
                continue
            key = (department, category)
            if key in merged:
                merged[key] += amount
                result.duplicates_merged += 1
            else:
                merged[key] = amount

    for key in sorted(merged):
        department, category = key
        result.rows.append(
            {
                "department": department,
                "category": category,
                "amount": merged[key].quantize(CENTS, rounding=ROUND_HALF_UP),
            }
        )
    result.line_items = len(result.rows)
    return result
