"""Command-line wrapper for the expense auditor.

Reads a policy file and an expense file, validates both, applies the policy, and
writes one output file:

  audited.csv - one row per expense with its computed amount, its flags, and whether
                it is approved or sent to review. The browser app in 02 reads this.

Usage:
  python cli.py
  python cli.py --expenses expenses.csv --policy policy.csv
"""

import argparse
import csv
import sys

from audit import audit
from validation import ValidationError, load_policy_rows, validate_expense_row

OUT_COLUMNS = [
    "expense_id", "date", "employee", "category", "amount", "km",
    "receipt", "computed_amount", "flags", "status",
]


def load_policy(path):
    with open(path, newline="", encoding="utf-8") as handle:
        return load_policy_rows(list(csv.DictReader(handle)))


def load_expenses(path, policy):
    rows = []
    seen = set()
    with open(path, newline="", encoding="utf-8") as handle:
        for raw in csv.DictReader(handle):
            row = validate_expense_row(raw, policy)
            if row["expense_id"] in seen:
                raise ValidationError("Expenses: expense_id %r appears more than once" % row["expense_id"])
            seen.add(row["expense_id"])
            rows.append(row)
    if not rows:
        raise ValidationError("Expenses file is empty")
    return rows


def write_csv(path, rows):
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=OUT_COLUMNS)
        writer.writeheader()
        for row in rows:
            record = dict(row)
            record["flags"] = ";".join(row["flags"])
            writer.writerow({col: str(record[col]) for col in OUT_COLUMNS})


def main(argv=None):
    parser = argparse.ArgumentParser(description="Travel and expense policy auditor.")
    parser.add_argument("--expenses", default="expenses.csv")
    parser.add_argument("--policy", default="policy.csv")
    parser.add_argument("--out", default="audited.csv")
    args = parser.parse_args(argv)

    try:
        policy = load_policy(args.policy)
        expenses = load_expenses(args.expenses, policy)
    except ValidationError as error:
        print("Input rejected. %s" % error, file=sys.stderr)
        return 1
    except FileNotFoundError as error:
        print("File not found: %s" % error.filename, file=sys.stderr)
        return 1

    result = audit(expenses, policy)
    write_csv(args.out, result["rows"])
    totals = result["totals"]

    print("Travel and expense policy audit")
    print("Mileage rate: %s/km   Receipt threshold: %s" % (
        policy["mileage_rate"], policy["receipt_threshold"]))
    print("Expenses: %d   Approved: %d   Flagged: %d" % (
        len(result["rows"]), totals["approved_count"], totals["flagged_count"]))
    print()
    header = "  %-7s %-10s %-10s %10s  %-8s  %s" % (
        "ID", "Employee", "Category", "Amount", "Status", "Flags")
    print(header)
    for r in result["rows"]:
        print("  %-7s %-10s %-10s %10s  %-8s  %s" % (
            r["expense_id"], r["employee"][:10], r["category"][:10], r["amount"],
            r["status"], ";".join(r["flags"])))
    print()
    print("Total claimed: %s   Flagged for review: %s   Approved: %s" % (
        totals["total_claimed"], totals["flagged_amount"], totals["approved_amount"]))
    print("Wrote %s" % args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
