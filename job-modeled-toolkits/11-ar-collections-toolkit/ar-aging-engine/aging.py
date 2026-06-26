"""Pure aging and late-fee logic for the AR Aging and Late-Fee Engine.

This module contains no input/output and no validation. Every function takes
plain values and returns plain values, so the rules can be tested directly and
reused without touching files or the command line.

Money is handled with decimal.Decimal and rounded with ROUND_HALF_UP so that
amounts are always exact to the cent and never appear in scientific notation.
"""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal, ROUND_HALF_UP

# All money values are rounded to this number of decimal places (cents).
CENTS = Decimal("0.01")

# Aging buckets in display order. The dashboard reuses the same order.
BUCKETS = ["Current", "1-30", "31-60", "61-90", "90-plus"]

# Column order of the aging report the engine writes and the dashboard reads.
OUTPUT_HEADER = [
    "invoice_number",
    "customer",
    "issue_date",
    "due_date",
    "amount",
    "days_past_due",
    "aging_bucket",
    "late_fee",
    "total_due",
]


@dataclass(frozen=True)
class Invoice:
    """A single open invoice after parsing, before aging."""

    invoice_number: str
    customer: str
    issue_date: date
    due_date: date
    amount: Decimal


@dataclass(frozen=True)
class AgedInvoice:
    """An invoice with its computed aging fields."""

    invoice_number: str
    customer: str
    issue_date: date
    due_date: date
    amount: Decimal
    days_past_due: int
    aging_bucket: str
    late_fee: Decimal
    total_due: Decimal


def days_past_due(due, reference):
    """Whole days the invoice is past due as of the reference date.

    A zero or negative result means the invoice is not yet overdue.
    """
    return (reference - due).days


def aging_bucket(dpd):
    """Assign an aging bucket from days past due using inclusive ranges.

    Current  : dpd <= 0
    1-30     : 1 to 30
    31-60    : 31 to 60
    61-90    : 61 to 90
    90-plus  : 91 and over
    """
    if dpd <= 0:
        return "Current"
    if dpd <= 30:
        return "1-30"
    if dpd <= 60:
        return "31-60"
    if dpd <= 90:
        return "61-90"
    return "90-plus"


def late_fee(amount, dpd, rate):
    """Late fee for an invoice: amount * rate, charged only when overdue.

    Current invoices (dpd < 1) are charged nothing. The result is rounded to
    the cent with ROUND_HALF_UP.
    """
    if dpd < 1:
        return Decimal("0.00")
    return (amount * rate).quantize(CENTS, rounding=ROUND_HALF_UP)


def age_invoice(invoice, reference, rate):
    """Produce an AgedInvoice from an Invoice, reference date, and fee rate."""
    dpd = days_past_due(invoice.due_date, reference)
    bucket = aging_bucket(dpd)
    fee = late_fee(invoice.amount, dpd, rate)
    amount = invoice.amount.quantize(CENTS, rounding=ROUND_HALF_UP)
    return AgedInvoice(
        invoice_number=invoice.invoice_number,
        customer=invoice.customer,
        issue_date=invoice.issue_date,
        due_date=invoice.due_date,
        amount=amount,
        days_past_due=dpd,
        aging_bucket=bucket,
        late_fee=fee,
        total_due=(amount + fee).quantize(CENTS, rounding=ROUND_HALF_UP),
    )


def age_invoices(invoices, reference, rate):
    """Age a list of invoices, preserving input order."""
    return [age_invoice(inv, reference, rate) for inv in invoices]


def summarize(aged):
    """Total outstanding (amount plus late fee) and count per aging bucket.

    Returns a dict keyed by bucket label with ``count`` and ``total`` (Decimal),
    covering every bucket in BUCKETS even when its count is zero.
    """
    summary = {b: {"count": 0, "total": Decimal("0.00")} for b in BUCKETS}
    for item in aged:
        entry = summary[item.aging_bucket]
        entry["count"] += 1
        entry["total"] += item.total_due
    return summary


def grand_total(aged):
    """Sum of total_due across every aged invoice."""
    total = Decimal("0.00")
    for item in aged:
        total += item.total_due
    return total


def money(value):
    """Format a Decimal as a fixed-point string with two decimals.

    Quantizing first guarantees two places and avoids scientific notation.
    """
    return str(value.quantize(CENTS, rounding=ROUND_HALF_UP))
