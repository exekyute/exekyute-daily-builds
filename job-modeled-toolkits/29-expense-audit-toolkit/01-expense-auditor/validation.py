"""Input validation for the expense auditor.

The policy file and the expense file are checked before any audit runs. A row that
breaks a rule is rejected with a clear message naming the expense or the policy line.
"""

from datetime import datetime
from decimal import Decimal, InvalidOperation

EXPENSE_FIELDS = ["expense_id", "date", "employee", "category", "amount", "km", "receipt"]
YES_NO = {"yes": True, "no": False}
MILEAGE_CATEGORY = "Mileage"


class ValidationError(Exception):
    """Raised when a row fails a validation rule."""


def _decimal(value, field, label):
    try:
        parsed = Decimal(str(value).strip())
    except (InvalidOperation, ValueError):
        raise ValidationError("%s: %s must be a number, got %r" % (label, field, value))
    return parsed


def _require_fields(row, fields, label):
    missing = [f for f in fields if f not in row or (f != "km" and str(row[f]).strip() == "")]
    if missing:
        raise ValidationError("%s: missing required field(s): %s" % (label, ", ".join(missing)))


def load_policy_rows(rows):
    """Build the policy dict from validated param rows.

    Each row has a param and a value. cap.<Category> rows set a category cap;
    mileage_rate_per_km and receipt_threshold set the two scalar limits.
    """
    policy = {"mileage_rate": None, "receipt_threshold": None, "caps": {}}
    for row in rows:
        param = str(row.get("param", "")).strip()
        if param == "":
            continue
        value = _decimal(row.get("value", ""), "value", "Policy %s" % param)
        if value < 0:
            raise ValidationError("Policy %s: value cannot be negative" % param)
        if param == "mileage_rate_per_km":
            policy["mileage_rate"] = value
        elif param == "receipt_threshold":
            policy["receipt_threshold"] = value
        elif param.startswith("cap."):
            policy["caps"][param[len("cap."):]] = value
        else:
            raise ValidationError("Policy: unknown parameter %r" % param)
    if policy["mileage_rate"] is None:
        raise ValidationError("Policy: mileage_rate_per_km is missing")
    if policy["receipt_threshold"] is None:
        raise ValidationError("Policy: receipt_threshold is missing")
    return policy


def validate_expense_row(row, policy):
    """Validate one expense row and return it parsed into typed values."""
    label = "Expense %s" % (str(row.get("expense_id", "")).strip() or "(missing id)")
    _require_fields(row, EXPENSE_FIELDS, label)

    category = str(row["category"]).strip()
    allowed = set(policy["caps"]) | {MILEAGE_CATEGORY}
    if category not in allowed:
        raise ValidationError(
            "%s: category %r has no policy, expected one of %s"
            % (label, category, ", ".join(sorted(allowed)))
        )

    try:
        date = datetime.strptime(str(row["date"]).strip(), "%Y-%m-%d").date()
    except ValueError:
        raise ValidationError("%s: date must be in YYYY-MM-DD format, got %r" % (label, row["date"]))

    amount = _decimal(row["amount"], "amount", label)
    if amount <= 0:
        raise ValidationError("%s: amount must be greater than zero" % label)

    km_text = str(row.get("km", "")).strip()
    km = _decimal(km_text, "km", label) if km_text != "" else Decimal("0")
    if km < 0:
        raise ValidationError("%s: km cannot be negative" % label)
    if category == MILEAGE_CATEGORY and km <= 0:
        raise ValidationError("%s: a mileage claim needs kilometres above zero" % label)

    receipt_text = str(row["receipt"]).strip().lower()
    if receipt_text not in YES_NO:
        raise ValidationError("%s: receipt must be yes or no, got %r" % (label, row["receipt"]))

    return {
        "expense_id": str(row["expense_id"]).strip(),
        "date": date.isoformat(),
        "employee": str(row["employee"]).strip(),
        "category": category,
        "amount": amount,
        "km": km,
        "receipt": YES_NO[receipt_text],
    }
