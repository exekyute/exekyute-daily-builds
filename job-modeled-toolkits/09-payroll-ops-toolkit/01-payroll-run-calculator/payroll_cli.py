"""Command-line wrapper: read a timesheet CSV, write a payroll register CSV.

This layer only handles input/output and orchestration. All money math lives
in payroll_logic and all input checking lives in payroll_validation, so this
file stays a thin, readable shell around those two.

Usage:
    python payroll_cli.py data/sample_timesheet.csv -o data/payroll_register.csv
"""

import argparse
import csv
import sys
from decimal import Decimal

import payroll_logic as logic
import payroll_validation as validation

REGISTER_FIELDS = [
    "employee_id",
    "name",
    "pay_type",
    "gross_pay",
    "overtime_pay",
    "pretax_deductions",
    "cpp",
    "ei",
    "income_tax",
    "posttax_deductions",
    "total_deductions",
    "net_pay",
]

MONEY_FIELDS = {
    "gross_pay",
    "overtime_pay",
    "pretax_deductions",
    "cpp",
    "ei",
    "income_tax",
    "posttax_deductions",
    "total_deductions",
    "net_pay",
}


def format_money(value):
    """Fixed-point string with two decimals, never scientific notation."""
    return "%0.2f" % value


def build_config(args):
    """Translate command-line arguments into an immutable PayrollConfig."""
    return logic.PayrollConfig(
        overtime_threshold=Decimal(str(args.overtime_threshold)),
        overtime_multiplier=Decimal(str(args.overtime_multiplier)),
        income_tax_rate=Decimal(str(args.income_tax_rate)),
        pay_periods_per_year=args.pay_periods,
    )


def process_rows(rows, fieldnames, config):
    """Validate and calculate every row.

    Returns (records, rejections) where records is a list of register dicts
    and rejections is a list of (row_label, [errors]). A header problem is
    fatal for the whole file and produces a single rejection.
    """
    header_errors = validation.validate_header(fieldnames)
    if header_errors:
        return [], [("header", header_errors)]

    records = []
    rejections = []
    seen_ids = set()

    for index, row in enumerate(rows, start=2):  # row 1 is the header
        errors = validation.validate_row(row)
        employee_id = (row.get("employee_id") or "").strip()

        if employee_id and employee_id in seen_ids:
            errors.append("Duplicate employee_id '%s' (first kept)" % employee_id)

        label = employee_id or ("row %d" % index)
        if errors:
            rejections.append((label, errors))
            continue

        seen_ids.add(employee_id)
        clean = {
            "employee_id": employee_id,
            "name": row["name"].strip(),
            "pay_type": row["pay_type"].strip().lower(),
            "rate": row["rate"].strip(),
            "hours_worked": row["hours_worked"].strip(),
            "pretax_deductions": row["pretax_deductions"].strip(),
            "posttax_deductions": row["posttax_deductions"].strip(),
        }
        records.append(logic.calculate_pay(clean, config))

    return records, rejections


def write_register(path, records):
    """Write the payroll register CSV with money fields as fixed-point text."""
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=REGISTER_FIELDS)
        writer.writeheader()
        for record in records:
            writer.writerow({
                field: format_money(record[field]) if field in MONEY_FIELDS else record[field]
                for field in REGISTER_FIELDS
            })


def summarize(records):
    """Return (total_gross, total_net) across all processed records."""
    total_gross = sum((record["gross_pay"] for record in records), Decimal("0"))
    total_net = sum((record["net_pay"] for record in records), Decimal("0"))
    return logic.money(total_gross), logic.money(total_net)


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Compute Canadian gross-to-net payroll from a timesheet CSV."
    )
    parser.add_argument("input", help="Path to the timesheet CSV to read")
    parser.add_argument(
        "-o", "--output",
        default="data/payroll_register.csv",
        help="Where to write the payroll register CSV (default: data/payroll_register.csv)",
    )
    parser.add_argument("--overtime-threshold", type=float, default=44.0,
                        help="Weekly hours before overtime applies (default: 44)")
    parser.add_argument("--overtime-multiplier", type=float, default=1.5,
                        help="Overtime pay multiplier (default: 1.5)")
    parser.add_argument("--income-tax-rate", type=float, default=0.20,
                        help="Flat combined federal and provincial rate (default: 0.20)")
    parser.add_argument("--pay-periods", type=int, default=26,
                        help="Pay periods per year for CPP and EI proration (default: 26)")
    args = parser.parse_args(argv)

    config = build_config(args)

    try:
        with open(args.input, newline="", encoding="utf-8-sig") as handle:
            reader = csv.DictReader(
                handle,
                restkey=validation.EXTRA_FIELD_KEY,
                restval=None,
            )
            fieldnames = reader.fieldnames
            rows = list(reader)
    except FileNotFoundError:
        print("Error: input file not found: %s" % args.input, file=sys.stderr)
        return 1

    records, rejections = process_rows(rows, fieldnames, config)
    write_register(args.output, records)

    total_gross, total_net = summarize(records)

    print("Payroll run complete.")
    print("  Processed: %d employee(s)" % len(records))
    print("  Rejected:  %d row(s)" % len(rejections))
    for label, errors in rejections:
        for error in errors:
            print("    - [%s] %s" % (label, error))
    print("  Total gross: $%s CAD" % format_money(total_gross))
    print("  Total net:   $%s CAD" % format_money(total_net))
    print("  Register written to: %s" % args.output)
    return 0


if __name__ == "__main__":
    sys.exit(main())
