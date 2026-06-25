"""Core business logic for the Multi-Currency Consultant Ledger.

This module is pure logic with no input or output. It converts each invoice into
the base currency, sums the total consultant spend, reconciles that spend against
the approved grant total, and reports every row that was skipped or duplicated.

All money math uses Decimal with ROUND_HALF_UP and is quantized to two decimal
places so printed values are always fixed-point.
"""

from decimal import Decimal, ROUND_HALF_UP

from rates import BASE_CURRENCY, EXCHANGE_RATES
from validators import (
    InvalidInvoice,
    validate_amount,
    validate_currency,
    validate_invoice_id,
)

CENTS = Decimal("0.01")


def money(value):
    """Quantize a Decimal to two places using banker-safe half-up rounding."""
    return Decimal(value).quantize(CENTS, rounding=ROUND_HALF_UP)


def convert_to_base(amount, currency):
    """Convert a foreign amount into the base currency.

    base_amount = amount * rate, where rate is base units per 1 foreign unit.
    """
    rate = EXCHANGE_RATES[currency]
    return money(Decimal(amount) * rate)


class LedgerLine:
    """One accepted invoice converted into the base currency."""

    def __init__(self, invoice_id, consultant, currency, amount, base_amount):
        self.invoice_id = invoice_id
        self.consultant = consultant
        self.currency = currency
        self.amount = amount
        self.base_amount = base_amount


class LedgerResult:
    """The outcome of reconciling a batch of invoices against the grant total."""

    def __init__(self, grant_total):
        self.base_currency = BASE_CURRENCY
        self.grant_total = money(grant_total)
        self.lines = []
        self.skipped = []
        self.duplicates = []

    @property
    def consultant_spend(self):
        return money(sum((line.base_amount for line in self.lines), Decimal("0")))

    @property
    def remaining(self):
        return money(self.grant_total - self.consultant_spend)

    @property
    def over_budget(self):
        return self.consultant_spend > self.grant_total

    @property
    def invoice_count(self):
        return len(self.lines)


def process_invoices(records, grant_total):
    """Reconcile invoice records against the grant total.

    records is an iterable of dicts with invoice_id, consultant, currency, amount.
    A row that fails validation is recorded in skipped. A repeated invoice id is
    recorded in duplicates and does not change the running total; the first
    occurrence is kept.
    """
    result = LedgerResult(grant_total)
    seen_ids = set()

    for index, record in enumerate(records, start=1):
        try:
            invoice_id = validate_invoice_id(record.get("invoice_id"))
            currency = validate_currency(record.get("currency"))
            amount = validate_amount(record.get("amount"))
        except InvalidInvoice as error:
            result.skipped.append(
                {"row": index, "record": record, "reason": str(error)}
            )
            continue

        if invoice_id in seen_ids:
            result.duplicates.append(
                {"row": index, "invoice_id": invoice_id,
                 "reason": "duplicate invoice id; first occurrence kept"}
            )
            continue

        seen_ids.add(invoice_id)
        consultant = (record.get("consultant") or "").strip()
        base_amount = convert_to_base(amount, currency)
        result.lines.append(
            LedgerLine(invoice_id, consultant, currency, amount, base_amount)
        )

    return result
