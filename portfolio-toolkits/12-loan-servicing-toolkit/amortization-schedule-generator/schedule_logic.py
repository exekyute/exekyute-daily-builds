"""Pure amortization logic.

Every function here takes plain values and returns plain values. There is no
argument parsing, no file reading, and no printing, so the logic can be tested
on its own. All money is handled with ``decimal.Decimal`` in whole-cent
precision using ``ROUND_HALF_UP``, so amounts never drift into binary-float
artifacts or scientific notation.
"""

from decimal import Decimal, ROUND_HALF_UP

CENTS = Decimal("0.01")


def to_cents(value):
    """Round a Decimal to a two-decimal cent value with ROUND_HALF_UP."""
    return value.quantize(CENTS, rounding=ROUND_HALF_UP)


def monthly_rate(annual_rate_percent):
    """Convert an annual percentage rate into an exact monthly Decimal rate.

    ``12`` (meaning 12%) becomes ``0.01`` per month. The result is kept exact
    (not rounded to cents) because it is a multiplier, not a money amount.
    """
    return Decimal(annual_rate_percent) / Decimal(100) / Decimal(12)


def level_payment(principal, annual_rate_percent, term_months):
    """Compute the level monthly payment, rounded to cents.

    For a zero-rate loan the payment is simply the principal spread evenly over
    the term. Otherwise it uses the standard amortization formula
    ``P * r / (1 - (1 + r) ** -n)``.
    """
    principal = Decimal(principal)
    r = monthly_rate(annual_rate_percent)
    n = int(term_months)

    if r == 0:
        return to_cents(principal / Decimal(n))

    factor = (Decimal(1) + r) ** (-n)
    payment = principal * r / (Decimal(1) - factor)
    return to_cents(payment)


def build_schedule(principal, annual_rate_percent, term_months):
    """Build the full amortization schedule.

    Returns a tuple ``(rows, summary)`` where ``rows`` is a list of dicts with
    keys ``period``, ``payment``, ``interest``, ``principal`` and ``balance``
    (all Decimals quantized to cents), and ``summary`` is a dict with the level
    payment, total interest and total of payments.

    The final period is reconciled: its principal is set to whatever balance
    remains and its payment to interest plus that principal, so the closing
    balance lands on exactly ``0.00`` with no residual cent.
    """
    principal = to_cents(Decimal(principal))
    r = monthly_rate(annual_rate_percent)
    n = int(term_months)
    payment = level_payment(principal, annual_rate_percent, term_months)

    rows = []
    balance = principal
    total_interest = Decimal("0.00")
    total_paid = Decimal("0.00")

    for period in range(1, n + 1):
        interest = to_cents(balance * r)

        if period == n:
            # Reconcile the last period so the balance closes exactly at zero.
            principal_paid = balance
            this_payment = to_cents(interest + principal_paid)
        else:
            this_payment = payment
            principal_paid = to_cents(this_payment - interest)

        balance = to_cents(balance - principal_paid)

        rows.append({
            "period": period,
            "payment": this_payment,
            "interest": interest,
            "principal": principal_paid,
            "balance": balance,
        })

        total_interest = to_cents(total_interest + interest)
        total_paid = to_cents(total_paid + this_payment)

    summary = {
        "level_payment": payment,
        "total_interest": total_interest,
        "total_paid": total_paid,
    }
    return rows, summary
