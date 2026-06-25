"""Read the central budget file produced by the Multi-Currency Consultant Ledger.

The burn rate tracker does not recompute consultant spend. It loads the grant
total and the consultant spend straight from the ledger's central_budget.json so
the two tools always agree on the same starting numbers.
"""

import json
from decimal import Decimal, InvalidOperation


class BudgetError(Exception):
    """Raised when the central budget file is missing or malformed."""


REQUIRED_KEYS = ("base_currency", "grant_total", "consultant_spend")


def load_budget(path):
    """Read the central budget file and return base currency, grant, and spend."""
    try:
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
    except FileNotFoundError:
        raise BudgetError(
            f"central budget file not found: {path}. "
            "Run the multi-currency-ledger tool first to produce it."
        )
    except json.JSONDecodeError as error:
        raise BudgetError(f"central budget file is not valid JSON: {error}")

    missing = [key for key in REQUIRED_KEYS if key not in data]
    if missing:
        raise BudgetError(
            "central budget file is missing key(s): " + ", ".join(missing)
        )

    try:
        grant_total = Decimal(str(data["grant_total"]))
        consultant_spend = Decimal(str(data["consultant_spend"]))
    except InvalidOperation:
        raise BudgetError("grant_total or consultant_spend is not a number")

    return {
        "base_currency": data["base_currency"],
        "grant_total": grant_total,
        "consultant_spend": consultant_spend,
    }
