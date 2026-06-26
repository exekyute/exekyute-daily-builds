"""Pure business logic for the delinquency and aging ledger.

This module holds the money and date math only. It does not read files, print, or
touch the command line, which keeps the rules easy to test with fixed numbers and
easy to reuse from the thin CLI wrapper in cli.py and the validation layer in
aging_validation.py.

Money uses decimal.Decimal with ROUND_HALF_UP, quantized to cents. A charge is aged
by the actual number of days past its due date. The grace period is a fee policy: it
does not change the aging bucket, it only decides whether a late fee has started to
accrue, so a charge a few days late still ages into a bucket but carries no fee yet.
"""

from decimal import Decimal, ROUND_HALF_UP

MONEY = Decimal("0.01")
ZERO = Decimal("0.00")

# Aging buckets, in order from least to most overdue.
BUCKET_CURRENT = "current"
BUCKET_1_30 = "1-30"
BUCKET_31_60 = "31-60"
BUCKET_61_90 = "61-90"
BUCKET_90_PLUS = "90+"

BUCKET_ORDER = [
    BUCKET_CURRENT,
    BUCKET_1_30,
    BUCKET_31_60,
    BUCKET_61_90,
    BUCKET_90_PLUS,
]


def quantize_money(value):
    """Round a Decimal to cents, half up."""
    return value.quantize(MONEY, rounding=ROUND_HALF_UP)


def balance(amount_charged, amount_paid):
    """What is still owed on a charge: the amount charged less the amount paid."""
    return quantize_money(amount_charged - amount_paid)


def days_overdue(as_of, due_date):
    """Whole days past the due date, never negative. 0 when the charge is not yet due."""
    days = (as_of - due_date).days
    return days if days > 0 else 0


def bucket_for(overdue):
    """Place a number of overdue days into an aging bucket."""
    if overdue <= 0:
        return BUCKET_CURRENT
    if overdue <= 30:
        return BUCKET_1_30
    if overdue <= 60:
        return BUCKET_31_60
    if overdue <= 90:
        return BUCKET_61_90
    return BUCKET_90_PLUS


def late_fee(open_balance, overdue, grace_days, rate):
    """Late fee on an open balance once it is past the grace period.

    No fee accrues while a charge is within the grace window or when nothing is
    owed. Past the grace window, the fee is the rate applied to the open balance.
    """
    if open_balance <= ZERO:
        return ZERO
    if overdue <= grace_days:
        return ZERO
    return quantize_money(open_balance * rate)


def total_owed(open_balance, fee):
    """The full amount owed on a charge: its open balance plus any late fee."""
    return quantize_money(open_balance + fee)
