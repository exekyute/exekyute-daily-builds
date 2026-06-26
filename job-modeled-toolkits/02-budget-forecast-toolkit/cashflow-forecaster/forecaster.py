"""Arithmetic moving averages and a cash runway projection.

Two plain averages are computed over the most recent window of periods: a simple
moving average (every period weighted equally) and a weighted moving average (the
most recent period weighted heaviest). Each average is carried forward across the
upcoming quarter to project the ending cash balance and the runway in months. All
math uses decimal.Decimal rounded half up to cents.
"""

from decimal import Decimal, ROUND_HALF_UP

CENTS = Decimal("0.01")


def format_amount(value):
    """Return a fixed-point string for a Decimal, never scientific notation."""
    return f"{value.quantize(CENTS, rounding=ROUND_HALF_UP):f}"


def has_enough_data(records, window):
    """True when there are at least `window` records to average over."""
    return len(records) >= window


def simple_moving_average(flows, window):
    """Mean of the last `window` net cash flows."""
    recent = flows[-window:]
    total = sum(recent, Decimal("0"))
    return (total / Decimal(window)).quantize(CENTS, rounding=ROUND_HALF_UP)


def weighted_moving_average(flows, window):
    """Weighted mean of the last `window` flows, most recent weighted heaviest.

    Weights are 1, 2, ... window across the window from oldest to newest, so the
    newest period carries the largest weight.
    """
    recent = flows[-window:]
    weighted_sum = Decimal("0")
    weight_total = 0
    for position, value in enumerate(recent, start=1):
        weighted_sum += value * position
        weight_total += position
    return (weighted_sum / Decimal(weight_total)).quantize(
        CENTS, rounding=ROUND_HALF_UP
    )


def next_periods(last_period, count):
    """Return the next `count` period labels after last_period.

    Understands YYYY-MM labels and rolls the month and year forward. Falls back
    to 'Next 1', 'Next 2', ... when the label is not in YYYY-MM form.
    """
    try:
        year_text, month_text = last_period.split("-")
        year = int(year_text)
        month = int(month_text)
        if not 1 <= month <= 12:
            raise ValueError
    except (ValueError, AttributeError):
        return [f"Next {index}" for index in range(1, count + 1)]

    periods = []
    for _ in range(count):
        month += 1
        if month > 12:
            month = 1
            year += 1
        periods.append(f"{year:04d}-{month:02d}")
    return periods


def project(starting_cash, average, periods):
    """Carry `average` forward across the periods, returning running balances.

    Each row is a dict with the period label, the projected net cash flow (the
    average), and the projected ending cash after that period.
    """
    rows = []
    balance = starting_cash
    for period in periods:
        balance = (balance + average).quantize(CENTS, rounding=ROUND_HALF_UP)
        rows.append({"period": period, "flow": average, "balance": balance})
    return rows


def runway_months(starting_cash, average):
    """Months of cash left at this average burn, or None when not net-negative.

    Returns None when the average net cash flow is zero or positive, since cash
    is not being drawn down.
    """
    if average >= 0:
        return None
    return (starting_cash / -average).quantize(CENTS, rounding=ROUND_HALF_UP)
