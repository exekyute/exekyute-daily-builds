"""Interactive front end for the Operational Field Audit Validator.

This file does the talking. It asks the inspector each question in turn, and for
every answer it calls the matching validator in core.py. If the answer is not
valid it explains why and asks again, looping until a good value is given, so a
typo never crashes the tool and never lands in the log. When every answer is in,
it shows a summary, asks for a final confirmation, and appends one timestamped
line to audit_log.txt.

Usage:
    python audit_cli.py
    python audit_cli.py --log audit_log.txt
"""

import argparse
import os
from datetime import datetime

import core
from questions import QUESTIONS

HERE = os.path.dirname(__file__)
DEFAULT_LOG = os.path.join(HERE, "audit_log.txt")


def ask_one(question, read=input, write=print):
    """Ask a single question and keep asking until the answer is valid.

    read and write are passed in so the loop can be exercised in a test, but by
    default they are the real input() and print().
    """
    while True:
        raw = read(f"{question['prompt']}: ")
        value, error = core.validate_answer(question, raw)
        if error is None:
            return value
        write(f"  not accepted: {error}")


def run_interview(questions, read=input, write=print):
    """Ask every question and return a dict of clean answers."""
    answers = {}
    for question in questions:
        answers[question["key"]] = ask_one(question, read=read, write=write)
    return answers


def confirm(read=input):
    """Ask the inspector to confirm. Returns True only for a clear yes."""
    reply = read("Save this audit entry? Type y to save, anything else to cancel: ")
    return core._clean(reply).lower() in ("y", "yes")


def main():
    parser = argparse.ArgumentParser(
        description="Interactive field audit questionnaire that records valid entries."
    )
    parser.add_argument("--log", default=DEFAULT_LOG,
                        help="the text file to append entries to (default: audit_log.txt)")
    args = parser.parse_args()

    print("OPERATIONAL FIELD AUDIT")
    print("=" * 40)
    print("Answer each question. Invalid answers are explained and asked again.")
    print()

    try:
        answers = run_interview(QUESTIONS)
    except (EOFError, KeyboardInterrupt):
        print("\nCancelled. Nothing was saved.")
        return

    # Show a summary before saving.
    print()
    print("Please review this entry:")
    for question in QUESTIONS:
        value = answers[question["key"]]
        shown = core._format_value(question, value)
        print(f"  {question['key']:<16}: {shown}")
    print()

    if not confirm():
        print("Cancelled. Nothing was saved.")
        return

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = core.format_record(QUESTIONS, answers, timestamp)
    with open(args.log, "a", encoding="utf-8") as handle:
        handle.write(line + "\n")

    print()
    print(f"Saved. One entry was appended to {args.log}")
    print(f"  {line}")


if __name__ == "__main__":
    main()
