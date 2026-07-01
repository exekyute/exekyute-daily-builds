"""Input validation for the SOW tracker.

Two files are checked before any earned value is computed: the milestones that
make up the SOW, and the effort logged against them. A row that breaks a rule is
rejected with a clear message naming the milestone or the effort entry.
"""

from decimal import Decimal, InvalidOperation

MILESTONE_FIELDS = ["milestone_id", "name", "budget", "complete_week"]
EFFORT_FIELDS = ["week", "milestone_id", "hours", "rate"]


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


def validate_milestone_row(row):
    """Validate one milestone row and return it parsed into typed values."""
    label = "Milestone %s" % (str(row.get("milestone_id", "")).strip() or "(missing id)")
    _require_fields(row, MILESTONE_FIELDS, label)

    budget = _decimal(row["budget"], "budget", label)
    if budget <= 0:
        raise ValidationError("%s: budget must be greater than zero" % label)

    complete_week = _int(row["complete_week"], "complete_week", label)
    if complete_week <= 0:
        raise ValidationError("%s: complete_week must be a positive week number" % label)

    return {
        "milestone_id": str(row["milestone_id"]).strip(),
        "name": str(row["name"]).strip(),
        "budget": budget,
        "complete_week": complete_week,
    }


def validate_effort_row(row, known_milestones):
    """Validate one effort row and return it parsed into typed values."""
    label = "Effort week %s" % (str(row.get("week", "")).strip() or "(missing week)")
    _require_fields(row, EFFORT_FIELDS, label)

    week = _int(row["week"], "week", label)
    if week <= 0:
        raise ValidationError("%s: week must be a positive week number" % label)

    milestone_id = str(row["milestone_id"]).strip()
    if milestone_id not in known_milestones:
        raise ValidationError(
            "%s: milestone_id %r is not in the milestones file" % (label, milestone_id)
        )

    hours = _decimal(row["hours"], "hours", label)
    if hours < 0:
        raise ValidationError("%s: hours cannot be negative" % label)

    rate = _decimal(row["rate"], "rate", label)
    if rate < 0:
        raise ValidationError("%s: rate cannot be negative" % label)

    return {"week": week, "milestone_id": milestone_id, "hours": hours, "rate": rate}


def validate_holdback_rate(value):
    """Validate the holdback rate, a share between 0 and 1."""
    rate = _decimal(value, "holdback_rate", "Holdback")
    if rate < 0 or rate > 1:
        raise ValidationError("Holdback: holdback_rate must be between 0 and 1, got %s" % rate)
    return rate
