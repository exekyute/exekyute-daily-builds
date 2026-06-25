"""Core logic for the Regulatory Deadline Monitor.

This module is the brain of the tool. It reads a log of environmental compliance
requirements, each with a due date, and compares every due date to a chosen
"today" so it can sort the work by urgency: what is overdue, what is due today,
what is due soon, and what is still upcoming. It can also read the unified ledger
that the waste and fuel aggregator builds and flag any site that has operational
activity but no tracked compliance deadline.

The job, in plain terms:
    a list of due dates + today   ->   an urgency-sorted compliance dashboard

The CLI front end (monitor_cli.py) imports from here, so the logic lives in one
place and can be tested on its own.
"""

import csv
import os
from datetime import date

# ---------------------------------------------------------------------------
# Settings you can tweak. These sit at the top so the behaviour is easy to find.
# ---------------------------------------------------------------------------

# An open item due within this many days (and not yet overdue) counts as DUE SOON.
DUE_SOON_DAYS = 14

# The columns the compliance log must provide.
REQUIRED_COLUMNS = ("site", "requirement", "due_date", "status")

# The two statuses we understand. Anything else is treated as "open" and reported.
VALID_STATUSES = ("open", "complete")

# The urgency band names, in the order they should be shown (most urgent first).
OVERDUE = "OVERDUE"
DUE_TODAY = "DUE TODAY"
DUE_SOON = "DUE SOON"
UPCOMING = "UPCOMING"
COMPLETE = "COMPLETE"

BAND_ORDER = (OVERDUE, DUE_TODAY, DUE_SOON, UPCOMING, COMPLETE)


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------

def _clean(text):
    """Trim spaces from a value, treating None as an empty string."""
    if text is None:
        return ""
    return str(text).strip()


def parse_date(text):
    """Validate a date written strictly as YYYY-MM-DD and return a date object.

    Raises ValueError on anything else. We insist on the YYYY-MM-DD shape (with
    leading zeros) so a date is never ambiguous: 2026-06-06 can only mean one day,
    while 06/06/2026 or 6-6-26 could be read more than one way.
    """
    value = _clean(text)
    parts = value.split("-")
    if len(parts) != 3:
        raise ValueError(f"date '{value}' is not in YYYY-MM-DD form")
    year, month, day = parts
    if len(year) != 4 or len(month) != 2 or len(day) != 2:
        raise ValueError(f"date '{value}' is not in YYYY-MM-DD form")
    if not (year.isdigit() and month.isdigit() and day.isdigit()):
        raise ValueError(f"date '{value}' is not in YYYY-MM-DD form")
    try:
        return date(int(year), int(month), int(day))
    except ValueError:
        raise ValueError(f"date '{value}' is not a real calendar date")


def describe_days(days_until):
    """Turn a day count into a short, unambiguous phrase."""
    if days_until < 0:
        count = abs(days_until)
        return f"{count} day overdue" if count == 1 else f"{count} days overdue"
    if days_until == 0:
        return "due today"
    if days_until == 1:
        return "due in 1 day"
    return f"due in {days_until} days"


# ---------------------------------------------------------------------------
# Reading and validating the compliance log
# ---------------------------------------------------------------------------

def validate_log_row(raw_row):
    """Turn one raw log row into a clean record, or explain the problem.

    Returns (record, error, note):
      record is a dict with site, requirement, due_date (a date), status, or None
      error  is a short reason the row was rejected, or None
      note   is a non-fatal remark (for example an unknown status), or None
    """
    site = _clean(raw_row.get("site"))
    requirement = _clean(raw_row.get("requirement"))
    status_raw = _clean(raw_row.get("status")).lower()

    if site == "":
        return None, "missing site", None
    if requirement == "":
        return None, "missing requirement", None

    try:
        due_date = parse_date(raw_row.get("due_date"))
    except ValueError as problem:
        return None, str(problem), None

    note = None
    status = status_raw
    if status not in VALID_STATUSES:
        note = f"unknown status '{status_raw or '(blank)'}' treated as open"
        status = "open"

    record = {
        "site": site,
        "requirement": requirement,
        "due_date": due_date,
        "status": status,
    }
    return record, None, note


def load_log(path):
    """Read the compliance log and validate every row.

    Returns a dict with:
      records  the clean rows kept (each a dict)
      skipped  list of (source, reason) for rows that were dropped
      notes    list of (source, remark) for rows kept with an adjustment
    Raises FileNotFoundError if the file is missing, or ValueError if the header
    is missing a required column.
    """
    if not os.path.isfile(path):
        raise FileNotFoundError(path)

    records = []
    skipped = []
    notes = []
    seen_keys = set()

    with open(path, "r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        fieldnames = [_clean(name).lower() for name in (reader.fieldnames or [])]
        missing = [c for c in REQUIRED_COLUMNS if c not in fieldnames]
        if missing:
            raise ValueError("log is missing column(s): " + ", ".join(missing))

        for index, raw_row in enumerate(reader, start=2):  # row 1 is the header
            # Normalise the keys to lower case so the column names are forgiving.
            row = {_clean(k).lower(): v for k, v in raw_row.items()}
            source = f"row {index}"
            record, error, note = validate_log_row(row)
            if error:
                skipped.append((source, error))
                continue
            key = (record["site"], record["requirement"])
            if key in seen_keys:
                skipped.append((source, f"duplicate of {record['site']} / {record['requirement']}"))
                continue
            seen_keys.add(key)
            if note:
                notes.append((source, note))
            records.append(record)

    return {"records": records, "skipped": skipped, "notes": notes}


# ---------------------------------------------------------------------------
# Classifying urgency and building the dashboard
# ---------------------------------------------------------------------------

def classify(due_date, today, due_soon_days=DUE_SOON_DAYS):
    """Return the urgency band for an open item and the day count.

    Returns (band, days_until) where days_until is positive in the future,
    zero today, and negative in the past.
    """
    days_until = (due_date - today).days
    if days_until < 0:
        return OVERDUE, days_until
    if days_until == 0:
        return DUE_TODAY, days_until
    if days_until <= due_soon_days:
        return DUE_SOON, days_until
    return UPCOMING, days_until


def build_dashboard(records, today, due_soon_days=DUE_SOON_DAYS):
    """Group records into urgency bands, each sorted by due date then site.

    Completed items go into the COMPLETE band regardless of date. Returns a dict
    mapping each band name to a list of item dicts that carry the day count.
    """
    bands = {name: [] for name in BAND_ORDER}

    for record in records:
        days_until = (record["due_date"] - today).days
        if record["status"] == "complete":
            band = COMPLETE
        else:
            band, days_until = classify(record["due_date"], today, due_soon_days)
        item = dict(record)
        item["days_until"] = days_until
        item["band"] = band
        bands[band].append(item)

    for name in BAND_ORDER:
        bands[name].sort(key=lambda i: (i["due_date"], i["site"]))

    return bands


# ---------------------------------------------------------------------------
# Cross-check against the aggregator's unified ledger
# ---------------------------------------------------------------------------

def load_ledger_sites(path):
    """Return the sorted distinct site names from a unified ledger CSV.

    Returns None if the file does not exist, so the caller can tell the
    difference between "no ledger to check" and "a ledger with no sites".
    """
    if not os.path.isfile(path):
        return None
    sites = set()
    with open(path, "r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        for raw_row in reader:
            row = {_clean(k).lower(): v for k, v in raw_row.items()}
            site = _clean(row.get("site"))
            if site:
                sites.add(site)
    return sorted(sites)


def cross_check(log_records, ledger_sites):
    """Find sites that have ledger activity but no compliance deadline tracked.

    Returns the sorted list of those sites (the compliance gaps).
    """
    if not ledger_sites:
        return []
    tracked = {record["site"] for record in log_records}
    return sorted(set(ledger_sites) - tracked)
