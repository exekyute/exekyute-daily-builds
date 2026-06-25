"""Command line front end for the Regulatory Deadline Monitor.

This file is a thin wrapper. It reads the compliance log, asks core.py to sort
the items by urgency and to cross-check against the aggregator's ledger, then
prints a dashboard and writes a copy to a text file.

Usage:
    python monitor_cli.py
    python monitor_cli.py --today 2026-06-06
    python monitor_cli.py --log data/compliance_log.csv --ledger ../waste-fuel-aggregator/output/unified_ledger.csv
"""

import argparse
import os
from datetime import date

import core

HERE = os.path.dirname(__file__)
DEFAULT_LOG = os.path.join(HERE, "data", "compliance_log.csv")
DEFAULT_LEDGER = os.path.join(HERE, "..", "waste-fuel-aggregator", "output", "unified_ledger.csv")
DEFAULT_OUT = os.path.join(HERE, "output", "dashboard.txt")


def parse_today(text):
    """Read the --today value, or use the real today if none was given."""
    if not text:
        return date.today()
    return core.parse_date(text)


def render(bands, today, gaps, ledger_sites, log_result):
    """Build the full dashboard as a list of text lines."""
    lines = []
    lines.append("REGULATORY DEADLINE MONITOR")
    lines.append("=" * 50)
    lines.append(f"As of: {today.isoformat()}")
    lines.append("")

    # Each urgency band, most urgent first.
    for name in core.BAND_ORDER:
        items = bands[name]
        lines.append(f"{name}  ({len(items)})")
        if not items:
            lines.append("  none")
        for item in items:
            # A finished item should not be described as overdue or due soon.
            if name == core.COMPLETE:
                phrase = "complete"
            else:
                phrase = core.describe_days(item["days_until"])
            lines.append(
                f"  {item['due_date'].isoformat()}  {item['site']:<12}  "
                f"{item['requirement']:<32}  {phrase}"
            )
        lines.append("")

    # Cross-check against the aggregator's ledger.
    lines.append("CROSS-CHECK AGAINST OPERATIONAL LEDGER")
    lines.append("-" * 50)
    if ledger_sites is None:
        lines.append("  No ledger found. Run the waste-fuel-aggregator first to enable this check.")
    else:
        lines.append(f"  Ledger sites ({len(ledger_sites)}): {', '.join(ledger_sites)}")
        if gaps:
            lines.append("  Compliance gap (activity in ledger, no deadline tracked):")
            for site in gaps:
                lines.append(f"    - {site}")
        else:
            lines.append("  Every site with ledger activity has at least one tracked deadline.")
    lines.append("")

    # Rows that needed attention.
    if log_result["notes"]:
        lines.append("Notes (kept, but adjusted):")
        for source, remark in log_result["notes"]:
            lines.append(f"  - {source}: {remark}")
        lines.append("")

    if log_result["skipped"]:
        lines.append("Rows skipped (bad data):")
        for source, reason in log_result["skipped"]:
            lines.append(f"  - {source}: {reason}")
        lines.append("")

    return lines


def main():
    parser = argparse.ArgumentParser(
        description="Sort compliance deadlines by urgency and print a dashboard."
    )
    parser.add_argument("--log", default=DEFAULT_LOG,
                        help="the compliance log CSV (default: data/compliance_log.csv)")
    parser.add_argument("--today", default=None,
                        help="treat this YYYY-MM-DD as today (default: the real today)")
    parser.add_argument("--ledger", default=DEFAULT_LEDGER,
                        help="unified ledger CSV to cross-check (default: the aggregator output)")
    parser.add_argument("--out", default=DEFAULT_OUT,
                        help="where to write a copy of the dashboard (default: output/dashboard.txt)")
    args = parser.parse_args()

    try:
        today = parse_today(args.today)
    except ValueError as problem:
        print(f"Bad --today value: {problem}")
        return

    try:
        log_result = core.load_log(args.log)
    except FileNotFoundError:
        print(f"No compliance log found at {args.log}")
        print("Run 'python generate_samples.py' first to create the sample data.")
        return
    except ValueError as problem:
        print(f"Cannot read the log: {problem}")
        return

    bands = core.build_dashboard(log_result["records"], today)
    ledger_sites = core.load_ledger_sites(args.ledger)
    gaps = core.cross_check(log_result["records"], ledger_sites)

    lines = render(bands, today, gaps, ledger_sites, log_result)
    text = "\n".join(lines)
    print(text)

    out_folder = os.path.dirname(args.out)
    if out_folder and not os.path.isdir(out_folder):
        os.makedirs(out_folder)
    with open(args.out, "w", encoding="utf-8") as handle:
        handle.write(text + "\n")
    print(f"Dashboard written: {args.out}")


if __name__ == "__main__":
    main()
