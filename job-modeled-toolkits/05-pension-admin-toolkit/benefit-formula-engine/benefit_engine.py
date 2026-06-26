"""Command-line entry point for the Benefit Formula Engine.

This is the thin wrapper: it reads the inputs (CSV file or command-line salaries),
validates them, calls the pure calculator, and prints a readable breakdown. All
the real rules live in plan_rules.py, validators.py, and calculator.py.

Examples
--------
Read salaries from a CSV:
    python benefit_engine.py --salary-file data/sample_salary_history.csv \
        --years-of-service 30 --retirement-age 60

Pass salaries directly:
    python benefit_engine.py --salary 80000 --salary 82000 --salary 85000 \
        --salary 88000 --salary 90000 --years-of-service 30 --retirement-age 65
"""

import argparse
import csv
import sys

from plan_rules import DEFAULT_PLAN
from validators import (
    ValidationError,
    validate_salary_history,
    validate_years_of_service,
    validate_retirement_age,
)
from calculator import calculate_benefit


def read_salaries_from_csv(path):
    """Read a CSV with a `year,annual_salary` header and return the salary column.

    Raising ValidationError here keeps every bad-input message in the same family
    the CLI already knows how to report.
    """
    try:
        with open(path, newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            if reader.fieldnames is None or "annual_salary" not in reader.fieldnames:
                raise ValidationError(
                    f"{path} must have a header row with an 'annual_salary' column."
                )
            return [row["annual_salary"] for row in reader]
    except FileNotFoundError:
        raise ValidationError(f"Salary file not found: {path}")


def build_parser():
    parser = argparse.ArgumentParser(
        description="Calculate a monthly defined-benefit pension payout."
    )
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument(
        "--salary-file",
        help="Path to a CSV with a 'year,annual_salary' header.",
    )
    source.add_argument(
        "--salary",
        action="append",
        dest="salaries",
        help="A single annual salary. Repeat the flag for multiple years.",
    )
    parser.add_argument(
        "--years-of-service",
        required=True,
        help="Whole number of years of credited service.",
    )
    parser.add_argument(
        "--retirement-age",
        required=True,
        help="Age at retirement.",
    )
    return parser


def _format_percent(fraction):
    """Show a Decimal fraction as a plain percent string, no scientific notation.

    Decimal.normalize() can return values like 3E+1; the 'f' format forces normal
    fixed-point digits, so 0.30 prints as 30 rather than 3E+1.
    """
    percent = (fraction * 100).normalize()
    return format(percent, "f")


def format_report(result, rules):
    """Build the printed breakdown as a single string."""
    reduction_percent = _format_percent(result.reduction_fraction)
    accrual_percent = _format_percent(rules.accrual_rate)
    cap_note = "  (capped at plan maximum)" if result.service_was_capped else ""

    lines = [
        "Pension Benefit Calculation",
        "===========================",
        f"Final average earnings (best {rules.averaging_window} years): ${result.final_average_earnings:,.2f}",
        f"Accrual rate:                {accrual_percent}% per year of service",
        f"Credited service used:       {result.credited_service} years{cap_note}",
        f"Gross annual pension:        ${result.gross_annual:,.2f}",
        f"Early-retirement reduction:  {reduction_percent}%",
        f"Net annual pension:          ${result.net_annual:,.2f}",
        "---------------------------",
        f"MONTHLY PAYOUT:              ${result.monthly_payout:,.2f}",
    ]
    return "\n".join(lines)


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    rules = DEFAULT_PLAN

    try:
        raw_salaries = (
            read_salaries_from_csv(args.salary_file)
            if args.salary_file
            else args.salaries
        )
        salaries = validate_salary_history(raw_salaries, rules)
        credited_service, was_capped = validate_years_of_service(args.years_of_service, rules)
        retirement_age = validate_retirement_age(args.retirement_age, rules)
    except ValidationError as error:
        print(f"Input error: {error}", file=sys.stderr)
        return 1

    result = calculate_benefit(salaries, credited_service, was_capped, retirement_age, rules)
    print(format_report(result, rules))
    return 0


if __name__ == "__main__":
    sys.exit(main())
