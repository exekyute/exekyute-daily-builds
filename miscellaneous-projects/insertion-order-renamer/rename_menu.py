"""Menu front end for the Insertion Order renamer.

This is the "I do not want to remember commands" way to use the tool. Run it
and you get a numbered menu; type a number and press Enter. It calls the exact
same functions in core.py that the command line version does, so the two front
ends always behave the same.

Run it with:

    python rename_menu.py

Like the command line tool, it works on a safe copy of the samples (the
"samples_work" folder) so you can experiment freely. To work on your own files,
edit the FOLDER value just below.
"""

import os

import core

HERE = os.path.dirname(os.path.abspath(__file__))

# Change these two lines to point the menu at your own files.
FOLDER = os.path.join(HERE, "samples_work")
LOOKUP = os.path.join(HERE, "companies.csv")

SAMPLES = os.path.join(HERE, "samples")
UNDO_LOG = os.path.join(HERE, core.UNDO_LOG_NAME)

SKIP_REASON = {
    core.STATUS_NO_IO: "no IO number found",
    core.STATUS_NO_COMPANY: "company could not be determined",
}


def ensure_work_folder():
    """Seed samples_work from samples the first time, so the menu just works."""
    if FOLDER == os.path.join(HERE, "samples_work") and not os.path.isdir(FOLDER):
        if os.path.isdir(SAMPLES):
            import shutil
            shutil.copytree(SAMPLES, FOLDER)
            print("(Set up a fresh working copy in samples_work/ from samples/)")


def show_plan(plan):
    renames = [p for p in plan if p.status == core.STATUS_OK]
    skips = [p for p in plan if p.status != core.STATUS_OK]

    if renames:
        width = max(len(p.old_name) for p in renames)
        print("\nFiles to rename:")
        for p in renames:
            print("  %-*s  ->  %s" % (width, p.old_name, p.new_name))
    else:
        print("\nFiles to rename: none")

    if skips:
        print("\nSkipped (%d):" % len(skips))
        for p in skips:
            print("  %s  (%s)" % (p.old_name, SKIP_REASON.get(p.status, p.status)))

    print("\nSummary: %d to rename, %d skipped" % (len(renames), len(skips)))
    return renames


def do_preview():
    lookup = core.load_lookup(LOOKUP)
    plan = core.plan_renames(FOLDER, lookup)
    show_plan(plan)
    print("\nNothing was changed.")


def do_apply():
    lookup = core.load_lookup(LOOKUP)
    plan = core.plan_renames(FOLDER, lookup)
    renames = show_plan(plan)
    if not renames:
        print("\nNothing to rename.")
        return
    answer = input("\nProceed with these renames? [y/N] ").strip().lower()
    if answer != "y":
        print("Cancelled. Nothing was changed.")
        return
    undo_entries = core.apply_renames(FOLDER, plan)
    core.write_undo_log(UNDO_LOG, FOLDER, undo_entries)
    print("\nRenamed %d files. Use option 4 to undo." % len(undo_entries))


def do_list():
    names = sorted(
        f for f in os.listdir(FOLDER)
        if os.path.isfile(os.path.join(FOLDER, f))
    )

    def sort_key(name):
        io_number = core.extract_io_number(name)
        return (io_number is None, io_number or "", name)

    print("\nFiles ordered by IO number:")
    for name in sorted(names, key=sort_key):
        io_number = core.extract_io_number(name)
        label = ("IO-" + io_number) if io_number else "(no IO number)"
        print("  %-14s  %s" % (label, name))


def do_undo():
    try:
        restored = core.undo(UNDO_LOG)
    except FileNotFoundError:
        print("\nNothing to undo (no undo log found).")
        return
    print("\nRestored %d files to their previous names." % restored)


MENU = """
==================================================
  Insertion Order Renamer
  Working folder: {folder}
==================================================
  1) Preview   - see what would change
  2) Apply     - rename after you confirm
  3) List      - show files by IO number
  4) Undo      - reverse the last apply
  5) Quit
""".strip()


def main():
    ensure_work_folder()
    actions = {"1": do_preview, "2": do_apply, "3": do_list, "4": do_undo}
    while True:
        print("\n" + MENU.format(folder=FOLDER))
        choice = input("\nChoose 1-5: ").strip()
        if choice == "5":
            print("Goodbye.")
            break
        action = actions.get(choice)
        if action:
            action()
        else:
            print("Please type a number from 1 to 5.")


if __name__ == "__main__":
    main()
