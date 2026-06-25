"""Pure allocation math for a fund capital call.

This module holds the calculation only. It does not read files, print, or touch
the command line. Every function takes plain values and returns plain values, so
the logic can be read and tested on its own.

Money is handled exactly. Dollar amounts are converted to whole cents (integers)
before anything is split, the split is reconciled with the largest-remainder
method, and the result is converted back to dollars at the end. Because the
reconciliation works in whole cents, the per-investor called amounts always add
up to the call total to the penny, with nothing lost or gained.
"""

from decimal import Decimal, ROUND_HALF_UP, ROUND_FLOOR

# A two-decimal "cents" quantum used whenever a dollar value is finalised.
CENTS = Decimal("0.01")
WHOLE = Decimal("1")


def dollars_to_cents(amount):
    """Convert a Decimal dollar amount to a whole number of cents.

    Uses ROUND_HALF_UP so a half cent always rounds up, which matches how a
    person would round money by hand.
    """
    return int((amount * 100).quantize(WHOLE, rounding=ROUND_HALF_UP))


def cents_to_dollars(cents):
    """Convert a whole number of cents back to a two-decimal dollar amount."""
    return (Decimal(cents) / 100).quantize(CENTS)


def allocate_call(call_total, commitments):
    """Split a capital call across investors pro-rata by commitment.

    Arguments:
        call_total: a Decimal dollar amount for the whole call (must be > 0).
        commitments: a list of (investor_name, commitment_decimal) pairs, in the
            order they should appear in the output. Commitments must be >= 0 and
            must not all be zero.

    Returns:
        A list of dicts, one per investor, in the same order as the input. Each
        dict has: investor, commitment (Decimal, 2dp), ownership_pct (Decimal,
        4dp) and called_amount (Decimal, 2dp). The called amounts always sum to
        call_total exactly.
    """
    call_cents = dollars_to_cents(call_total)
    total_commitment = sum(commitment for _, commitment in commitments)

    working = []
    for name, commitment in commitments:
        # Exact (fractional) cents this investor is owed before rounding.
        exact_cents = Decimal(call_cents) * commitment / total_commitment
        rounded_cents = int(exact_cents.quantize(WHOLE, rounding=ROUND_HALF_UP))
        floor_cents = int(exact_cents.to_integral_value(rounding=ROUND_FLOOR))
        remainder = exact_cents - floor_cents  # the dropped fraction, in [0, 1)
        ownership = (commitment / total_commitment * 100).quantize(
            Decimal("0.0001"), rounding=ROUND_HALF_UP
        )
        working.append(
            {
                "name": name,
                "commitment": commitment,
                "ownership": ownership,
                "remainder": remainder,
                "cents": rounded_cents,
            }
        )

    # After rounding, the parts may be a few cents short of or over the call.
    # Hand out (or take back) one cent at a time using the largest-remainder
    # method so the totals reconcile exactly.
    difference = call_cents - sum(row["cents"] for row in working)
    if difference > 0:
        # We rounded down overall. Give the spare cents to the largest dropped
        # fractions first. Ties go to the larger commitment, then to name order.
        order = sorted(
            working, key=lambda row: (-row["remainder"], -row["commitment"], row["name"])
        )
        for row in order[:difference]:
            row["cents"] += 1
    elif difference < 0:
        # We rounded up overall. Take the extra cents back from the smallest
        # dropped fractions first, using the same deterministic tie-break.
        order = sorted(
            working, key=lambda row: (row["remainder"], -row["commitment"], row["name"])
        )
        for row in order[: -difference]:
            row["cents"] -= 1

    return [
        {
            "investor": row["name"],
            "commitment": row["commitment"].quantize(CENTS),
            "ownership_pct": row["ownership"],
            "called_amount": cents_to_dollars(row["cents"]),
        }
        for row in working
    ]
