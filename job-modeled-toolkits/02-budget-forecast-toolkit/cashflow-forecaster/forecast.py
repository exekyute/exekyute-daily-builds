"""Command-line entry point for the cash flow forecaster.

Reads a history of monthly net cash flows, computes a simple and a weighted
moving average over the most recent window, projects the upcoming quarter, and
reports the cash runway in months for each average. Writes the projection to a
CSV file.

Example:
    python forecast.py --history data/cash_flow_history.csv --starting-cash 250000.00
"""

import argparse
import csv
import sys
from decimal import Decimal, InvalidOperation
from pathlib import Path

from forecaster import (
    format_amount,
    has_enough_data,
    next_periods,
    project,
    runway_months,
    simple_moving_average,
    weighted_moving_average,
)
from loader import HistoryError, load_history

QUARTER = 3


def build_parser():
    parser = argparse.ArgumentParser(
        description="Project the upcoming quarter and cash runway from historical cash flow."
    )
    parser.add_argument(
        "--history",
        default="data/cash_flow_history.csv",
        help="History CSV with a period,net_cash_flow header (default: data/cash_flow_history.csv).",
    )
    parser.add_argument(
        "--starting-cash",
        default="250000.00",
        help="Current cash balance (default: 250000.00).",
    )
    parser.add_argument(
        "--window",
        default="3",
        help="Number of recent periods to average over (default: 3).",
    )
    parser.add_argument(
        "--output",
        default="output/forecast.csv",
        help="Path for the projection CSV (default: output/forecast.csv).",
    )
    return parser


def print_history(records):
    print("| Period | Net Cash Flow |")
    print("| --- | ---: |")
    for period, amount in records:
        print(f"| {period} | {format_amount(amount)} |")


def print_projection(title, rows, runway):
    print()
    print(title)
    print("| Period | Projected Net Cash Flow | Projected Ending Cash |")
    print("| --- | ---: | ---: |")
    for row in rows:
        print(
            f"| {row['period']} | {format_amount(row['flow'])} | "
            f"{format_amount(row['balance'])} |"
        )
    if runway is None:
        print("  Runway: not net-negative, cash is not being drawn down.")
    else:
        print(f"  Runway: {format_amount(runway)} months at this average burn.")


def write_output(output_path, simple_rows, weighted_rows):
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            ["method", "period", "projected_net_cash_flow", "projected_ending_cash"]
        )
        for label, rows in (("simple", simple_rows), ("weighted", weighted_rows)):
            for row in rows:
                writer.writerow(
                    [
                        label,
                        row["period"],
                        format_amount(row["flow"]),
                        format_amount(row["balance"]),
                    ]
                )


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        starting_cash = Decimal(args.starting_cash)
    except InvalidOperation:
        print("Error: starting cash must be numeric.", file=sys.stderr)
        return 1
    try:
        window = int(args.window)
    except ValueError:
        print("Error: window must be a whole number.", file=sys.stderr)
        return 1
    if window < 1:
        print("Error: window must be at least 1.", file=sys.stderr)
        return 1

    try:
        history = load_history(args.history)
    except HistoryError as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1

    if not has_enough_data(history.records, window):
        print(
            f"Error: need at least {window} usable periods to average over, "
            f"found {len(history.records)}.",
            file=sys.stderr,
        )
        return 1

    flows = [amount for _period, amount in history.records]
    simple = simple_moving_average(flows, window)
    weighted = weighted_moving_average(flows, window)
    periods = next_periods(history.records[-1][0], QUARTER)
    simple_rows = project(starting_cash, simple, periods)
    weighted_rows = project(starting_cash, weighted, periods)

    print_history(history.records)
    print()
    print(f"Window: {window} periods")
    print(f"Starting cash: {format_amount(starting_cash)}")
    print(f"Simple moving average:   {format_amount(simple)}")
    print(f"Weighted moving average: {format_amount(weighted)}")

    print_projection(
        "Projected quarter (simple moving average)",
        simple_rows,
        runway_months(starting_cash, simple),
    )
    print_projection(
        "Projected quarter (weighted moving average)",
        weighted_rows,
        runway_months(starting_cash, weighted),
    )

    print()
    print("Findings")
    print(f"  Usable periods: {len(history.records)}")
    print(f"  Duplicate periods skipped: {history.duplicates}")
    print(f"  Rows skipped (blank or unreadable): {history.skipped}")

    write_output(args.output, simple_rows, weighted_rows)
    print()
    print(f"Projection written to: {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
