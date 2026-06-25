"""Input validation for the Benefit Formula Engine.

Every "is this input sane" check lives here, separate from the math. If a value
is bad, these functions raise ValidationError with a plain-language message. The
calculator can then trust whatever it receives.
"""

from decimal import Decimal, InvalidOperation

from plan_rules import PlanRules


class ValidationError(ValueError):
    """Raised when an input fails a business rule or is the wrong type."""


def parse_positive_money(raw, field_name):
    """Turn a raw value into a positive Decimal, or raise ValidationError.

    Accepts ints, floats given as strings, and plain numeric strings. Rejects
    blanks, non-numbers, zero, and negatives, because a salary of zero or less
    is never valid input for a pension calculation.
    """
    text = str(raw).strip()
    if text == "":
        raise ValidationError(f"{field_name} is empty; a positive amount is required.")
    try:
        value = Decimal(text)
    except InvalidOperation:
        raise ValidationError(f"{field_name} is not a number: {raw!r}.")
    if value <= 0:
        raise ValidationError(f"{field_name} must be greater than zero, got {value}.")
    return value


def validate_salary_history(salaries, rules: PlanRules):
    """Check the salary list, then return it as a list of positive Decimals.

    There must be at least as many salary years as the averaging window, because
    you cannot average the best 5 years out of only 3.
    """
    if not salaries:
        raise ValidationError("Salary history is empty; at least one salary is required.")

    cleaned = [
        parse_positive_money(salary, f"Salary #{index + 1}")
        for index, salary in enumerate(salaries)
    ]

    if len(cleaned) < rules.averaging_window:
        raise ValidationError(
            f"Need at least {rules.averaging_window} salary years for the "
            f"averaging window, but only {len(cleaned)} were provided."
        )
    return cleaned


def validate_years_of_service(years, rules: PlanRules):
    """Check years of service and clamp it to the plan's maximum.

    Returns a tuple (credited_service, was_capped) so the caller can report when
    the cap changed the input.
    """
    try:
        value = int(years)
    except (TypeError, ValueError):
        raise ValidationError(f"Years of service must be a whole number, got {years!r}.")
    if value <= 0:
        raise ValidationError(f"Years of service must be greater than zero, got {value}.")

    if value > rules.max_credited_service:
        return rules.max_credited_service, True
    return value, False


def validate_retirement_age(age, rules: PlanRules):
    """Check the retirement age falls inside the plan's allowed window."""
    try:
        value = int(age)
    except (TypeError, ValueError):
        raise ValidationError(f"Retirement age must be a whole number, got {age!r}.")

    if value < rules.earliest_retirement_age:
        raise ValidationError(
            f"Retirement age {value} is below the earliest allowed age of "
            f"{rules.earliest_retirement_age}."
        )
    if value > 71:
        raise ValidationError(f"Retirement age {value} is above the maximum of 71.")
    return value
