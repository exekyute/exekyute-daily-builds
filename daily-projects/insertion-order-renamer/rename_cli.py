"""Command line front end for the Insertion Order renamer.

This is the "type a command" way to use the tool. It does no real thinking of
its own; it reads your command, calls the functions in core.py, and prints the
results. Keeping the logic in core.py means this file stays short and easy.

Quick start (run these from the project folder):

    python rename_cli.py preview     # see what WOULD change, nothing renamed
    python rename_cli.py apply       # preview, then rename after you confirm
    python rename_cli.py list        # list files in IO-number order
    python rename_cli.py undo        # reverse the last apply

By default it works on a safe copy of the samples (the "samples_work" folder),
so you can experiment without touching the originals. Point it at a real folder
of your own with  --folder "C:\\path\\to\\your\\IOs".
"""

import argparse
import os
import shutil
import sys

import core

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_SAMPLES = os.path.join(HERE, "samples")
DEFAULT_WORK = os.path.join(HERE, "samples_work")
DEFAULT_LOOKUP = os.path.join(HERE, "companies.csv")
UNDO_LOG = os.path.join(HERE, core.UNDO_LOG_NAME)

# How each skip status reads in the preview.
SKIP_REASON = {
    core.STATUS_NO_IO: "no IO number found",
    core.STATUS_NO_COMPANY: "company could not be determined",
}


def ensure_work_folder(folder):
    """If we are about to use the default work folder and it is missing,
    seed it with a fresh copy of the samples so the demo just works."""
    if folder == DEFAULT_WORK and not os.path.isdir(DEFAULT_WORK):
        if os.path.isdir(DEFAULT_SAMPLES):
            shutil.copytree(DEFAULT_SAMPLES, DEFAULT_WORK)
            print("(Set up a fresh working copy in samples_work/ from samples/)\n")


def print_plan(plan):
    """Show the old -> new table plus a list of anything being skipped."""
    renames = [p for p in plan if p.status == core.STATUS_OK]
    skips = [p for p in plan if p.status != core.STATUS_OK]

    if renames:
        width = max(len(p.old_name) for p in renames)
        print("Files to rename:")
        for p in renames:
            print("  %-*s  ->  %s" % (width, p.old_name, p.new_name))
    else:
        print("Files to rename: none")

    if skips:
        print("\nSkipped (%d):" % len(skips))
        for p in skips:
            reason = SKIP_REASON.get(p.status, p.status)
            print("  %s  (%s)" % (p.old_name, reason))

    print("\nSummary: %d to rename, %d skipped" % (len(renames), len(skips)))


def cmd_preview(args):
    folder = args.folder
    ensure_work_folder(folder)
    lookup = core.load_lookup(args.lookup)
    plan = core.plan_renames(folder, lookup)
    print("Previewing folder: %s\n" % folder)
    print_plan(plan)
    print("\nNothing was changed. Run 'apply' to perform these renames.")


def cmd_apply(args):
    folder = args.folder
    ensure_work_folder(folder)
    lookup = core.load_lookup(args.lookup)
    plan = core.plan_renames(folder, lookup)
    print("About to rename in folder: %s\n" % folder)
    print_plan(plan)

    if not any(p.status == core.STATUS_OK for p in plan):
        print("\nNothing to rename.")
        return

    answer = input("\nProceed with these renames? [y/N] ").strip().lower()
    if answer != "y":
        print("Cancelled. Nothing was changed.")
        return

    undo_entries = core.apply_renames(folder, plan)
    core.write_undo_log(UNDO_LOG, folder, undo_entries)
    print("\nRenamed %d files." % len(undo_entries))
    print("Undo this with:  python rename_cli.py undo")


def cmd_list(args):
    folder = args.folder
    ensure_work_folder(folder)
    names = sorted(
        f for f in os.listdir(folder)
        if os.path.isfile(os.path.join(folder, f))
    )
    # Sort by IO number; files without one sink to the bottom.
    def sort_key(name):
        io_number = core.extract_io_number(name)
        return (io_number is None, io_number or "", name)

    print("Files in %s, ordered by IO number:\n" % folder)
    for name in sorted(names, key=sort_key):
        io_number = core.extract_io_number(name)
        label = ("IO-" + io_number) if io_number else "(no IO number)"
        print("  %-14s  %s" % (label, name))


def cmd_undo(args):
    try:
        restored = core.undo(UNDO_LOG)
    except FileNotFoundError:
        print("Nothing to undo (no undo log found).")
        return
    print("Restored %d files to their previous names." % restored)


def build_parser():
    parser = argparse.ArgumentParser(
        description="Clean up messy insertion order file names, safely.",
    )
    parser.add_argument(
        "--folder", default=DEFAULT_WORK,
        help="Folder of files to work on (default: samples_work).",
    )
    parser.add_argument(
        "--lookup", default=DEFAULT_LOOKUP,
        help="CSV mapping IO number to company (default: companies.csv).",
    )

    sub = parser.add_subparsers(dest="command")
    sub.add_parser("preview", help="Show what would change. Renames nothing.")
    sub.add_parser("apply", help="Rename after showing a preview and confirming.")
    sub.add_parser("list", help="List files ordered by IO number.")
    sub.add_parser("undo", help="Reverse the most recent apply.")
    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)

    # No subcommand given: default to a friendly preview.
    command = args.command or "preview"

    handlers = {
        "preview": cmd_preview,
        "apply": cmd_apply,
        "list": cmd_list,
        "undo": cmd_undo,
    }
    handlers[command](args)


if __name__ == "__main__":
    main()
