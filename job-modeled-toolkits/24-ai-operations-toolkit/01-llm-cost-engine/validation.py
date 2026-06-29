"""Input validation for the LLM cost engine.

Every raw CSV row is checked here before any cost is calculated. A row that breaks
a rule is rejected with a clear message naming the record and the field, so a bad
file is caught at the door rather than producing wrong numbers.

The four inputs each have their own parser:

  usage_log.csv   - one row per usage record (team, project, model, tokens).
  price_book.csv  - the rate card, one row per model.
  shared_costs.csv- the monthly shared pool, one row per cost item.
  budgets.csv     - one row per team with its monthly budget.
"""

from datetime import datetime
from decimal import Decimal, InvalidOperation

USAGE_FIELDS = [
    "record_id",
    "usage_date",
    "team",
    "project",
    "model",
    "requests",
    "input_tokens",
    "cached_input_tokens",
    "output_tokens",
]

PRICE_FIELDS = ["model", "input_per_1m", "cached_input_per_1m", "output_per_1m"]
SHARED_FIELDS = ["item", "amount"]
BUDGET_FIELDS = ["team", "monthly_budget"]


class ValidationError(Exception):
    """Raised when a row fails a validation rule."""


def _decimal(value, field, label):
    try:
        parsed = Decimal(str(value).strip())
    except (InvalidOperation, ValueError):
        raise ValidationError("%s: %s must be a number, got %r" % (label, field, value))
    return parsed


def _nonneg_int(value, field, label):
    text = str(value).strip()
    try:
        parsed = int(text)
    except ValueError:
        raise ValidationError(
            "%s: %s must be a whole number, got %r" % (label, field, value)
        )
    if parsed < 0:
        raise ValidationError("%s: %s cannot be negative" % (label, field))
    return parsed


def _require_fields(row, fields, label):
    missing = [f for f in fields if f not in row or str(row[f]).strip() == ""]
    if missing:
        raise ValidationError(
            "%s: missing required field(s): %s" % (label, ", ".join(missing))
        )


def validate_usage_row(row, known_models):
    """Validate one usage row and return it parsed into typed values.

    Token fields become integers, the date becomes a datetime.date, and the model
    is checked against the price book. Cached input tokens cannot exceed the input
    tokens they are drawn from. Raises ValidationError on the first rule a row breaks.
    """
    label = "Usage %s" % (str(row.get("record_id", "")).strip() or "(missing id)")
    _require_fields(row, USAGE_FIELDS, label)

    model = str(row["model"]).strip()
    if model not in known_models:
        raise ValidationError(
            "%s: unknown model %r, expected one of %s"
            % (label, model, ", ".join(sorted(known_models)))
        )

    try:
        usage_date = datetime.strptime(str(row["usage_date"]).strip(), "%Y-%m-%d").date()
    except ValueError:
        raise ValidationError(
            "%s: usage_date must be in YYYY-MM-DD format, got %r"
            % (label, row["usage_date"])
        )

    requests = _nonneg_int(row["requests"], "requests", label)
    input_tokens = _nonneg_int(row["input_tokens"], "input_tokens", label)
    cached_input_tokens = _nonneg_int(row["cached_input_tokens"], "cached_input_tokens", label)
    output_tokens = _nonneg_int(row["output_tokens"], "output_tokens", label)

    if cached_input_tokens > input_tokens:
        raise ValidationError(
            "%s: cached_input_tokens (%d) cannot exceed input_tokens (%d)"
            % (label, cached_input_tokens, input_tokens)
        )

    return {
        "record_id": str(row["record_id"]).strip(),
        "usage_date": usage_date,
        "team": str(row["team"]).strip(),
        "project": str(row["project"]).strip(),
        "model": model,
        "requests": requests,
        "input_tokens": input_tokens,
        "cached_input_tokens": cached_input_tokens,
        "output_tokens": output_tokens,
    }


def validate_price_row(row):
    """Validate one price-book row and return (model, rates dict of Decimals)."""
    label = "Price %s" % (str(row.get("model", "")).strip() or "(missing model)")
    _require_fields(row, PRICE_FIELDS, label)
    model = str(row["model"]).strip()
    rates = {}
    for field in ("input_per_1m", "cached_input_per_1m", "output_per_1m"):
        rate = _decimal(row[field], field, label)
        if rate < 0:
            raise ValidationError("%s: %s cannot be negative" % (label, field))
        rates[field] = rate
    return model, rates


def validate_shared_row(row):
    """Validate one shared-cost row and return (item, Decimal amount)."""
    label = "Shared cost %s" % (str(row.get("item", "")).strip() or "(missing item)")
    _require_fields(row, SHARED_FIELDS, label)
    amount = _decimal(row["amount"], "amount", label)
    if amount < 0:
        raise ValidationError("%s: amount cannot be negative" % label)
    return str(row["item"]).strip(), amount


def validate_budget_row(row):
    """Validate one budget row and return (team, Decimal monthly budget)."""
    label = "Budget %s" % (str(row.get("team", "")).strip() or "(missing team)")
    _require_fields(row, BUDGET_FIELDS, label)
    budget = _decimal(row["monthly_budget"], "monthly_budget", label)
    if budget <= 0:
        raise ValidationError("%s: monthly_budget must be greater than zero" % label)
    return str(row["team"]).strip(), budget
