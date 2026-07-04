"""Input validation for the grant compliance engine.

Three files are checked before any drawdown is computed: the award budget by
category, the spending transactions, and the reporting schedule. A row that breaks
a rule is rejected with a clear message naming the row.
"""

from decimal import Decimal, InvalidOperation

AWARD_FIELDS = ["category", "budget"]
TXN_FIELDS = ["period", "category", "amount"]
DEADLINE_FIELDS = ["report", "due_period", "submitted"]
YES_NO = {"yes": True, "no": False}


class ValidationError(Exception):
    """Raised when a row fails a validation rule."""


def _decimal(value, field, label):
    try:
        parsed = Decimal(str(value).strip())
    except (InvalidOperation, ValueError):
        raise ValidationError("%s: %s must be a number, got %r" % (label, field, value))
    return parsed


def _int(value, field, label):
    try:
        return int(str(value).strip())
    except ValueError:
        raise ValidationError("%s: %s must be a whole number, got %r" % (label, field, value))


def _require_fields(row, fields, label):
    missing = [f for f in fields if f not in row or str(row[f]).strip() == ""]
    if missing:
        raise ValidationError("%s: missing required field(s): %s" % (label, ", ".join(missing)))


def validate_award_row(row):
    """Validate one award-budget row and return (category, Decimal budget)."""
    label = "Award category %s" % (str(row.get("category", "")).strip() or "(missing category)")
    _require_fields(row, AWARD_FIELDS, label)
    budget = _decimal(row["budget"], "budget", label)
    if budget <= 0:
        raise ValidationError("%s: budget must be greater than zero" % label)
    return str(row["category"]).strip(), budget


def validate_txn_row(row):
    """Validate one transaction row and return it parsed into typed values."""
    label = "Transaction %s" % (str(row.get("category", "")).strip() or "(missing category)")
    _require_fields(row, TXN_FIELDS, label)
    period = _int(row["period"], "period", label)
    if period <= 0:
        raise ValidationError("%s: period must be a positive period number" % label)
    amount = _decimal(row["amount"], "amount", label)
    if amount <= 0:
        raise ValidationError("%s: amount must be greater than zero" % label)
    return {"period": period, "category": str(row["category"]).strip(), "amount": amount}


def validate_deadline_row(row):
    """Validate one reporting-schedule row and return it parsed into typed values."""
    label = "Report %s" % (str(row.get("report", "")).strip() or "(missing report)")
    _require_fields(row, DEADLINE_FIELDS, label)
    due_period = _int(row["due_period"], "due_period", label)
    if due_period <= 0:
        raise ValidationError("%s: due_period must be a positive period number" % label)
    submitted_text = str(row["submitted"]).strip().lower()
    if submitted_text not in YES_NO:
        raise ValidationError("%s: submitted must be yes or no, got %r" % (label, row["submitted"]))
    return {"report": str(row["report"]).strip(), "due_period": due_period, "submitted": YES_NO[submitted_text]}
