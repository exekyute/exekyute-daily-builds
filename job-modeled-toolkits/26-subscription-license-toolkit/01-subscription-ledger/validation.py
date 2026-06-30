"""Input validation for the subscription ledger.

Every raw CSV row is checked here before any cost is worked out. A row that breaks
a rule is rejected with a clear message naming the subscription and the field.
"""

from datetime import datetime
from decimal import Decimal, InvalidOperation

SUB_FIELDS = [
    "sub_id",
    "vendor",
    "plan",
    "plan_type",
    "monthly_unit_cost",
    "seats_owned",
    "seats_used",
    "renewal_date",
    "auto_renew",
]

PLAN_TYPES = {"per_seat", "flat"}
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


def validate_sub_row(row):
    """Validate one subscription row and return it parsed into typed values."""
    label = "Subscription %s" % (str(row.get("sub_id", "")).strip() or "(missing id)")
    _require_fields(row, SUB_FIELDS, label)

    plan_type = str(row["plan_type"]).strip()
    if plan_type not in PLAN_TYPES:
        raise ValidationError(
            "%s: plan_type must be per_seat or flat, got %r" % (label, plan_type)
        )

    monthly_unit_cost = _decimal(row["monthly_unit_cost"], "monthly_unit_cost", label)
    if monthly_unit_cost < 0:
        raise ValidationError("%s: monthly_unit_cost cannot be negative" % label)

    seats_owned = _int(row["seats_owned"], "seats_owned", label)
    seats_used = _int(row["seats_used"], "seats_used", label)
    if seats_owned <= 0:
        raise ValidationError("%s: seats_owned must be greater than zero" % label)
    if seats_used < 0:
        raise ValidationError("%s: seats_used cannot be negative" % label)
    if seats_used > seats_owned:
        raise ValidationError(
            "%s: seats_used (%d) cannot exceed seats_owned (%d)" % (label, seats_used, seats_owned)
        )

    try:
        renewal_date = datetime.strptime(str(row["renewal_date"]).strip(), "%Y-%m-%d").date()
    except ValueError:
        raise ValidationError(
            "%s: renewal_date must be in YYYY-MM-DD format, got %r" % (label, row["renewal_date"])
        )

    auto_renew_text = str(row["auto_renew"]).strip().lower()
    if auto_renew_text not in YES_NO:
        raise ValidationError("%s: auto_renew must be yes or no, got %r" % (label, row["auto_renew"]))

    return {
        "sub_id": str(row["sub_id"]).strip(),
        "vendor": str(row["vendor"]).strip(),
        "plan": str(row["plan"]).strip(),
        "plan_type": plan_type,
        "monthly_unit_cost": monthly_unit_cost,
        "seats_owned": seats_owned,
        "seats_used": seats_used,
        "renewal_date": renewal_date,
        "auto_renew": YES_NO[auto_renew_text],
    }
