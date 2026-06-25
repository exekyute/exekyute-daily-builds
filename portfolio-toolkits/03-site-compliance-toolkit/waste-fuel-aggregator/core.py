"""Core logic for the Regional Waste and Fuel Log Aggregator.

This module is the brain of the tool. Job sites send in a monthly spreadsheet of
their waste tonnage and fuel use, but every site names its columns differently.
One site writes "Waste (tons)", another writes "Waste Tonnage", a third writes
"waste_tons". This module reads all of those files, translates each site's column
names into one shared set of names, checks every row, drops the bad rows with a
clear reason, and combines the good rows into one unified operational ledger.

The job, in plain terms:
    many messy monthly site files   ->   one clean, validated ledger

The CLI front end (aggregate_cli.py) imports from here, so the logic lives in
exactly one place and can be tested on its own.
"""

import csv
import os
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

# ---------------------------------------------------------------------------
# Settings you can tweak. These sit at the top so you can change behaviour
# without hunting through the code.
# ---------------------------------------------------------------------------

# The four columns every row in the final ledger will have. These are the
# "canonical" names: the single agreed spelling we translate every site into.
CANONICAL_COLUMNS = ("site", "month", "waste_tons", "fuel_gallons")

# How many decimal places we keep for quantities, and the rounding style.
QUANTITY_PLACES = Decimal("0.01")

# The translation table. For each canonical column on the left, we list every
# header spelling a site might use on the right. Matching is case-insensitive
# and ignores surrounding spaces, so "  Waste (Tons) " still matches.
HEADER_SYNONYMS = {
    "site": ["site", "location", "facility", "job site"],
    "month": ["month", "reporting month", "period"],
    "waste_tons": ["waste_tons", "waste (tons)", "waste tonnage", "waste"],
    "fuel_gallons": ["fuel_gallons", "fuel (gal)", "diesel gallons", "fuel used", "fuel"],
}


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------

def _clean(text):
    """Trim spaces from a value, treating None as an empty string."""
    if text is None:
        return ""
    return str(text).strip()


def format_quantity(value):
    """Return a Decimal as a plain fixed-point string, for example '12.50'.

    We never want scientific notation (like '1.2E+1') in an operational ledger,
    so quantities are rounded to two places and formatted explicitly.
    """
    rounded = value.quantize(QUANTITY_PLACES, rounding=ROUND_HALF_UP)
    return f"{rounded:.2f}"


# ---------------------------------------------------------------------------
# Header normalisation: turn a site's column names into our canonical names
# ---------------------------------------------------------------------------

def build_header_map(fieldnames):
    """Map a file's real column names onto our canonical column names.

    Returns a tuple of (header_map, missing), where:
      header_map is a dict like {"site": "Location", "month": "Reporting Month", ...}
                 mapping each canonical name to the actual column in this file,
      missing    is the list of canonical columns this file does not provide.

    A file is only usable if nothing is missing.
    """
    # Flip the synonym table into a lookup: spelling -> canonical name.
    lookup = {}
    for canonical, spellings in HEADER_SYNONYMS.items():
        for spelling in spellings:
            lookup[spelling] = canonical

    header_map = {}
    for name in fieldnames or []:
        key = _clean(name).lower()
        canonical = lookup.get(key)
        # If two columns map to the same canonical name, keep the first one.
        if canonical and canonical not in header_map:
            header_map[canonical] = name

    missing = [c for c in CANONICAL_COLUMNS if c not in header_map]
    return header_map, missing


# ---------------------------------------------------------------------------
# Value validation
# ---------------------------------------------------------------------------

def parse_month(text):
    """Validate a reporting month written as YYYY-MM.

    Returns the cleaned string on success, or raises ValueError on a bad value.
    We keep months as text (not dates) because a ledger groups by calendar
    month, not by a specific day.
    """
    value = _clean(text)
    parts = value.split("-")
    if len(parts) != 2:
        raise ValueError(f"month '{value}' is not in YYYY-MM form")
    year, month = parts
    if len(year) != 4 or not year.isdigit() or not month.isdigit():
        raise ValueError(f"month '{value}' is not in YYYY-MM form")
    if not (1 <= int(month) <= 12):
        raise ValueError(f"month '{value}' has a month outside 01-12")
    return value


def parse_quantity(text, field_name):
    """Validate a non-negative quantity and return it as a Decimal.

    Raises ValueError if the value is blank, not a number, or negative. A
    negative tonnage or gallon count is not possible in the field, so we reject
    it rather than letting it poison the totals.
    """
    value = _clean(text)
    if value == "":
        raise ValueError(f"{field_name} is blank")
    try:
        amount = Decimal(value)
    except InvalidOperation:
        raise ValueError(f"{field_name} '{value}' is not a number")
    if amount < 0:
        raise ValueError(f"{field_name} '{value}' is negative")
    return amount


def validate_row(raw_row, header_map):
    """Turn one raw file row into a clean ledger record, or explain the problem.

    Returns (record, error). Exactly one of them is filled in:
      on success: ({"site":..., "month":..., "waste_tons":Decimal, "fuel_gallons":Decimal}, None)
      on failure: (None, "a short human reason")
    """
    site = _clean(raw_row.get(header_map["site"]))
    if site == "":
        return None, "missing site"

    try:
        month = parse_month(raw_row.get(header_map["month"]))
        waste = parse_quantity(raw_row.get(header_map["waste_tons"]), "waste_tons")
        fuel = parse_quantity(raw_row.get(header_map["fuel_gallons"]), "fuel_gallons")
    except ValueError as problem:
        return None, str(problem)

    record = {
        "site": site,
        "month": month,
        "waste_tons": waste,
        "fuel_gallons": fuel,
    }
    return record, None


# ---------------------------------------------------------------------------
# Combining many files into one ledger
# ---------------------------------------------------------------------------

def find_input_files(folder):
    """Return the sorted list of .csv files in a folder (not recursive)."""
    if not os.path.isdir(folder):
        return []
    names = [n for n in os.listdir(folder) if n.lower().endswith(".csv")]
    return [os.path.join(folder, n) for n in sorted(names)]


def read_rows(path):
    """Read a CSV file and return (fieldnames, rows) using the header row.

    utf-8-sig quietly strips the byte-order mark some spreadsheet exports add,
    so the first column name does not arrive with hidden characters attached.
    """
    with open(path, "r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
        return reader.fieldnames, rows


def combine_files(paths):
    """Read every file, validate every row, deduplicate, and sort.

    Returns a result dict with:
      records       the clean ledger rows, sorted by site then month
      skipped       list of (source, reason) for rows that were dropped
      files_used    filenames that contributed at least the right columns
      files_skipped list of (filename, reason) for unusable files
      sites         sorted list of the distinct site names in the ledger

    Deduplication key is site + month: if the same site reports the same month
    twice, the first occurrence is kept and the later one is reported.
    """
    records = []
    skipped = []
    files_used = []
    files_skipped = []
    seen_keys = set()

    for path in paths:
        name = os.path.basename(path)
        fieldnames, rows = read_rows(path)
        header_map, missing = build_header_map(fieldnames)

        if missing:
            files_skipped.append((name, "missing column(s): " + ", ".join(missing)))
            continue

        files_used.append(name)
        for index, raw_row in enumerate(rows, start=2):  # start=2: row 1 is the header
            source = f"{name} row {index}"
            record, error = validate_row(raw_row, header_map)
            if error:
                skipped.append((source, error))
                continue

            key = (record["site"], record["month"])
            if key in seen_keys:
                skipped.append((source, f"duplicate of {record['site']} {record['month']}"))
                continue

            seen_keys.add(key)
            records.append(record)

    records.sort(key=lambda r: (r["site"], r["month"]))
    sites = sorted({r["site"] for r in records})

    return {
        "records": records,
        "skipped": skipped,
        "files_used": files_used,
        "files_skipped": files_skipped,
        "sites": sites,
    }


# ---------------------------------------------------------------------------
# Writing the ledger out
# ---------------------------------------------------------------------------

def write_ledger(records, path):
    """Write the clean records to a CSV with the canonical header row."""
    folder = os.path.dirname(path)
    if folder and not os.path.isdir(folder):
        os.makedirs(folder)

    with open(path, "w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(CANONICAL_COLUMNS)
        for record in records:
            writer.writerow([
                record["site"],
                record["month"],
                format_quantity(record["waste_tons"]),
                format_quantity(record["fuel_gallons"]),
            ])
