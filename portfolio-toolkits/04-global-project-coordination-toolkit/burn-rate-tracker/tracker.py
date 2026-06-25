"""Command-line entry point for the Milestone-Driven Burn Rate Tracker.

Loads the grant fund and the consultant spend from the ledger's central budget
file, applies a CSV of project phase costs (or live entries in interactive mode)
on top, and prints the running burn rate against the fund after each phase.

Example
-------
    python tracker.py --phases data/phase_updates.csv
    python tracker.py --budget ../multi-currency-ledger/central_budget.json
    python tracker.py --interactive
"""

import argparse
import csv
import sys

from budget_source import load_budget, BudgetError
from burnrate import process_phases, money, burn_rate, remaining
from validators import InvalidPhase, validate_cost, validate_phase_name

DEFAULT_BUDGET = "data/central_budget.json"
DEFAULT_PHASES = "data/phase_updates.csv"


def load_phase_rows(path):
    """Read the phase CSV into a list of row dicts."""
    try:
        with open(path, newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            header = reader.fieldnames or []
            for column in ("phase", "cost"):
                if column not in header:
                    raise BudgetError(
                        f"phase file is missing required column: {column}"
                    )
            return list(reader)
    except FileNotFoundError:
        raise BudgetError(f"phase file not found: {path}")


def format_markdown_table(result):
    """Render the accepted phases and their running totals as a markdown table."""
    header = (
        "| Phase | Cost | Spent to date | Remaining | Burn rate | Status |\n"
        "| --- | ---: | ---: | ---: | ---: | --- |"
    )
    rows = []
    for line in result.lines:
        status = "OVER FUND" if line.over_fund else "within fund"
        rows.append(
            f"| {line.name} | {line.cost:.2f} | {line.spent:.2f} | "
            f"{line.remaining:.2f} | {line.burn_rate:.2f}% | {status} |"
        )
    return "\n".join([header, *rows])


def print_report(result):
    """Print the starting position, the per-phase table, and the final summary."""
    start_rate = burn_rate(result.starting_spend, result.fund)
    print(
        f"Grant fund: {result.fund:.2f} {result.base_currency} | "
        f"Consultant spend carried from ledger: {result.starting_spend:.2f} "
        f"({start_rate:.2f}% of fund)"
    )
    print()
    print(format_markdown_table(result))
    print()

    for item in result.skipped:
        print(f"  skipped row {item['row']}: {item['reason']}")
    for item in result.duplicates:
        print(f"  duplicate row {item['row']}: {item['reason']}")
    if result.skipped or result.duplicates:
        print()

    status = "OVER FUND" if result.over_fund else "within fund"
    print(
        f"Applied {result.phase_count} phase(s) | "
        f"skipped {len(result.skipped)} | duplicates {len(result.duplicates)}"
    )
    print(
        f"Final spend: {result.final_spent:.2f} {result.base_currency} | "
        f"Remaining: {result.final_remaining:.2f} | "
        f"Burn rate: {result.final_burn_rate:.2f}% ({status})"
    )


def run_interactive(budget):
    """Prompt for phases one at a time and print the running burn rate."""
    fund = budget["grant_total"]
    spent = budget["consultant_spend"]
    currency = budget["base_currency"]
    seen = set()
    print(
        f"Grant fund {money(fund):.2f} {currency}, "
        f"starting spend {money(spent):.2f}. "
        "Enter a phase name then its cost. Blank phase name to finish."
    )
    while True:
        name_raw = input("Phase name: ")
        if not name_raw.strip():
            break
        try:
            name = validate_phase_name(name_raw)
            if name.lower() in seen:
                print("  duplicate phase name; not counted")
                continue
            cost = validate_cost(input("Phase cost: "))
        except InvalidPhase as error:
            print(f"  rejected: {error}")
            continue
        seen.add(name.lower())
        spent = spent + cost
        status = "OVER FUND" if spent > fund else "within fund"
        print(
            f"  spent {money(spent):.2f} | remaining {remaining(fund, spent):.2f} | "
            f"burn rate {burn_rate(spent, fund):.2f}% ({status})"
        )


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Track project burn rate against a grant fund."
    )
    parser.add_argument(
        "--budget", default=DEFAULT_BUDGET,
        help=f"path to the ledger's central budget file (default: {DEFAULT_BUDGET})",
    )
    parser.add_argument(
        "--phases", default=DEFAULT_PHASES,
        help=f"path to the phase updates CSV (default: {DEFAULT_PHASES})",
    )
    parser.add_argument(
        "--interactive", action="store_true",
        help="enter phases one at a time instead of reading the CSV",
    )
    args = parser.parse_args(argv)

    try:
        budget = load_budget(args.budget)
    except BudgetError as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1

    if args.interactive:
        run_interactive(budget)
        return 0

    try:
        records = load_phase_rows(args.phases)
    except BudgetError as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1

    result = process_phases(
        records,
        budget["grant_total"],
        budget["consultant_spend"],
        budget["base_currency"],
    )
    print_report(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
