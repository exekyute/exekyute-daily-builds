"""Input validation for the job-cost engine.

Every raw CSV row is checked here before any revenue is recognized. A row that
breaks a rule is rejected with a clear message naming the job and the field, so a
bad file is caught at the door rather than producing a wrong WIP schedule.

The one input is contracts.csv, one row per job with its contract value, the
current estimated total cost, the cost booked to date, and the amount billed.
"""

from decimal import Decimal, InvalidOperation

CONTRACT_FIELDS = [
    "job_id",
    "job_name",
    "contract_value",
    "estimated_total_cost",
    "cost_to_date",
    "billed_to_date",
]


class ValidationError(Exception):
    """Raised when a row fails a validation rule."""


def _decimal(value, field, label):
    try:
        parsed = Decimal(str(value).strip())
    except (InvalidOperation, ValueError):
        raise ValidationError("%s: %s must be a number, got %r" % (label, field, value))
    if not parsed.is_finite():
        raise ValidationError("%s: %s must be a finite number, got %r" % (label, field, value))
    return parsed


def _require_fields(row, fields, label):
    missing = [f for f in fields if f not in row or str(row[f]).strip() == ""]
    if missing:
        raise ValidationError(
            "%s: missing required field(s): %s" % (label, ", ".join(missing))
        )


def validate_contract_row(row):
    """Validate one contract row and return it parsed into typed values.

    Money fields become Decimals and the identifiers become trimmed strings.
    The rules:
      contract_value         greater than zero
      estimated_total_cost   greater than zero
      cost_to_date           zero or more
      billed_to_date         zero or more
      estimated_total_cost   not less than cost_to_date, so a job cannot report a
                             cost overrun past its own estimate without the
                             estimate being revised first
    Raises ValidationError on the first rule a row breaks.
    """
    label = "Job %s" % (str(row.get("job_id", "")).strip() or "(missing id)")
    _require_fields(row, CONTRACT_FIELDS, label)

    contract_value = _decimal(row["contract_value"], "contract_value", label)
    estimated_total_cost = _decimal(row["estimated_total_cost"], "estimated_total_cost", label)
    cost_to_date = _decimal(row["cost_to_date"], "cost_to_date", label)
    billed_to_date = _decimal(row["billed_to_date"], "billed_to_date", label)

    if contract_value <= 0:
        raise ValidationError("%s: contract_value must be greater than zero" % label)
    if estimated_total_cost <= 0:
        raise ValidationError("%s: estimated_total_cost must be greater than zero" % label)
    if cost_to_date < 0:
        raise ValidationError("%s: cost_to_date cannot be negative" % label)
    if billed_to_date < 0:
        raise ValidationError("%s: billed_to_date cannot be negative" % label)
    if estimated_total_cost < cost_to_date:
        raise ValidationError(
            "%s: estimated_total_cost (%s) cannot be less than cost_to_date (%s); "
            "revise the estimate before recognizing revenue"
            % (label, estimated_total_cost, cost_to_date)
        )

    return {
        "job_id": str(row["job_id"]).strip(),
        "job_name": str(row["job_name"]).strip(),
        "contract_value": contract_value,
        "estimated_total_cost": estimated_total_cost,
        "cost_to_date": cost_to_date,
        "billed_to_date": billed_to_date,
    }
