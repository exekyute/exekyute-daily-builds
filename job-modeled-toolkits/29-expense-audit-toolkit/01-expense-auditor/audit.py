"""Expense and travel policy audit logic.

Pure functions only. Each takes plain values and returns plain values, with no
file or console access. The CLI layer in cli.py reads and writes; the browser
review app in 02 mirrors this same logic to the cent.

Each expense line is checked against the policy and given zero or more flags:

  MILEAGE_MISMATCH - a mileage claim whose amount does not equal kilometres times
                     the prescribed rate.
  OVER_CAP         - a category amount above its daily cap.
  NO_RECEIPT       - an amount above the receipt threshold with no receipt attached.
  DUPLICATE        - the same employee, date, category, and amount appearing more
                     than once.

A line with no flags is approved; a flagged line goes to the review queue.

All money is decimal.Decimal rounded half up to the cent.
"""

from decimal import Decimal, ROUND_HALF_UP

CENT = Decimal("0.01")
MILEAGE_CATEGORY = "Mileage"


def money(value):
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


def mileage_amount(km, rate):
    """The allowed amount for a mileage claim: kilometres times the rate."""
    return money(km * rate)


def duplicate_keys(expenses):
    """The set of (employee, date, category, amount) keys that appear more than once."""
    counts = {}
    for e in expenses:
        key = (e["employee"], e["date"], e["category"], e["amount"])
        counts[key] = counts.get(key, 0) + 1
    return {key for key, count in counts.items() if count > 1}


def computed_amount(expense, policy):
    """The amount the policy expects: the mileage formula for mileage, the claimed
    amount otherwise."""
    if expense["category"] == MILEAGE_CATEGORY:
        return mileage_amount(expense["km"], policy["mileage_rate"])
    return money(expense["amount"])


def flags_for(expense, policy, dup_keys):
    """The list of policy flags on one expense, in a stable order."""
    flags = []
    category = expense["category"]
    amount = money(expense["amount"])

    if category == MILEAGE_CATEGORY:
        if amount != mileage_amount(expense["km"], policy["mileage_rate"]):
            flags.append("MILEAGE_MISMATCH")
    else:
        cap = policy["caps"].get(category)
        if cap is not None and amount > cap:
            flags.append("OVER_CAP")
        if amount > policy["receipt_threshold"] and not expense["receipt"]:
            flags.append("NO_RECEIPT")

    key = (expense["employee"], expense["date"], category, expense["amount"])
    if key in dup_keys:
        flags.append("DUPLICATE")
    return flags


def audit(expenses, policy):
    """Audit every expense and return the rows plus the run totals."""
    dup_keys = duplicate_keys(expenses)
    rows = []
    for e in expenses:
        flags = flags_for(e, policy, dup_keys)
        rows.append({
            "expense_id": e["expense_id"],
            "date": e["date"],
            "employee": e["employee"],
            "category": e["category"],
            "amount": money(e["amount"]),
            "km": e["km"],
            "receipt": "yes" if e["receipt"] else "no",
            "computed_amount": computed_amount(e, policy),
            "flags": flags,
            "status": "Approved" if not flags else "Flagged",
        })

    flagged = [r for r in rows if r["flags"]]
    totals = {
        "total_claimed": money(sum((r["amount"] for r in rows), Decimal("0.00"))),
        "flagged_amount": money(sum((r["amount"] for r in flagged), Decimal("0.00"))),
        "approved_amount": money(sum((r["amount"] for r in rows if not r["flags"]), Decimal("0.00"))),
        "flagged_count": len(flagged),
        "approved_count": len(rows) - len(flagged),
        "over_cap_count": sum(1 for r in rows if "OVER_CAP" in r["flags"]),
        "no_receipt_count": sum(1 for r in rows if "NO_RECEIPT" in r["flags"]),
        "duplicate_count": sum(1 for r in rows if "DUPLICATE" in r["flags"]),
        "mileage_mismatch_count": sum(1 for r in rows if "MILEAGE_MISMATCH" in r["flags"]),
    }
    return {"rows": rows, "totals": totals}
