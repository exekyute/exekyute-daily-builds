"""Load and validate a historical cash flow file.

The file has a `period,net_cash_flow` header. A negative net cash flow is a net
outflow (burn) for that period. Amounts are parsed with decimal.Decimal. Blank
or unreadable rows are skipped and counted; a repeated period is counted and the
first occurrence is kept.
"""

import csv
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation
from pathlib import Path

REQUIRED_COLUMNS = ("period", "net_cash_flow")
CENTS = Decimal("0.01")


class HistoryError(Exception):
    """Raised when the history file is missing or is missing a required column."""


def parse_amount(raw):
    """Parse a raw net cash flow into a Decimal rounded to cents, or None."""
    cleaned = raw.replace("$", "").replace(",", "").strip()
    if cleaned == "":
        return None
    try:
        value = Decimal(cleaned)
    except InvalidOperation:
        return None
    return value.quantize(CENTS, rounding=ROUND_HALF_UP)


class HistoryResult:
    """Ordered (period, amount) records plus duplicate and skip counts."""

    def __init__(self):
        self.records = []
        self.duplicates = 0
        self.skipped = 0


def load_history(path):
    """Read the history CSV into a HistoryResult, preserving row order."""
    path = Path(path)
    if not path.is_file():
        raise HistoryError(f"history file not found: {path}")

    result = HistoryResult()
    seen = set()
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        header = reader.fieldnames or []
        lookup = {name.strip().lower(): name for name in header}
        for column in REQUIRED_COLUMNS:
            if column not in lookup:
                found = ", ".join(header) if header else "(no columns)"
                raise HistoryError(
                    f"{path.name} is missing the required '{column}' column. "
                    f"Found: {found}."
                )
        period_key = lookup["period"]
        amount_key = lookup["net_cash_flow"]
        for raw in reader:
            period = (raw.get(period_key) or "").strip()
            amount = parse_amount(raw.get(amount_key) or "")
            if period == "" or amount is None:
                result.skipped += 1
                continue
            if period in seen:
                result.duplicates += 1
                continue
            seen.add(period)
            result.records.append((period, amount))
    return result
