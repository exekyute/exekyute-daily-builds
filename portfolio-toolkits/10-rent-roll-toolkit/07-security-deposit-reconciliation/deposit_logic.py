"""Pure business logic for the security deposit reconciliation tool.

This module holds the money math only. It does not read files, print, or touch the
command line, which keeps the rules easy to test with fixed numbers and easy to reuse
from the thin CLI wrapper in cli.py and the validation layer in deposit_validation.py.

Money uses decimal.Decimal with ROUND_HALF_UP, quantized to cents. Reconciliation is
a single, exact subtraction: the deposit held less the itemized deductions, settled as
either a refund owed to the tenant, a balance the tenant still owes, or an even result
when the two match to the cent.
"""

from decimal import Decimal, ROUND_HALF_UP

MONEY = Decimal("0.01")
ZERO = Decimal("0.00")

# The three ways a move-out can settle.
RESULT_REFUND = "refund"
RESULT_BALANCE = "balance"
RESULT_EVEN = "even"


def quantize_money(value):
    """Round a Decimal to cents, half up."""
    return value.quantize(MONEY, rounding=ROUND_HALF_UP)


def total_deductions(unpaid_rent, cleaning, damages):
    """Sum the itemized deductions against a deposit."""
    return quantize_money(unpaid_rent + cleaning + damages)


def settle(deposit_held, deductions):
    """Reconcile a deposit against its deductions.

    Returns (refund_due, balance_owed, result):
    - a positive net is a refund owed to the tenant (balance_owed is 0),
    - a negative net is a balance the tenant still owes (refund_due is 0),
    - a net of exactly 0 is an even result, with neither a refund nor a balance.
    """
    net = quantize_money(deposit_held - deductions)
    if net > ZERO:
        return net, ZERO, RESULT_REFUND
    if net < ZERO:
        return ZERO, -net, RESULT_BALANCE
    return ZERO, ZERO, RESULT_EVEN
