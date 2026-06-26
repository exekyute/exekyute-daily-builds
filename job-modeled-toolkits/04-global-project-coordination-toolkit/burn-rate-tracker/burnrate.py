"""Core business logic for the Milestone-Driven Burn Rate Tracker.

This module is pure logic with no input or output. It starts from the consultant
spend the ledger already recorded, adds each project phase cost on top, and after
every phase reports the running burn rate against the fixed grant fund.

Burn rate is spent divided by the fund, expressed as a fixed-point percentage. All
money math uses Decimal with ROUND_HALF_UP.
"""

from decimal import Decimal, ROUND_HALF_UP

from validators import (
    InvalidPhase,
    validate_cost,
    validate_phase_name,
)

CENTS = Decimal("0.01")


def money(value):
    """Quantize a Decimal to two places using half-up rounding."""
    return Decimal(value).quantize(CENTS, rounding=ROUND_HALF_UP)


def burn_rate(spent, fund):
    """Return spent / fund as a percentage, quantized to two decimal places."""
    if fund <= 0:
        raise ValueError("grant fund must be greater than zero")
    percent = (Decimal(spent) / Decimal(fund)) * Decimal("100")
    return percent.quantize(CENTS, rounding=ROUND_HALF_UP)


def remaining(fund, spent):
    """Return fund minus spent (may be negative when over the fund)."""
    return money(Decimal(fund) - Decimal(spent))


class PhaseLine:
    """One accepted phase with the running totals after it was added."""

    def __init__(self, name, cost, spent, fund):
        self.name = name
        self.cost = money(cost)
        self.spent = money(spent)
        self.remaining = remaining(fund, spent)
        self.burn_rate = burn_rate(spent, fund)
        self.over_fund = spent > fund


class BurnResult:
    """The outcome of applying a batch of phases on top of consultant spend."""

    def __init__(self, fund, starting_spend, base_currency="USD"):
        self.base_currency = base_currency
        self.fund = money(fund)
        self.starting_spend = money(starting_spend)
        self.lines = []
        self.skipped = []
        self.duplicates = []

    @property
    def final_spent(self):
        if self.lines:
            return self.lines[-1].spent
        return self.starting_spend

    @property
    def final_remaining(self):
        return remaining(self.fund, self.final_spent)

    @property
    def final_burn_rate(self):
        return burn_rate(self.final_spent, self.fund)

    @property
    def over_fund(self):
        return self.final_spent > self.fund

    @property
    def phase_count(self):
        return len(self.lines)


def process_phases(records, fund, starting_spend, base_currency="USD"):
    """Apply phase records on top of the starting spend, in order.

    records is an iterable of dicts with phase and cost. A row that fails
    validation is recorded in skipped. A repeated phase name is recorded in
    duplicates and does not change the running total.
    """
    result = BurnResult(fund, starting_spend, base_currency)
    running = Decimal(starting_spend)
    seen_names = set()

    for index, record in enumerate(records, start=1):
        try:
            name = validate_phase_name(record.get("phase"))
            cost = validate_cost(record.get("cost"))
        except InvalidPhase as error:
            result.skipped.append(
                {"row": index, "record": record, "reason": str(error)}
            )
            continue

        key = name.lower()
        if key in seen_names:
            result.duplicates.append(
                {"row": index, "phase": name,
                 "reason": "duplicate phase name; first occurrence kept"}
            )
            continue

        seen_names.add(key)
        running = running + cost
        result.lines.append(PhaseLine(name, cost, running, Decimal(fund)))

    return result
