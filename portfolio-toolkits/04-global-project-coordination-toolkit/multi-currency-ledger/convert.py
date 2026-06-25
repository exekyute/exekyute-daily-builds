"""Command-line entry point for the Multi-Currency Consultant Ledger.

Reads a CSV of consultant invoices in mixed currencies, converts each to the USD
base, reconciles the total against the approved grant, prints a markdown table and
a summary line, and writes a central budget file the Burn Rate Tracker can consume.

Example
-------
    python convert.py --invoices data/consultant_invoices.csv
    python convert.py --invoices data/consultant_invoices.csv --grant 250000.00
"""

import argparse
import json
import sys

from ledger import process_invoices
from loader import load_invoices, LedgerError
from rates import BASE_CURRENCY

DEFAULT_GRANT = "250000.00"
DEFAULT_OUT = "central_budget.json"


def format_markdown_table(result):
    """Render the accepted invoices as a GitHub-flavored markdown table."""
    header = (
        f"| Invoice | Consultant | Currency | Amount | Base ({BASE_CURRENCY}) |\n"
        "| --- | --- | --- | ---: | ---: |"
    )
    rows = [
        f"| {line.invoice_id} | {line.consultant} | {line.currency} | "
        f"{line.amount:.2f} | {line.base_amount:.2f} |"
        for line in result.lines
    ]
    return "\n".join([header, *rows])


def build_budget_record(result):
    """Build the central budget dictionary written to disk for the next tool."""
    return {
        "base_currency": result.base_currency,
        "grant_total": f"{result.grant_total:.2f}",
        "consultant_spend": f"{result.consultant_spend:.2f}",
        "remaining": f"{result.remaining:.2f}",
        "over_budget": result.over_budget,
        "invoice_count": result.invoice_count,
    }


def print_report(result, out_path):
    """Print the table, the findings, and the reconciliation summary."""
    print(format_markdown_table(result))
    print()

    for item in result.skipped:
        print(f"  skipped row {item['row']}: {item['reason']}")
    for item in result.duplicates:
        print(f"  duplicate row {item['row']}: {item['reason']}")
    if result.skipped or result.duplicates:
        print()

    status = "OVER BUDGET" if result.over_budget else "within grant"
    print(
        f"Accepted {result.invoice_count} invoice(s) | "
        f"skipped {len(result.skipped)} | duplicates {len(result.duplicates)}"
    )
    print(
        f"Consultant spend: {result.consultant_spend:.2f} {result.base_currency} | "
        f"Grant: {result.grant_total:.2f} | "
        f"Remaining: {result.remaining:.2f} ({status})"
    )
    print(f"Central budget written to {out_path}")


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Reconcile multi-currency consultant invoices against a grant."
    )
    parser.add_argument(
        "--invoices", default="data/consultant_invoices.csv",
        help="path to the invoice CSV (default: data/consultant_invoices.csv)",
    )
    parser.add_argument(
        "--grant", default=DEFAULT_GRANT,
        help=f"approved grant total in {BASE_CURRENCY} (default: {DEFAULT_GRANT})",
    )
    parser.add_argument(
        "--out", default=DEFAULT_OUT,
        help=f"path for the central budget file (default: {DEFAULT_OUT})",
    )
    args = parser.parse_args(argv)

    try:
        records = load_invoices(args.invoices)
    except LedgerError as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1

    result = process_invoices(records, args.grant)
    budget = build_budget_record(result)

    with open(args.out, "w", encoding="utf-8") as handle:
        json.dump(budget, handle, indent=2)
        handle.write("\n")

    print_report(result, args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
