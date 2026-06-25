"""Validation for raw timesheet rows before any money is calculated.

Each function returns a list of human-readable error strings. An empty list
means the input is clean. Validation never raises on bad employee data; it
reports the problem so the command-line wrapper can skip that row and keep
processing the rest of the run.
"""

from decimal import Decimal, InvalidOperation

REQUIRED_FIELDS = [
    "employee_id",
    "name",
    "pay_type",
    "rate",
    "hours_worked",
    "pretax_deductions",
    "posttax_deductions",
]

NUMERIC_FIELDS = [
    "rate",
    "hours_worked",
    "pretax_deductions",
    "posttax_deductions",
]

VALID_PAY_TYPES = {"hourly", "salaried"}

# Key used by csv.DictReader to collect any values beyond the header columns.
EXTRA_FIELD_KEY = "_extra"


def validate_header(fieldnames):
    """Return errors describing any missing or unexpected columns."""
    if not fieldnames:
        return ["File has no header row."]
    found = [name.strip() for name in fieldnames]
    errors = []
    missing = [name for name in REQUIRED_FIELDS if name not in found]
    extra = [name for name in found if name not in REQUIRED_FIELDS]
    if missing:
        errors.append("Missing column(s): " + ", ".join(missing))
    if extra:
        errors.append("Unexpected column(s): " + ", ".join(extra))
    return errors


def _is_nonnegative_number(value):
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return False
    return number >= 0


def validate_row(row):
    """Return a list of errors for one timesheet row (empty list means clean)."""
    errors = []

    for field in REQUIRED_FIELDS:
        value = row.get(field)
        if value is None or str(value).strip() == "":
            errors.append("Missing value for '%s'" % field)

    if row.get(EXTRA_FIELD_KEY):
        errors.append("Row has more fields than the header expects")

    pay_type = (row.get("pay_type") or "").strip().lower()
    if pay_type and pay_type not in VALID_PAY_TYPES:
        errors.append("Unknown pay_type '%s' (expected hourly or salaried)" % row.get("pay_type"))

    for field in NUMERIC_FIELDS:
        value = row.get(field)
        if value is not None and str(value).strip() != "" and not _is_nonnegative_number(value):
            errors.append("Field '%s' must be a non-negative number (got '%s')" % (field, value))

    return errors
