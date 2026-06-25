"""Command line front end for the Contact List Cleaner.

This is the "type a command" way to use the tool. It does no real thinking of its
own; it reads your command, calls the functions in core.py, and prints the
results. Keeping the logic in core.py means this file stays short and easy.

Quick start (run these from the project folder):

    python clean_cli.py preview     # see what WOULD change, nothing written
    python clean_cli.py clean       # preview, then write after you confirm
    python clean_cli.py report      # just show the merge + conflict report

By default it reads the sample file (samples/contacts_messy.csv). Point it at a
file of your own with  --input "C:\\path\\to\\your\\contacts.csv".
"""

import argparse
import os

import core

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_INPUT = os.path.join(HERE, "samples", "contacts_messy.csv")
DEFAULT_CLEAN = os.path.join(HERE, "contacts_clean.csv")
DEFAULT_REPORT = os.path.join(HERE, "merge_report.txt")


def load_plan(args):
    """Read the input file and plan the clean. Shared by every command."""
    rows = core.read_contacts(args.input)
    return core.plan_clean(rows)


def print_summary(plan):
    """The one-line-per-fact rollup shown at the top of preview and clean."""
    print("Rows in:        %d" % plan.rows_in)
    print("Clean rows out: %d" % plan.rows_out)
    print("Groups merged:  %d" % len(plan.merged_groups))
    print("Conflicts:      %d" % len(plan.conflicts))
    print("Flagged phones: %d" % len(plan.invalid_phones))


def print_clean_table(plan):
    """Show the cleaned, de-duplicated rows as a simple aligned table."""
    rows = plan.clean_rows
    if not rows:
        print("\nNo contacts.")
        return
    name_w = max(len(r["name"]) for r in rows)
    email_w = max(len(r["email"]) for r in rows)
    print("\nClean contacts:")
    for r in rows:
        print("  %-*s  %-*s  %s" % (
            name_w, r["name"] or "(no name)",
            email_w, r["email"] or "(no email)",
            r["phone"] or "(no phone)",
        ))


def cmd_preview(args):
    plan = load_plan(args)
    print("Previewing: %s\n" % args.input)
    print_summary(plan)
    print_clean_table(plan)
    if plan.conflicts or plan.invalid_phones:
        print("\nThere are conflicts or flagged phones. See 'report' for details.")
    print("\nNothing was written. Run 'clean' to save the tidy list.")


def cmd_clean(args):
    plan = load_plan(args)
    print("About to clean: %s\n" % args.input)
    print_summary(plan)
    print_clean_table(plan)

    answer = input("\nWrite the clean list and report? [y/N] ").strip().lower()
    if answer != "y":
        print("Cancelled. Nothing was written. Your input file is untouched.")
        return

    try:
        core.write_clean_csv(args.out, plan.clean_rows, overwrite=args.force)
        core.write_report(args.report, plan, overwrite=args.force)
    except FileExistsError as exc:
        print("\n%s" % exc)
        print("Re-run with --force to overwrite, or move the old file aside.")
        return

    print("\nWrote clean contacts to: %s" % args.out)
    print("Wrote report to:         %s" % args.report)
    print("Your input file was not changed.")


def cmd_report(args):
    plan = load_plan(args)
    print(core.format_report(plan), end="")
    print("\n(Read-only. No files were written.)")


def build_parser():
    parser = argparse.ArgumentParser(
        description="Clean up and de-duplicate a messy contact list, safely.",
    )
    parser.add_argument(
        "--input", default=DEFAULT_INPUT,
        help="CSV of contacts to clean (default: samples/contacts_messy.csv).",
    )
    parser.add_argument(
        "--out", default=DEFAULT_CLEAN,
        help="Where to write the clean CSV (default: contacts_clean.csv).",
    )
    parser.add_argument(
        "--report", default=DEFAULT_REPORT,
        help="Where to write the report (default: merge_report.txt).",
    )
    parser.add_argument(
        "--force", action="store_true",
        help="Allow overwriting existing output files.",
    )

    sub = parser.add_subparsers(dest="command")
    sub.add_parser("preview", help="Show what would change. Writes nothing.")
    sub.add_parser("clean", help="Write the clean list after you confirm.")
    sub.add_parser("report", help="Show the merge and conflict report.")
    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)

    # No subcommand given: default to a friendly preview.
    command = args.command or "preview"

    handlers = {
        "preview": cmd_preview,
        "clean": cmd_clean,
        "report": cmd_report,
    }
    handlers[command](args)


if __name__ == "__main__":
    main()
