"""Menu front end for the Contact List Cleaner.

If you would rather not remember commands, run this and type a number. It does
the same three things as clean_cli.py and shares all of its logic, so you never
have to pick one front end over the other.

    python clean_menu.py
"""

import argparse

import clean_cli


def make_args():
    """Build the same default settings the command line uses."""
    return argparse.Namespace(
        input=clean_cli.DEFAULT_INPUT,
        out=clean_cli.DEFAULT_CLEAN,
        report=clean_cli.DEFAULT_REPORT,
        force=False,
    )


MENU = """
Contact List Cleaner
  1) Preview  - see what would change, write nothing
  2) Clean    - write the tidy list after you confirm
  3) Report   - show the merge and conflict report
  4) Quit
"""


def main():
    args = make_args()
    while True:
        print(MENU)
        choice = input("Choose 1-4: ").strip()
        print()
        if choice == "1":
            clean_cli.cmd_preview(args)
        elif choice == "2":
            clean_cli.cmd_clean(args)
        elif choice == "3":
            clean_cli.cmd_report(args)
        elif choice == "4":
            print("Bye.")
            return
        else:
            print("Please type 1, 2, 3, or 4.")
        print("\n" + "-" * 50)


if __name__ == "__main__":
    main()
