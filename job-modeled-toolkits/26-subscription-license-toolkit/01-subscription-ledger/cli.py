"""Command-line wrapper for the subscription ledger.

Reads a subscriptions CSV, validates every row, works out the cost, waste, and
renewal position for each, and writes one output file:

  subscriptions_normalized.csv - one row per subscription with the monthly and
                                 annual cost, the seat waste, the days to renewal,
                                 the renewal status, and the suggested action. The
                                 browser app in 02 reads this file.

Usage:
  python cli.py
  python cli.py --subs subscriptions.csv --out subscriptions_normalized.csv
  python cli.py --asof 2026-06-30

The renewal clock is measured from --asof, which defaults to today.
"""

import argparse
import csv
import sys
from datetime import date, datetime

from subscriptions import summarize
from validation import ValidationError, validate_sub_row

OUT_COLUMNS = [
    "sub_id", "vendor", "plan", "plan_type", "monthly_unit_cost",
    "seats_owned", "seats_used", "monthly_cost", "annual_cost",
    "unused_seats", "monthly_waste", "annual_waste", "utilization",
    "renewal_date", "days_to_renewal", "renewal_status", "auto_renew", "action",
]


def load_subs(path):
    rows = []
    seen = set()
    with open(path, newline="", encoding="utf-8") as handle:
        for raw in csv.DictReader(handle):
            row = validate_sub_row(raw)
            if row["sub_id"] in seen:
                raise ValidationError("Subscriptions: sub_id %r appears more than once" % row["sub_id"])
            seen.add(row["sub_id"])
            rows.append(row)
    if not rows:
        raise ValidationError("Subscriptions file is empty")
    return rows


def _format(value):
    if value is None:
        return ""
    return str(value)


def write_csv(path, rows):
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=OUT_COLUMNS)
        writer.writeheader()
        for row in rows:
            writer.writerow({col: _format(row[col]) for col in OUT_COLUMNS})


def main(argv=None):
    parser = argparse.ArgumentParser(description="SaaS subscription and license ledger.")
    parser.add_argument("--subs", default="subscriptions.csv")
    parser.add_argument("--out", default="subscriptions_normalized.csv")
    parser.add_argument("--asof", default=None, help="renewal clock date, YYYY-MM-DD")
    args = parser.parse_args(argv)

    if args.asof:
        try:
            as_of = datetime.strptime(args.asof, "%Y-%m-%d").date()
        except ValueError:
            print("Invalid --asof date, expected YYYY-MM-DD.", file=sys.stderr)
            return 1
    else:
        as_of = date.today()

    try:
        subs = load_subs(args.subs)
    except ValidationError as error:
        print("Input rejected. %s" % error, file=sys.stderr)
        return 1
    except FileNotFoundError as error:
        print("File not found: %s" % error.filename, file=sys.stderr)
        return 1

    result = summarize(subs, as_of)
    write_csv(args.out, result["per_sub"])
    totals = result["totals"]

    print("Subscription and license ledger")
    print("As of %s   Subscriptions: %d" % (as_of.isoformat(), len(result["per_sub"])))
    print("Due soon: %d   Expired: %d   Underused: %d" % (
        totals["due_soon_count"], totals["expired_count"], totals["underused_count"]))
    print()
    header = "  %-6s %-12s %10s %12s %10s  %-10s  %s" % (
        "ID", "Vendor", "Monthly", "Annual", "Waste/mo", "Renewal", "Action")
    print(header)
    for r in result["per_sub"]:
        print("  %-6s %-12s %10s %12s %10s  %-10s  %s" % (
            r["sub_id"], r["vendor"][:12], r["monthly_cost"], r["annual_cost"],
            r["monthly_waste"], r["renewal_status"], r["action"]))
    print("  " + "-" * (len(header) - 2))
    print("  %-6s %-12s %10s %12s %10s" % (
        "Total", "", totals["monthly_cost"], totals["annual_cost"], totals["monthly_waste"]))
    print()
    print("Annual spend: %s   Annual waste on unused seats: %s" % (
        totals["annual_cost"], totals["annual_waste"]))
    print("Wrote %s" % args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
