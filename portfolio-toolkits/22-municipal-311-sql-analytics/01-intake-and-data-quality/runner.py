"""Intake and data-quality runner for the 311 service-request analytics repo.

Builds an in-memory SQLite database from a raw request CSV, runs the data-quality
queries in queries.sql, prints what each one found, checks the counts against the
hand-checked numbers in spec.md, and writes the clean rows to clean_requests.csv
for the backlog and SLA tools to read.

Standard library only: csv, sqlite3, os, sys, datetime. Run it with:

    python runner.py
    python runner.py bad-requests.csv
"""

import csv
import os
import re
import sqlite3
import sys
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
SCHEMA_FILE = os.path.join(HERE, "schema.sql")
QUERIES_FILE = os.path.join(HERE, "queries.sql")
DEFAULT_INPUT = os.path.join(HERE, "sample-requests.csv")
CLEAN_OUTPUT = os.path.join(HERE, "clean_requests.csv")

REQUIRED_COLUMNS = [
    "request_id",
    "opened_date",
    "closed_date",
    "category",
    "department",
    "ward",
    "status",
]

# The numbers the sample data is built to produce. The runner checks against
# these so a passing run is proof the queries still behave. See spec.md.
EXPECTED = {
    "duplicate_id_count": 1,      # R-1004 reported twice
    "missing_field_count": 1,     # R-6001 has no category
    "closed_before_count": 1,     # R-6002 closed before it opened
    "status_inconsistent_count": 1,  # R-6003 is Closed with no close date
    "clean_count": 14,
}

DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def valid_date(value):
    """Return True if value is a real YYYY-MM-DD date."""
    if not DATE_RE.match(value):
        return False
    try:
        datetime.strptime(value, "%Y-%m-%d")
        return True
    except ValueError:
        return False


def load_rows(path):
    """Read the raw CSV. Empty cells become NULL. A malformed date stops the run
    with a clear message before any analysis, so a broken file never loads."""
    with open(path, newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        missing = [c for c in REQUIRED_COLUMNS if c not in (reader.fieldnames or [])]
        if missing:
            raise ValueError(
                "Input is missing required columns: " + ", ".join(missing)
            )
        rows = []
        for line_no, raw in enumerate(reader, start=2):
            row = {c: (raw.get(c) or "").strip() for c in REQUIRED_COLUMNS}
            for field in ("opened_date", "closed_date"):
                if row[field] and not valid_date(row[field]):
                    raise ValueError(
                        "Row %d has an invalid %s: %r. Dates must be YYYY-MM-DD."
                        % (line_no, field, row[field])
                    )
            rows.append(row)
        return rows


def build_db(rows):
    conn = sqlite3.connect(":memory:")
    with open(SCHEMA_FILE, encoding="utf-8") as handle:
        conn.executescript(handle.read())
    for seq, row in enumerate(rows, start=1):
        conn.execute(
            "INSERT INTO raw_requests "
            "(load_seq, request_id, opened_date, closed_date, category, department, ward, status) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                seq,
                row["request_id"] or None,
                row["opened_date"] or None,
                row["closed_date"] or None,
                row["category"] or None,
                row["department"] or None,
                row["ward"] or None,
                row["status"] or None,
            ),
        )
    conn.commit()
    return conn


def parse_queries(path):
    """Split queries.sql into named blocks on the '-- name:' markers."""
    blocks = {}
    name = None
    buffer = []
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            marker = line.strip()
            if marker.startswith("-- name:"):
                if name:
                    blocks[name] = "".join(buffer).strip()
                name = marker.split(":", 1)[1].strip()
                buffer = []
            elif name:
                buffer.append(line)
    if name:
        blocks[name] = "".join(buffer).strip()
    return blocks


def print_table(title, columns, rows):
    print("\n" + title)
    if not rows:
        print("  (no rows)")
        return
    widths = [len(c) for c in columns]
    for row in rows:
        for i, cell in enumerate(row):
            widths[i] = max(widths[i], len("" if cell is None else str(cell)))
    header = "  " + " | ".join(c.ljust(widths[i]) for i, c in enumerate(columns))
    print(header)
    print("  " + "-+-".join("-" * w for w in widths))
    for row in rows:
        cells = ["" if c is None else str(c) for c in row]
        print("  " + " | ".join(cells[i].ljust(widths[i]) for i in range(len(columns))))


def run_query(conn, sql):
    cur = conn.execute(sql)
    columns = [d[0] for d in cur.description]
    return columns, cur.fetchall()


def export_clean(columns, rows):
    with open(CLEAN_OUTPUT, "w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(columns)
        for row in rows:
            writer.writerow(["" if c is None else c for c in row])


def main():
    input_path = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_INPUT
    if not os.path.isabs(input_path):
        input_path = os.path.join(HERE, input_path)

    print("311 intake and data quality")
    print("Reading: " + os.path.basename(input_path))

    try:
        rows = load_rows(input_path)
    except (OSError, ValueError) as err:
        print("\nInput rejected: " + str(err))
        sys.exit(1)

    conn = build_db(rows)
    queries = parse_queries(QUERIES_FILE)

    dup_cols, dup_rows = run_query(conn, queries["duplicate_ids"])
    print_table("Duplicate request ids (later copies dropped)", dup_cols, dup_rows)

    miss_cols, miss_rows = run_query(conn, queries["missing_fields"])
    print_table("Rows missing a required field", miss_cols, miss_rows)

    cbo_cols, cbo_rows = run_query(conn, queries["closed_before_opened"])
    print_table("Rows closed before they opened", cbo_cols, cbo_rows)

    sta_cols, sta_rows = run_query(conn, queries["status_inconsistent"])
    print_table("Rows whose status disagrees with the close date", sta_cols, sta_rows)

    clean_cols, clean_rows = run_query(conn, queries["clean_requests"])
    print_table("Clean requests (written to clean_requests.csv)", clean_cols, clean_rows)

    export_clean(clean_cols, clean_rows)

    checks = [
        ("duplicate ids flagged", len(dup_rows), EXPECTED["duplicate_id_count"]),
        ("missing-field rows", len(miss_rows), EXPECTED["missing_field_count"]),
        ("closed-before-opened rows", len(cbo_rows), EXPECTED["closed_before_count"]),
        ("status-inconsistent rows", len(sta_rows), EXPECTED["status_inconsistent_count"]),
        ("clean rows", len(clean_rows), EXPECTED["clean_count"]),
    ]

    print("\nChecks")
    ok = True
    for label, got, want in checks:
        mark = "ok" if got == want else "MISMATCH"
        if got != want:
            ok = False
        print("  [%s] %s: got %d, expected %d" % (mark, label, got, want))

    print("\n" + ("PASS" if ok else "FAIL"))
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
