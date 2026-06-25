"""Core logic for the Insertion Order renamer.

This module is the brain of the project. It holds the pure functions that figure
out the new name for a file, plus the small bit of file handling that actually
performs (and can undo) the renames. Both front ends, the command line
(rename_cli.py) and the menu (rename_menu.py), import from here, so the logic
lives in exactly one place.

The job, in plain terms:
    messy file name in   ->   clean, consistent name out

A clean name looks like:
    Acme-Corporation_IO-12345.pdf
    ^company (the sender)  ^IO number, zero padded so it sorts in number order
"""

import csv
import json
import os
import re

# ---------------------------------------------------------------------------
# Settings you can tweak. These are deliberately at the top so a beginner can
# change the output style without hunting through the code.
# ---------------------------------------------------------------------------

# How the new name is built. Swap to "IO-{io}_{company}" to sort by IO number
# across every sender instead of grouping by company first.
NAME_FORMAT = "{company}_IO-{io}"

# IO numbers are padded with leading zeros to this width. Padding is what lets
# names sort in true numeric order when your file explorer sorts them as text
# (so IO-00042 comes before IO-12345).
IO_PAD = 5

# Words that show up in messy names but are not part of the company. We strip
# these out when we have to guess the company from the file name. Lower case.
JUNK_WORDS = {
    "io", "io#", "insertionorder", "insertion", "order",
    "final", "draft", "signed", "copy", "approved",
    "v1", "v2", "v3", "the", "agency", "partners", "corp",
}

# Statuses a planned rename can have.
STATUS_OK = "ok"
STATUS_NO_IO = "skip-no-io"
STATUS_NO_COMPANY = "skip-no-company"

# Name of the undo log written next to the script after an apply.
UNDO_LOG_NAME = "undo_log.json"


# ---------------------------------------------------------------------------
# Step 1: find the IO number inside a messy name.
# ---------------------------------------------------------------------------

# Patterns are tried in order. The first one that matches wins. Each captures
# the run of digits we care about.
#
# When the letters "IO" sit right next to the number we trust even a short
# number (the "IO" label is strong evidence). A bare number with no "IO" label
# has to be at least 3 digits long, so we do not mistake a version number like
# "v2" for an IO number. \b is a "word boundary".
_IO_PATTERNS = [
    re.compile(r"io[\s#_\-]*(\d{1,8})", re.IGNORECASE),  # IO 42, IO#12345, IO_24680
    re.compile(r"(\d{1,8})[\s#_\-]*io", re.IGNORECASE),  # 12345-IO, 99001 io
    # A bare number, last resort. We use look-arounds instead of \b because \b
    # counts the underscore as a letter, which would miss "13579_UMBRELLA".
    re.compile(r"(?<![A-Za-z0-9])(\d{3,8})(?![A-Za-z0-9])"),
]


def extract_io_number(filename):
    """Return the IO number as a zero-padded string, or None if none is found.

    Examples:
        "IO 12345 Acme Corp.pdf"  -> "12345"
        "12345-Acme-IO.pdf"       -> "12345"
        "scanned_document.pdf"    -> None
    """
    stem = os.path.splitext(filename)[0]
    for pattern in _IO_PATTERNS:
        match = pattern.search(stem)
        if match:
            return match.group(1).zfill(IO_PAD)
    return None


# ---------------------------------------------------------------------------
# Step 2: turn a company name into a clean filename piece.
# ---------------------------------------------------------------------------

def slugify_company(name):
    """Turn a company name into a safe, hyphenated filename piece.

    "Acme Corporation"  -> "Acme-Corporation"
    "Globex Inc."       -> "Globex-Inc"
    """
    # Keep letters, numbers and spaces; drop everything else.
    cleaned = re.sub(r"[^A-Za-z0-9 ]+", " ", name)
    words = cleaned.split()
    return "-".join(words)


# ---------------------------------------------------------------------------
# Step 3: decide which company a file belongs to.
# ---------------------------------------------------------------------------

def load_lookup(csv_path):
    """Read companies.csv into a dict of {padded_io_number: company name}.

    Returns an empty dict if the file does not exist, so the tool still runs
    (it just falls back to guessing for every file).
    """
    lookup = {}
    if not os.path.exists(csv_path):
        return lookup
    with open(csv_path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            io_number = (row.get("io_number") or "").strip()
            company = (row.get("company") or "").strip()
            if io_number and company:
                lookup[io_number.zfill(IO_PAD)] = company
    return lookup


def _guess_company_from_name(filename, io_number):
    """Best effort: pull the company out of the file name itself.

    We remove the extension, the IO number, and any junk words, then keep
    what is left over. Returns "" if nothing usable remains.
    """
    stem = os.path.splitext(filename)[0]
    # Split on anything that is not a letter or digit.
    tokens = re.split(r"[^A-Za-z0-9]+", stem)
    kept = []
    for token in tokens:
        if not token:
            continue
        low = token.lower()
        if low in JUNK_WORDS:
            continue
        if token.isdigit():            # the IO number and any other numbers
            continue
        kept.append(token)
    return " ".join(kept)


def resolve_company(io_number, filename, lookup):
    """Find the clean company name for a file.

    Lookup table first (most reliable). If the IO number is not listed, fall
    back to guessing from the file name. Returns None if we end up with nothing.
    """
    if io_number and io_number in lookup:
        return lookup[io_number]
    guess = _guess_company_from_name(filename, io_number)
    if guess:
        # Title-case so "umbrella media" becomes "Umbrella Media".
        return guess.title()
    return None


# ---------------------------------------------------------------------------
# Step 4: build the new name and plan all the renames.
# ---------------------------------------------------------------------------

def build_new_name(company, io_number, ext):
    """Combine the pieces into the final filename, including the dot extension."""
    stem = NAME_FORMAT.format(company=slugify_company(company), io=io_number)
    return stem + ext


class Rename:
    """One planned rename: where it came from, where it is going, and why."""

    def __init__(self, old_name, new_name, status, io_number):
        self.old_name = old_name
        self.new_name = new_name      # None when the file is being skipped
        self.status = status
        self.io_number = io_number    # None when no IO number was found


def plan_renames(folder, lookup):
    """Look at every file in `folder` and decide its new name.

    Returns a list of Rename objects. Files we cannot handle are included with
    a skip status and an explanation, so the caller can report them instead of
    silently ignoring them. Name collisions get a numeric suffix (-2, -3, ...).
    """
    plan = []
    taken = set()  # new names already claimed in this run, to avoid clashes

    names = sorted(
        f for f in os.listdir(folder)
        if os.path.isfile(os.path.join(folder, f))
    )

    for old_name in names:
        io_number = extract_io_number(old_name)
        if not io_number:
            plan.append(Rename(old_name, None, STATUS_NO_IO, None))
            continue

        company = resolve_company(io_number, old_name, lookup)
        if not company:
            plan.append(Rename(old_name, None, STATUS_NO_COMPANY, io_number))
            continue

        ext = os.path.splitext(old_name)[1].lower()
        new_name = build_new_name(company, io_number, ext)
        new_name = _dedupe(new_name, taken, ext)
        taken.add(new_name.lower())
        plan.append(Rename(old_name, new_name, STATUS_OK, io_number))

    return plan


def _dedupe(new_name, taken, ext):
    """If new_name is already claimed, append -2, -3, ... until it is unique."""
    if new_name.lower() not in taken:
        return new_name
    stem = new_name[: -len(ext)] if ext else new_name
    counter = 2
    while True:
        candidate = "%s-%d%s" % (stem, counter, ext)
        if candidate.lower() not in taken:
            return candidate
        counter += 1


# ---------------------------------------------------------------------------
# Step 5: actually rename, and be able to undo it.
# ---------------------------------------------------------------------------

def apply_renames(folder, plan):
    """Perform the renames marked `ok`. Return undo entries: list of [new, old].

    Skipped files are left untouched. The returned list, fed to write_undo_log,
    is what makes a one-command undo possible.
    """
    undo_entries = []
    for item in plan:
        if item.status != STATUS_OK:
            continue
        if item.old_name == item.new_name:
            continue
        src = os.path.join(folder, item.old_name)
        dst = os.path.join(folder, item.new_name)
        os.rename(src, dst)
        undo_entries.append([item.new_name, item.old_name])
    return undo_entries


def write_undo_log(log_path, folder, undo_entries):
    """Save what we just did so it can be reversed later."""
    data = {"folder": folder, "renames": undo_entries}
    with open(log_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def undo(log_path):
    """Reverse the most recent apply using the saved log.

    Returns the number of files restored. Raises FileNotFoundError if there is
    no log to undo.
    """
    if not os.path.exists(log_path):
        raise FileNotFoundError("No undo log found at %s" % log_path)
    with open(log_path, encoding="utf-8") as f:
        data = json.load(f)
    folder = data["folder"]
    restored = 0
    # Reverse order is safest in case of chained names.
    for new_name, old_name in reversed(data["renames"]):
        src = os.path.join(folder, new_name)
        dst = os.path.join(folder, old_name)
        if os.path.exists(src):
            os.rename(src, dst)
            restored += 1
    os.remove(log_path)
    return restored
