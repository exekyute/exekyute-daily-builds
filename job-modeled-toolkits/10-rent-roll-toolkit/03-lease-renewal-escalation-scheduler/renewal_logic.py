"""Pure business logic for the lease renewal and escalation scheduler.

This module holds the date and money math only. It does not read files, print, or
touch the command line, which keeps the rules easy to test with fixed dates and
easy to reuse from the thin CLI wrapper in cli.py and the validation layer in
renewal_validation.py.

Money uses decimal.Decimal with ROUND_HALF_UP, quantized to cents. Dates use
datetime and calendar, and every date is treated as a plain calendar day. Adding
months clamps to the last valid day of the target month, so the end of a long
month never rolls forward into the next one.
"""

import calendar
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP

MONEY = Decimal("0.01")

# Status names for a lease, decided against the as-of date and the notice window.
STATUS_EXPIRED = "expired"
STATUS_DUE_NOW = "due_now"
STATUS_UPCOMING = "upcoming"


def quantize_money(value):
    """Round a Decimal to cents, half up."""
    return value.quantize(MONEY, rounding=ROUND_HALF_UP)


def add_months(start, months):
    """Return the date `months` calendar months after `start`.

    The day is clamped to the last day of the target month, so adding one month
    to January 31 gives February 28 (or 29 in a leap year) rather than rolling
    into March.
    """
    total = start.month - 1 + months
    year = start.year + total // 12
    month = total % 12 + 1
    last_day = calendar.monthrange(year, month)[1]
    return date(year, month, min(start.day, last_day))


def escalate_rent(monthly_rent, escalation_rate):
    """Rent for the next term after applying the escalation rate, rounded to cents."""
    return quantize_money(monthly_rent * (Decimal("1") + escalation_rate))


def renewal_window(lease_end, term_months):
    """The next lease term, as (renewal_start, renewal_end).

    The new term starts the day after the current lease ends and runs for the
    given number of months, ending the day before that span completes.
    """
    renewal_start = lease_end + timedelta(days=1)
    renewal_end = add_months(renewal_start, term_months) - timedelta(days=1)
    return renewal_start, renewal_end


def notice_due_date(lease_end, notice_days):
    """The date a renewal notice must go out: that many days before the lease ends."""
    return lease_end - timedelta(days=notice_days)


def days_between(start, end):
    """Whole days from start to end. Negative when end is before start."""
    return (end - start).days


def status_for(lease_end, as_of, notice_due):
    """Classify a lease against the as-of date.

    - expired: the lease has already ended.
    - due_now: the lease is still active but the notice date has arrived or passed.
    - upcoming: the lease is active and the notice date is still in the future.
    """
    if lease_end < as_of:
        return STATUS_EXPIRED
    if as_of >= notice_due:
        return STATUS_DUE_NOW
    return STATUS_UPCOMING
