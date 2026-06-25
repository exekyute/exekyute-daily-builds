"""Input validation for the Milestone-Driven Burn Rate Tracker.

Each function returns a cleaned value or raises InvalidPhase with a plain,
specific message. The logic layer catches these so one bad phase row is reported
and counted instead of crashing the run.
"""

from decimal import Decimal, InvalidOperation


class InvalidPhase(Exception):
    """Raised when a phase update fails a validation rule."""


def validate_phase_name(raw):
    """A phase name must be present and non-blank."""
    name = (raw or "").strip()
    if not name:
        raise InvalidPhase("phase name is blank")
    return name


def validate_cost(raw):
    """A phase cost must be numeric and greater than zero."""
    text = (raw or "").strip()
    if not text:
        raise InvalidPhase("cost is blank")
    try:
        cost = Decimal(text)
    except InvalidOperation:
        raise InvalidPhase(f"cost '{text}' is not a number")
    if cost <= 0:
        raise InvalidPhase(f"cost '{text}' is not greater than zero")
    return cost
