"""Core logic for the Contact List Cleaner.

This module is the brain of the project. It holds the pure functions that tidy a
single field (a name, an email, a phone number), decide whether two rows are the
same person, and merge the duplicates into one clean record. Both front ends, the
command line (clean_cli.py) and the menu (clean_menu.py), import from here, so the
logic lives in exactly one place.

The job, in plain terms:
    a messy CSV of contacts in   ->   one clean, de-duplicated CSV out

A messy file is the kind you get when you export contacts from three different
places: the same person typed three ways, JOHN in all caps next to john in all
lower, and phone numbers in every format a human can invent. This tool reads each
row, cleans every field, groups rows that are really the same person, and merges
them. It never changes your input file; it writes a fresh clean copy and a report
of every judgement call it made, so you can check its work.
"""

import csv
import os
import re

# ---------------------------------------------------------------------------
# Settings you can tweak. These are deliberately at the top so a beginner can
# change the behaviour without hunting through the code.
# ---------------------------------------------------------------------------

# The columns we read and write, in order. If your export uses different column
# names, the simplest fix is to rename them to these in your spreadsheet first.
FIELDS = ["name", "email", "phone", "company", "title"]

# Fields that, when two rows disagree on a non-empty value, count as a real
# conflict worth reporting (rather than silently picking one). We do not flag a
# name disagreement because small spelling differences there are expected; the
# point of a conflict is "these two records claim different facts".
CONFLICT_FIELDS = ["company", "title", "phone"]


# ---------------------------------------------------------------------------
# Step 1: clean one field at a time. Each function takes a raw string and
# returns a tidy one. They are pure: same input, same output, no side effects.
# ---------------------------------------------------------------------------

def _collapse_spaces(text):
    """Trim the ends and squeeze any run of inner whitespace down to one space."""
    return " ".join((text or "").split())


def normalize_name(raw):
    """Tidy a person's name.

    "  JOHN   DOE "  -> "John Doe"
    "mary o'brien"   -> "Mary O'Brien"
    """
    return _collapse_spaces(raw).title()


# Pull the address out of a "Display Name <addr@host>" style value. The address
# is whatever sits between the angle brackets.
_ANGLE_EMAIL = re.compile(r"<([^<>]+)>")


def normalize_email(raw):
    """Tidy an email address.

    "  Jane@Acme.com "            -> "jane@acme.com"
    "Jane Doe <jane@acme.com>"    -> "jane@acme.com"
    ""                           -> ""
    """
    text = (raw or "").strip()
    match = _ANGLE_EMAIL.search(text)
    if match:
        text = match.group(1).strip()
    return text.lower()


def normalize_phone(raw):
    """Tidy a phone number into a (formatted, is_valid) pair.

    We throw away everything that is not a digit, drop a leading US country code
    "1" if that leaves ten digits, then format the ten as (555) 123-4567.

    Anything that does not boil down to ten digits is handed back as its bare
    digits with is_valid=False, so the report can flag it instead of pretending
    it cleaned up. An empty value is "valid" (a blank phone is not a problem).

    "+1 (555) 123-4567"  -> ("(555) 123-4567", True)
    "555.123.4567"       -> ("(555) 123-4567", True)
    "555-12"             -> ("55512", False)
    ""                  -> ("", True)
    """
    digits = re.sub(r"\D", "", raw or "")
    if not digits:
        return "", True
    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]
    if len(digits) == 10:
        formatted = "(%s) %s-%s" % (digits[0:3], digits[3:6], digits[6:10])
        return formatted, True
    return digits, False


# ---------------------------------------------------------------------------
# Step 2: turn a raw CSV row into a clean contact record.
# ---------------------------------------------------------------------------

def normalize_contact(row):
    """Clean every field of one row.

    Returns a dict with the five FIELDS plus two bookkeeping keys:
      _phone_valid  whether the phone cleaned up to ten digits
      _raw          the original row, kept so the report can show what came in
    """
    phone, phone_valid = normalize_phone(row.get("phone", ""))
    return {
        "name": normalize_name(row.get("name", "")),
        "email": normalize_email(row.get("email", "")),
        "phone": phone,
        "company": _collapse_spaces(row.get("company", "")),
        "title": _collapse_spaces(row.get("title", "")),
        "_phone_valid": phone_valid,
        "_raw": dict(row),
    }


# ---------------------------------------------------------------------------
# Step 3: decide which rows are the same person.
# ---------------------------------------------------------------------------

def match_key(contact, fallback_id=None):
    """Return a key that is the same for two rows that are the same person.

    We try the most reliable signal first, exactly like the renamer trusts its
    lookup table before guessing:
      1. email  - the strongest signal; two rows with the same email are one person
      2. phone  - next best when an email is missing
      3. name   - last resort when there is nothing else to go on

    A row with none of the three cannot be matched to anything, so it gets a
    unique key (fallback_id) and stands on its own instead of merging with other
    blank rows.
    """
    if contact["email"]:
        return "email:" + contact["email"]
    if contact["phone"]:
        return "phone:" + contact["phone"]
    if contact["name"]:
        return "name:" + contact["name"].lower()
    return "row:%s" % fallback_id


def merge_group(rows):
    """Combine rows that share a match key into one record.

    For each field we keep the first non-empty value we saw. Empty fields get
    filled in from a later row in the group (that is how a row with just a phone
    donates its phone to a row that had only an email). When two rows give
    different non-empty values for a CONFLICT_FIELD, we keep the first and record
    the disagreement so a human can settle it.

    Returns (merged_contact, conflicts) where conflicts is a list of
    (field, [value_seen_first, other_value, ...]).
    """
    merged = {f: "" for f in FIELDS}
    merged["_phone_valid"] = True
    conflicts = []

    for field in FIELDS:
        seen = []  # distinct non-empty values, in first-seen order
        for row in rows:
            value = row[field]
            if value and value not in seen:
                seen.append(value)
        if not seen:
            continue
        merged[field] = seen[0]
        if field == "phone":
            # Carry the validity flag of whichever row donated the phone.
            for row in rows:
                if row["phone"] == seen[0]:
                    merged["_phone_valid"] = row["_phone_valid"]
                    break
        if field in CONFLICT_FIELDS and len(seen) > 1:
            conflicts.append((field, seen))

    return merged, conflicts


# ---------------------------------------------------------------------------
# Step 4: plan the whole clean. This is the read-only "what would happen".
# ---------------------------------------------------------------------------

class MergeGroup:
    """One set of rows that were judged to be the same person."""

    def __init__(self, key, members, merged, conflicts):
        self.key = key
        self.members = members      # the original normalized contacts
        self.merged = merged        # the single record they became
        self.conflicts = conflicts  # list of (field, [values]) disagreements


class CleanPlan:
    """The result of planning a clean: clean rows, plus everything notable."""

    def __init__(self, clean_rows, groups, rows_in):
        self.clean_rows = clean_rows                       # sorted, de-duplicated
        self.groups = groups                               # every MergeGroup
        self.rows_in = rows_in                             # how many came in
        self.rows_out = len(clean_rows)                    # how many remain
        self.merged_groups = [g for g in groups if len(g.members) > 1]
        self.conflicts = [g for g in groups if g.conflicts]
        self.invalid_phones = [r for r in clean_rows
                               if r["phone"] and not r["_phone_valid"]]


def plan_clean(rows):
    """Group rows by person, merge each group, and return a CleanPlan.

    `rows` is a list of raw dicts (as read from the CSV). Nothing is written.
    """
    contacts = [normalize_contact(row) for row in rows]

    # Group while preserving the order keys were first seen, so the output is
    # stable and easy to diff.
    order = []
    buckets = {}
    for index, contact in enumerate(contacts):
        key = match_key(contact, fallback_id=index)
        if key not in buckets:
            buckets[key] = []
            order.append(key)
        buckets[key].append(contact)

    groups = []
    clean_rows = []
    for key in order:
        members = buckets[key]
        merged, conflicts = merge_group(members)
        groups.append(MergeGroup(key, members, merged, conflicts))
        clean_rows.append(merged)

    # Sort the clean output by name (then email) so it reads like a directory.
    clean_rows.sort(key=lambda c: (c["name"].lower(), c["email"]))

    return CleanPlan(clean_rows, groups, rows_in=len(rows))


# ---------------------------------------------------------------------------
# Step 5: read input and write output. These are the only functions that touch
# the disk, and the writers refuse to clobber an existing file unless told to.
# ---------------------------------------------------------------------------

def read_contacts(csv_path):
    """Read the input CSV into a list of raw dicts. The file is only ever read."""
    with open(csv_path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def write_clean_csv(path, rows, overwrite=False):
    """Write the cleaned contacts to a new CSV.

    Refuses to overwrite an existing file unless overwrite=True, so a stray run
    can never quietly destroy a previous result.
    """
    if os.path.exists(path) and not overwrite:
        raise FileExistsError("Refusing to overwrite existing file: %s" % path)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow({f: row[f] for f in FIELDS})


def format_report(plan):
    """Build the plain-English report as a single string.

    Both the on-screen "report" command and the saved merge_report.txt use this,
    so what you read in the terminal is exactly what lands in the file.
    """
    lines = []
    lines.append("Contact cleaning report")
    lines.append("=" * 40)
    lines.append("Rows in:        %d" % plan.rows_in)
    lines.append("Clean rows out: %d" % plan.rows_out)
    lines.append("Groups merged:  %d" % len(plan.merged_groups))
    lines.append("Conflicts:      %d" % len(plan.conflicts))
    lines.append("Flagged phones: %d" % len(plan.invalid_phones))
    lines.append("")

    if plan.merged_groups:
        lines.append("Merged duplicates")
        lines.append("-" * 40)
        for group in plan.merged_groups:
            merged = group.merged
            lines.append("* %s  ->  %s | %s | %s" % (
                merged["name"] or "(no name)",
                merged["email"] or "(no email)",
                merged["phone"] or "(no phone)",
                merged["company"] or "(no company)",
            ))
            for member in group.members:
                raw = member["_raw"]
                lines.append("    from: %s | %s | %s" % (
                    raw.get("name", ""),
                    raw.get("email", ""),
                    raw.get("phone", ""),
                ))
        lines.append("")

    if plan.conflicts:
        lines.append("Conflicts (kept the first value, listed the rest)")
        lines.append("-" * 40)
        for group in plan.conflicts:
            who = group.merged["name"] or group.merged["email"] or "(unknown)"
            for field, values in group.conflicts:
                kept = values[0]
                others = ", ".join(values[1:])
                lines.append("* %s: %s = %r  (also saw: %s)" % (
                    who, field, kept, others))
        lines.append("")

    if plan.invalid_phones:
        lines.append("Phone numbers that did not look like 10 digits")
        lines.append("-" * 40)
        for row in plan.invalid_phones:
            who = row["name"] or row["email"] or "(unknown)"
            lines.append("* %s: %s" % (who, row["phone"]))
        lines.append("")

    if not (plan.merged_groups or plan.conflicts or plan.invalid_phones):
        lines.append("Nothing to merge and nothing to flag. The list was clean.")

    return "\n".join(lines).rstrip() + "\n"


def write_report(path, plan, overwrite=False):
    """Save the report next to the clean CSV. Same no-clobber rule as the CSV."""
    if os.path.exists(path) and not overwrite:
        raise FileExistsError("Refusing to overwrite existing file: %s" % path)
    with open(path, "w", encoding="utf-8") as f:
        f.write(format_report(plan))
