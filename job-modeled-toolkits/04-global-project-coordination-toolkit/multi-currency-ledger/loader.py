"""CSV loading for the Multi-Currency Consultant Ledger.

The loader is deliberately thin. It reads the invoice CSV into a list of plain
dicts and checks that the required columns are present. Per-row validation
(currency, amount, blank ids) happens later in the logic layer so a single bad
row is counted rather than fatal.
"""

import csv

REQUIRED_COLUMNS = ("invoice_id", "consultant", "currency", "amount")


class LedgerError(Exception):
    """Raised when the invoice file cannot be read or is missing a column."""


def load_invoices(path):
    """Read the invoice CSV at path and return a list of row dicts."""
    try:
        with open(path, newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            header = reader.fieldnames or []
            missing = [name for name in REQUIRED_COLUMNS if name not in header]
            if missing:
                raise LedgerError(
                    "invoice file is missing required column(s): "
                    + ", ".join(missing)
                )
            return list(reader)
    except FileNotFoundError:
        raise LedgerError(f"invoice file not found: {path}")
