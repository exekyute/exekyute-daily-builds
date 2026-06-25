"""Pure business logic for the rent roll and proration calculator.

This module holds the money and date math only. It does not read files, print,
parse raw CSV text, or touch the command line. Every function takes already-typed
values (Decimal money, date objects, plain integers) and returns a value, which
keeps the rules easy to test with fixed numbers and easy to reuse from the thin
CLI wrapper in cli.py and the validation layer in rent_roll_validation.py.

All money math uses decimal.Decimal with ROUND_HALF_UP, quantized to cents, so
results are exact and never appear in scientific notation. Proration counts the
actual days a unit is occupied against the actual number of days in the billing
month, so February and a 31-day month are treated on their own terms.
"""

import calendar
from datetime import date
from decimal import Decimal, ROUND_HALF_UP

# Money lands on cents (two places), rounded half up.
MONEY = Decimal("0.01")
ZERO = Decimal("0.00")


def quantize_money(value):
    """Round a Decimal to cents, half up."""
    return value.quantize(MONEY, rounding=ROUND_HALF_UP)


def days_in_month(year, month):
    """Actual number of days in the given month, for example 28, 30, or 31."""
    return calendar.monthrange(year, month)[1]


def occupied_days(year, month, move_in, move_out):
    """Count the days a unit is occupied inside the billing month, inclusive.

    The occupied span is clamped to the month. A move-in before the month, or
    no move-in at all, starts on the first. A move-out after the month, or no
    move-out at all, runs to the last day. A lease that is not active in the
    month at all (it ended before the month or started after it) returns 0.
    """
    total = days_in_month(year, month)
    month_first = date(year, month, 1)
    month_last = date(year, month, total)

    start = move_in if (move_in is not None and move_in > month_first) else month_first
    end = move_out if (move_out is not None and move_out < month_last) else month_last

    if start > end:
        return 0
    return (end - start).days + 1


def prorate_rent(monthly_rent, occupied, total_days):
    """Rent owed for the occupied days, rounded to cents.

    A full month (occupied days equal to the days in the month) bills the whole
    monthly rent with no division, so a full-month lease is never a cent off from
    rounding. A zero-day span bills nothing.
    """
    if occupied <= 0:
        return ZERO
    if occupied >= total_days:
        return quantize_money(monthly_rent)
    return quantize_money(monthly_rent * Decimal(occupied) / Decimal(total_days))


def late_fee(overdue_balance, rate):
    """Late fee on an overdue balance, rounded to cents. Zero when nothing is overdue."""
    if overdue_balance <= ZERO:
        return ZERO
    return quantize_money(overdue_balance * rate)


def amount_due(prorated_rent, overdue_balance, fee):
    """Total a unit owes this month: prorated rent plus any overdue balance plus the late fee."""
    return quantize_money(prorated_rent + overdue_balance + fee)
