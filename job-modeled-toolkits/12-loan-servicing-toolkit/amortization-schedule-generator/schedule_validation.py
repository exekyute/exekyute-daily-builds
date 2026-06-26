"""Input validation for the amortization generator.

Validation is kept separate from the math so the rules read in one place. Every
problem is collected in a single pass and returned as a list of messages, so a
caller can show the user everything that is wrong at once rather than failing on
the first issue. Nothing here computes a schedule or touches files.
"""

from decimal import Decimal, InvalidOperation


def _parse_decimal(raw):
    """Parse a value into a Decimal, or return None if it is not a number."""
    try:
        return Decimal(str(raw))
    except (InvalidOperation, ValueError, TypeError):
        return None


def _parse_int(raw):
    """Parse a value into a whole integer, or return None if it is not one.

    A value like ``6.5`` is rejected because a term must be a whole number of
    monthly periods.
    """
    try:
        number = Decimal(str(raw))
    except (InvalidOperation, ValueError, TypeError):
        return None
    if number != number.to_integral_value():
        return None
    return int(number)


def validate_inputs(principal, annual_rate_percent, term_months):
    """Validate the three loan inputs.

    Returns a list of human-readable error messages. An empty list means the
    inputs are valid.
    """
    errors = []

    principal_value = _parse_decimal(principal)
    if principal_value is None:
        errors.append("Principal must be a number, for example 1000.00.")
    elif principal_value <= 0:
        errors.append("Principal must be greater than zero.")

    rate_value = _parse_decimal(annual_rate_percent)
    if rate_value is None:
        errors.append("Annual rate must be a number, for example 12 or 12.5.")
    elif rate_value < 0:
        errors.append("Annual rate must not be negative (zero is allowed).")

    term_value = _parse_int(term_months)
    if term_value is None:
        errors.append("Term must be a whole number of months, for example 6.")
    elif term_value < 1:
        errors.append("Term must be at least 1 month.")

    return errors
