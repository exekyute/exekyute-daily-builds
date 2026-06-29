"""Command-line wrapper for the job-cost engine.

Reads a contracts CSV, validates every row, recognizes revenue by cost-to-cost
percent complete, and writes one output file:

  wip_schedule.csv - the full work-in-progress schedule, one row per job, with
                     percent complete, earned revenue, cost to complete, gross
                     profit, and the over/under billing position. The workbook
                     builder in the next tool reads this file.

Usage:
  python cli.py
  python cli.py --contracts contracts.csv --out wip_schedule.csv

The output file is written next to this script.
"""

import argparse
import csv
import sys
from decimal import Decimal

from validation import ValidationError, validate_contract_row
from wip import summarize

OUT_COLUMNS = [
    "job_id",
    "job_name",
    "contract_value",
    "estimated_total_cost",
    "cost_to_date",
    "billed_to_date",
    "percent_complete",
    "earned_revenue",
    "cost_to_complete",
    "estimated_gross_profit",
    "gross_profit_to_date",
    "over_under_billing",
    "status",
]


def load_contracts(path):
    rows = []
    seen = set()
    with open(path, newline="", encoding="utf-8") as handle:
        for raw in csv.DictReader(handle):
            row = validate_contract_row(raw)
            if row["job_id"] in seen:
                raise ValidationError(
                    "Contracts: job_id %r appears more than once" % row["job_id"]
                )
            seen.add(row["job_id"])
            rows.append(row)
    if not rows:
        raise ValidationError("Contracts file is empty")
    return rows


def write_csv(path, columns, rows):
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        for row in rows:
            writer.writerow({col: str(row[col]) for col in columns})


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Construction work-in-progress and job-cost engine."
    )
    parser.add_argument("--contracts", default="contracts.csv", help="contracts CSV")
    parser.add_argument("--out", default="wip_schedule.csv", help="output schedule CSV")
    args = parser.parse_args(argv)

    try:
        contracts = load_contracts(args.contracts)
    except ValidationError as error:
        print("Input rejected. %s" % error, file=sys.stderr)
        return 1
    except FileNotFoundError as error:
        print("File not found: %s" % error.filename, file=sys.stderr)
        return 1

    result = summarize(contracts)
    write_csv(args.out, OUT_COLUMNS, result["per_job"])

    totals = result["totals"]
    print("Construction WIP and job-cost engine")
    print("Jobs: %d   Underbilled: %d   Overbilled: %d   Even: %d" % (
        len(result["per_job"]),
        totals["underbilled_count"],
        totals["overbilled_count"],
        totals["even_count"],
    ))
    print()
    header = "  %-8s %-22s %8s %14s %14s %14s  %-11s" % (
        "Job", "Name", "% Comp", "Earned", "Billed", "Over/Under", "Status"
    )
    print(header)
    for row in result["per_job"]:
        pct = (row["percent_complete"] * 100).quantize(Decimal("0.1"))
        print("  %-8s %-22s %7s%% %14s %14s %14s  %-11s" % (
            row["job_id"],
            row["job_name"][:22],
            pct,
            row["earned_revenue"],
            row["billed_to_date"],
            row["over_under_billing"],
            row["status"],
        ))
    print("  " + "-" * (len(header) - 2))
    print("  %-8s %-22s %8s %14s %14s %14s" % (
        "Total", "",
        "",
        totals["earned_revenue"],
        totals["billed_to_date"],
        totals["over_under_billing"],
    ))
    print()
    print("Gross profit to date: %s   Estimated gross profit at completion: %s" % (
        totals["gross_profit_to_date"], totals["estimated_gross_profit"]
    ))
    print("Wrote %s" % args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
