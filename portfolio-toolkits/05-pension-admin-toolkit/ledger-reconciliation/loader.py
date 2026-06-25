"""CSV loading and column validation for the reconciliation tool.

This is the defensive layer. It reads a ledger file, checks the required columns
exist, parses each amount as a Decimal, and reports problems instead of letting
bad data flow into the comparison. Duplicate Employee IDs are captured rather
than silently overwritten, because a duplicate is itself a finding.
"""

import csv
from decimal import Decimal, InvalidOperation


class LedgerError(ValueError):
    """Raised when a ledger file is missing columns or cannot be read."""


def _parse_amount(raw):
    """Return (amount, error). Exactly one of the two is None."""
    text = str(raw).strip()
    if text == "":
        return None, "amount is blank"
    try:
        return Decimal(text), None
    except InvalidOperation:
        return None, f"amount is not a number: {raw!r}"


def load_ledger(path, required_columns):
    """Load a ledger CSV keyed by employee_id.

    Returns a dict:
        {
            "records":    {employee_id: {column: value, ...}},
            "duplicates": [employee_id, ...],   # ids that appeared more than once
            "skipped":    [(row_number, reason), ...],  # rows dropped for bad data
        }

    The first time an id is seen it is stored; a later repeat is recorded in
    `duplicates` and does not overwrite the original.
    """
    records = {}
    duplicates = []
    skipped = []

    try:
        handle = open(path, newline="", encoding="utf-8")
    except FileNotFoundError:
        raise LedgerError(f"Ledger file not found: {path}")

    with handle:
        reader = csv.DictReader(handle)
        headers = reader.fieldnames or []
        missing = [column for column in required_columns if column not in headers]
        if missing:
            raise LedgerError(
                f"{path} is missing required column(s): {', '.join(missing)}."
            )

        for row_number, row in enumerate(reader, start=2):  # row 1 is the header
            employee_id = (row.get("employee_id") or "").strip()
            if employee_id == "":
                skipped.append((row_number, "employee_id is blank"))
                continue

            amount, error = _parse_amount(row.get("amount"))
            if error is not None:
                skipped.append((row_number, f"{employee_id}: {error}"))
                continue

            if employee_id in records:
                duplicates.append(employee_id)
                continue

            entry = {"amount": amount}
            if "name" in headers:
                entry["name"] = (row.get("name") or "").strip()
            records[employee_id] = entry

    return {"records": records, "duplicates": duplicates, "skipped": skipped}
