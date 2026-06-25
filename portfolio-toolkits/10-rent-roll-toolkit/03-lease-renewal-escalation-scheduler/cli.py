"""Command-line wrapper for the lease renewal and escalation scheduler.

Reads a leases CSV, validates it, works out each lease's next term and escalated
rent, decides which leases need a renewal notice as of a given date, prints a
readable table, and writes the schedule to CSV. The math lives in renewal_logic.py
and the checks live in renewal_validation.py. This file only handles input, output,
and formatting.

Run from inside this folder:

    python cli.py
    python cli.py --as-of 2026-06-12 --notice-days 90 --escalation-rate 0.04
    python cli.py --input data/sample_leases.csv --output data/renewals.csv
    python cli.py --input data/invalid_leases.csv
"""

import argparse
import csv
import os
import sys
from datetime import datetime
from decimal import Decimal

import renewal_logic as logic
import renewal_validation as validation

DEFAULT_INPUT = os.path.join("data", "sample_leases.csv")
DEFAULT_OUTPUT = os.path.join("data", "renewals.csv")
DEFAULT_AS_OF = "2026-06-12"
DEFAULT_NOTICE_DAYS = 90
DEFAULT_ESCALATION_RATE = "0.04"
DEFAULT_TERM_MONTHS = 12

RENEWAL_COLUMNS = [
    "unit",
    "tenant",
    "current_rent",
    "lease_end",
    "renewal_start",
    "renewal_end",
    "escalated_rent",
    "notice_due_date",
    "days_to_notice",
    "status",
]

# Order the status groups are reported in the footer.
STATUS_ORDER = [logic.STATUS_DUE_NOW, logic.STATUS_UPCOMING, logic.STATUS_EXPIRED]


def parse_as_of(text):
    """Parse the as-of date. Raises ValidationError if it is not YYYY-MM-DD."""
    try:
        return datetime.strptime(text.strip(), "%Y-%m-%d").date()
    except ValueError:
        raise validation.ValidationError(
            ["--as-of must be in YYYY-MM-DD form, for example 2026-06-12"]
        )


def read_csv(path):
    """Read a CSV into (header, rows). Raises ValidationError for missing or empty files."""
    if not os.path.isfile(path):
        raise validation.ValidationError(["input file not found: {0}".format(path)])
    with open(path, newline="", encoding="utf-8") as handle:
        reader = csv.reader(handle)
        all_rows = [row for row in reader if row != []]
    if not all_rows:
        raise validation.ValidationError(["input file is empty: {0}".format(path)])
    return all_rows[0], all_rows[1:]


def build_schedule(leases, as_of, notice_days, escalation_rate, term_months):
    """Turn validated leases into renewal records, one dict per unit."""
    records = []
    for lease in leases:
        renewal_start, renewal_end = logic.renewal_window(lease.lease_end, term_months)
        notice_due = logic.notice_due_date(lease.lease_end, notice_days)
        records.append(
            {
                "unit": lease.unit,
                "tenant": lease.tenant,
                "current_rent": logic.quantize_money(lease.monthly_rent),
                "lease_end": lease.lease_end,
                "renewal_start": renewal_start,
                "renewal_end": renewal_end,
                "escalated_rent": logic.escalate_rent(lease.monthly_rent, escalation_rate),
                "notice_due_date": notice_due,
                "days_to_notice": logic.days_between(as_of, notice_due),
                "status": logic.status_for(lease.lease_end, as_of, notice_due),
            }
        )
    return records


def write_schedule(path, records):
    """Write renewal records to CSV with fixed-point money and YYYY-MM-DD dates."""
    folder = os.path.dirname(path)
    if folder:
        os.makedirs(folder, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=RENEWAL_COLUMNS)
        writer.writeheader()
        for record in records:
            writer.writerow(
                {
                    "unit": record["unit"],
                    "tenant": record["tenant"],
                    "current_rent": "{0:.2f}".format(record["current_rent"]),
                    "lease_end": record["lease_end"].strftime("%Y-%m-%d"),
                    "renewal_start": record["renewal_start"].strftime("%Y-%m-%d"),
                    "renewal_end": record["renewal_end"].strftime("%Y-%m-%d"),
                    "escalated_rent": "{0:.2f}".format(record["escalated_rent"]),
                    "notice_due_date": record["notice_due_date"].strftime("%Y-%m-%d"),
                    "days_to_notice": record["days_to_notice"],
                    "status": record["status"],
                }
            )


def print_table(records):
    """Print the schedule as an aligned console table."""
    header = [
        "UNIT",
        "TENANT",
        "CURRENT",
        "ESCALATED",
        "LEASE END",
        "RENEWAL START",
        "RENEWAL END",
        "NOTICE DUE",
        "DAYS",
        "STATUS",
    ]
    rows = [header]
    for record in records:
        rows.append(
            [
                record["unit"],
                record["tenant"],
                "{0:.2f}".format(record["current_rent"]),
                "{0:.2f}".format(record["escalated_rent"]),
                record["lease_end"].strftime("%Y-%m-%d"),
                record["renewal_start"].strftime("%Y-%m-%d"),
                record["renewal_end"].strftime("%Y-%m-%d"),
                record["notice_due_date"].strftime("%Y-%m-%d"),
                str(record["days_to_notice"]),
                record["status"],
            ]
        )

    widths = [max(len(row[i]) for row in rows) for i in range(len(header))]
    for line_index, row in enumerate(rows):
        cells = [row[i].ljust(widths[i]) for i in range(len(row))]
        print("  ".join(cells))
        if line_index == 0:
            print("  ".join("-" * widths[i] for i in range(len(header))))


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Schedule lease renewals and escalated rents from a leases CSV."
    )
    parser.add_argument("--input", default=DEFAULT_INPUT, help="leases CSV to read")
    parser.add_argument("--output", default=DEFAULT_OUTPUT, help="renewals CSV to write")
    parser.add_argument("--as-of", default=DEFAULT_AS_OF, help="reference date in YYYY-MM-DD form")
    parser.add_argument(
        "--notice-days",
        type=int,
        default=DEFAULT_NOTICE_DAYS,
        help="days before lease end that a renewal notice is due",
    )
    parser.add_argument(
        "--escalation-rate",
        default=DEFAULT_ESCALATION_RATE,
        help="rent increase for the next term as a fraction, for example 0.04 for 4 percent",
    )
    parser.add_argument(
        "--term-months",
        type=int,
        default=DEFAULT_TERM_MONTHS,
        help="length of the renewed lease term in months",
    )
    args = parser.parse_args(argv)

    try:
        as_of = parse_as_of(args.as_of)
        escalation_rate = Decimal(args.escalation_rate)
        header, rows = read_csv(args.input)
        validation.check_header(header)
        leases, issues = validation.validate_rows(header, rows)
    except validation.ValidationError as error:
        print("Input rejected. Fix these problems and run again:", file=sys.stderr)
        for problem in error.problems:
            print("  - {0}".format(problem), file=sys.stderr)
        return 1

    records = build_schedule(leases, as_of, args.notice_days, escalation_rate, args.term_months)
    print_table(records)

    write_schedule(args.output, records)

    counts = {status: 0 for status in STATUS_ORDER}
    for record in records:
        counts[record["status"]] += 1

    print("")
    print(
        "Scheduled {0} lease(s) as of {1}. Due now: {2}, upcoming: {3}, expired: {4}".format(
            len(records),
            as_of.strftime("%Y-%m-%d"),
            counts[logic.STATUS_DUE_NOW],
            counts[logic.STATUS_UPCOMING],
            counts[logic.STATUS_EXPIRED],
        )
    )
    print("Renewals written to {0}".format(args.output))

    if issues:
        print("", file=sys.stderr)
        print("Skipped {0} row(s):".format(len(issues)), file=sys.stderr)
        for issue in issues:
            print("  - {0}".format(issue), file=sys.stderr)

    return 0


if __name__ == "__main__":
    sys.exit(main())
