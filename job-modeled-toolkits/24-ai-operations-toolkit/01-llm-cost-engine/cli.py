"""Command-line wrapper for the LLM cost engine.

Reads a usage log, a price book, a shared-cost list, and a team budget file,
validates every row, computes the costs, and writes three output files:

  cost_by_call.csv  - the billable cost of each usage record.
  cost_by_model.csv - cost and tokens rolled up by model.
  cost_by_team.csv  - direct cost, allocated shared cost, loaded cost, budget
                      status, and the month-end forecast for each team.

Usage:
  python cli.py
  python cli.py --usage usage_log.csv --prices price_book.csv \
                --shared shared_costs.csv --budgets budgets.csv
  python cli.py --asof 2026-06-20

The forecast as-of date defaults to the latest date in the usage log. The output
files are written next to this script.
"""

import argparse
import csv
import sys
from datetime import datetime
from decimal import Decimal

from costing import summarize
from validation import (
    ValidationError,
    validate_budget_row,
    validate_price_row,
    validate_shared_row,
    validate_usage_row,
)

CALL_COLUMNS = [
    "record_id", "usage_date", "team", "project", "model",
    "requests", "input_tokens", "cached_input_tokens", "output_tokens", "cost",
]

MODEL_COLUMNS = ["model", "requests", "input_tokens", "output_tokens", "cost"]

TEAM_COLUMNS = [
    "team", "requests", "input_tokens", "output_tokens",
    "direct_cost", "allocated_shared", "loaded_cost",
    "monthly_budget", "remaining", "utilization_pct", "status",
    "forecast_loaded", "forecast_status",
]


def load_price_book(path):
    book = {}
    with open(path, newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            model, rates = validate_price_row(row)
            if model in book:
                raise ValidationError("Price book: model %r is listed twice" % model)
            book[model] = rates
    if not book:
        raise ValidationError("Price book is empty")
    return book


def load_shared(path):
    total = Decimal("0.00")
    items = []
    with open(path, newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            item, amount = validate_shared_row(row)
            items.append((item, amount))
            total += amount
    return total, items


def load_budgets(path):
    budgets = {}
    with open(path, newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            team, budget = validate_budget_row(row)
            if team in budgets:
                raise ValidationError("Budgets: team %r is listed twice" % team)
            budgets[team] = budget
    if not budgets:
        raise ValidationError("Budget file is empty")
    return budgets


def load_usage(path, known_models, budgets):
    rows = []
    seen = set()
    with open(path, newline="", encoding="utf-8") as handle:
        for raw in csv.DictReader(handle):
            row = validate_usage_row(raw, known_models)
            if row["record_id"] in seen:
                raise ValidationError(
                    "Usage log: record_id %r appears more than once" % row["record_id"]
                )
            seen.add(row["record_id"])
            if row["team"] not in budgets:
                raise ValidationError(
                    "Usage %s: team %r has no budget row" % (row["record_id"], row["team"])
                )
            rows.append(row)
    if not rows:
        raise ValidationError("Usage log is empty")
    return rows


def write_csv(path, columns, rows):
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        for row in rows:
            writer.writerow({col: str(row[col]) for col in columns})


def main(argv=None):
    parser = argparse.ArgumentParser(description="LLM usage cost and chargeback engine.")
    parser.add_argument("--usage", default="usage_log.csv", help="usage log CSV")
    parser.add_argument("--prices", default="price_book.csv", help="price book CSV")
    parser.add_argument("--shared", default="shared_costs.csv", help="shared cost CSV")
    parser.add_argument("--budgets", default="budgets.csv", help="team budget CSV")
    parser.add_argument("--asof", default=None, help="forecast as-of date, YYYY-MM-DD")
    parser.add_argument("--call-out", default="cost_by_call.csv")
    parser.add_argument("--model-out", default="cost_by_model.csv")
    parser.add_argument("--team-out", default="cost_by_team.csv")
    args = parser.parse_args(argv)

    try:
        price_book = load_price_book(args.prices)
        budgets = load_budgets(args.budgets)
        shared_total, shared_items = load_shared(args.shared)
        usage = load_usage(args.usage, set(price_book), budgets)
    except ValidationError as error:
        print("Input rejected. %s" % error, file=sys.stderr)
        return 1
    except FileNotFoundError as error:
        print("File not found: %s" % error.filename, file=sys.stderr)
        return 1

    if args.asof:
        try:
            as_of = datetime.strptime(args.asof, "%Y-%m-%d").date()
        except ValueError:
            print("Invalid --asof date, expected YYYY-MM-DD.", file=sys.stderr)
            return 1
    else:
        as_of = max(row["usage_date"] for row in usage)

    result = summarize(usage, price_book, shared_total, budgets, as_of)

    write_csv(args.call_out, CALL_COLUMNS, result["per_call"])
    write_csv(args.model_out, MODEL_COLUMNS, result["per_model"])
    write_csv(args.team_out, TEAM_COLUMNS, result["per_team"])

    totals = result["totals"]
    print("LLM cost engine")
    print("Period as-of date: %s" % totals["as_of"])
    print("Usage records: %d   Requests: %d" % (len(result["per_call"]), totals["requests"]))
    print("Shared pool: %s across %d item(s)" % (shared_total, len(shared_items)))
    print()
    print("Cost by team")
    header = "  %-14s %12s %12s %12s %12s  %-12s" % (
        "Team", "Direct", "Shared", "Loaded", "Budget", "Status"
    )
    print(header)
    for row in result["per_team"]:
        print("  %-14s %12s %12s %12s %12s  %-12s" % (
            row["team"], row["direct_cost"], row["allocated_shared"],
            row["loaded_cost"], row["monthly_budget"], row["status"],
        ))
    print("  " + "-" * (len(header) - 2))
    print("  %-14s %12s %12s %12s %12s" % (
        "Total", totals["direct_cost"], totals["allocated_shared"],
        totals["loaded_cost"], totals["monthly_budget"],
    ))
    print()
    print("Month-end forecast (loaded): %s" % totals["forecast_loaded"])
    print("Wrote %s, %s, and %s" % (args.call_out, args.model_out, args.team_out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
