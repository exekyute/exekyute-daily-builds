"""Input validation for the cost-allocation engine.

Two files are checked before any cost is split: the pool of shared cost items and
the drivers that the split is based on. A row that breaks a rule is rejected with a
clear message naming the item or the department.
"""

from decimal import Decimal, InvalidOperation

POOL_FIELDS = ["item", "amount"]
DRIVER_FIELDS = ["department", "driver_value"]


class ValidationError(Exception):
    """Raised when a row fails a validation rule."""


def _decimal(value, field, label):
    try:
        parsed = Decimal(str(value).strip())
    except (InvalidOperation, ValueError):
        raise ValidationError("%s: %s must be a number, got %r" % (label, field, value))
    return parsed


def _require_fields(row, fields, label):
    missing = [f for f in fields if f not in row or str(row[f]).strip() == ""]
    if missing:
        raise ValidationError("%s: missing required field(s): %s" % (label, ", ".join(missing)))


def validate_pool_row(row):
    """Validate one pool row and return (item, Decimal amount)."""
    label = "Pool item %s" % (str(row.get("item", "")).strip() or "(missing item)")
    _require_fields(row, POOL_FIELDS, label)
    amount = _decimal(row["amount"], "amount", label)
    if amount <= 0:
        raise ValidationError("%s: amount must be greater than zero" % label)
    return str(row["item"]).strip(), amount


def validate_driver_row(row):
    """Validate one driver row and return (department, Decimal driver value)."""
    label = "Driver %s" % (str(row.get("department", "")).strip() or "(missing department)")
    _require_fields(row, DRIVER_FIELDS, label)
    driver = _decimal(row["driver_value"], "driver_value", label)
    if driver < 0:
        raise ValidationError("%s: driver_value cannot be negative" % label)
    return str(row["department"]).strip(), driver
