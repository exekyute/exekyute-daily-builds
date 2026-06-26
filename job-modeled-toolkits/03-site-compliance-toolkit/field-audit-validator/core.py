"""Core logic for the Operational Field Audit Validator.

This module holds the pure rules of the tool: the validators that decide whether
a typed answer is acceptable, and the function that formats one finished audit
into a single line for the log. Keeping these here, separate from the interactive
prompts in audit_cli.py, means each rule can be tested on its own without anyone
having to type at a keyboard.

The job, in plain terms:
    one typed answer   ->   either a clean value, or a clear reason it is not valid

Each validator returns a pair (value, error):
  on success the value is filled in and error is None,
  on failure the value is None and error is a short, friendly message.
"""

from datetime import date
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

# Quantities (like a meter reading) are kept to two decimal places.
QUANTITY_PLACES = Decimal("0.01")


def _clean(text):
    """Trim spaces from a value, treating None as an empty string."""
    if text is None:
        return ""
    return str(text).strip()


def format_quantity(value):
    """Return a Decimal as a plain fixed-point string, for example '12.50'."""
    rounded = value.quantize(QUANTITY_PLACES, rounding=ROUND_HALF_UP)
    return f"{rounded:.2f}"


# ---------------------------------------------------------------------------
# The validators. Each takes the raw typed text and returns (value, error).
# ---------------------------------------------------------------------------

def validate_text(raw):
    """Accept any non-empty text once surrounding spaces are removed."""
    value = _clean(raw)
    if value == "":
        return None, "this cannot be blank, please type a value"
    return value, None


def validate_date(raw):
    """Accept a date strictly as YYYY-MM-DD and return it in that same form.

    We insist on the YYYY-MM-DD shape (with leading zeros) so the recorded date
    is never ambiguous.
    """
    value = _clean(raw)
    parts = value.split("-")
    if len(parts) != 3:
        return None, "use the form YYYY-MM-DD, for example 2026-06-06"
    year, month, day = parts
    if len(year) != 4 or len(month) != 2 or len(day) != 2:
        return None, "use the form YYYY-MM-DD, for example 2026-06-06"
    if not (year.isdigit() and month.isdigit() and day.isdigit()):
        return None, "use the form YYYY-MM-DD, for example 2026-06-06"
    try:
        real = date(int(year), int(month), int(day))
    except ValueError:
        return None, f"'{value}' is not a real calendar date"
    return real.isoformat(), None


def validate_number(raw):
    """Accept a non-negative number and return it as a Decimal."""
    value = _clean(raw)
    if value == "":
        return None, "please type a number, for example 12.5"
    try:
        amount = Decimal(value)
    except InvalidOperation:
        return None, f"'{value}' is not a number, please type a number like 12.5"
    if amount < 0:
        return None, "the value cannot be negative"
    return amount, None


def validate_choice(raw, choices):
    """Accept one of a fixed set of choices, ignoring case.

    Returns the choice in its canonical spelling (as listed in choices).
    """
    value = _clean(raw).lower()
    for choice in choices:
        if value == choice.lower():
            return choice, None
    return None, "please enter one of: " + ", ".join(choices)


# ---------------------------------------------------------------------------
# Dispatch: validate one answer against the rule named by its question.
# ---------------------------------------------------------------------------

def validate_answer(question, raw):
    """Validate a raw answer using the validator named by question['type']."""
    kind = question["type"]
    if kind == "text":
        return validate_text(raw)
    if kind == "date":
        return validate_date(raw)
    if kind == "number":
        return validate_number(raw)
    if kind == "choice":
        return validate_choice(raw, question["choices"])
    raise ValueError(f"unknown question type: {kind}")


# ---------------------------------------------------------------------------
# Turning a finished set of answers into one log line.
# ---------------------------------------------------------------------------

def _format_value(question, value):
    """Render one stored answer as text for the log line."""
    if question["type"] == "number":
        return format_quantity(value)
    text = str(value)
    # The log is pipe-delimited, so a stray pipe or newline in free text would
    # break the columns. Replace them with a space.
    return text.replace("|", " ").replace("\n", " ").replace("\r", " ").strip()


def format_record(questions, answers, timestamp):
    """Build one pipe-delimited log line: timestamp first, then each answer.

    timestamp is passed in as a string so the caller controls it (and tests can
    pin it to a fixed value).
    """
    fields = [timestamp]
    for question in questions:
        fields.append(_format_value(question, answers[question["key"]]))
    return " | ".join(fields)
