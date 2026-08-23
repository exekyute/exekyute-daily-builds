"""Load the sample page views into SQLite and run the sessionization queries.

Usage:
    python run.py                                     run every query in sql/
    python run.py --test                              run the assertion suite
    python run.py --pageviews data/other.csv          load a different view log
"""

import argparse
import csv
import io
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).parent
PAGEVIEWS_CSV = HERE / "data" / "pageviews.csv"
SQL_DIR = HERE / "sql"


def fail(path, row_num, message):
    print(f"{path.name} row {row_num}: {message}", file=sys.stderr)
    sys.exit(2)


def fail_file(path, message):
    print(f"{Path(path).name}: {message}", file=sys.stderr)
    sys.exit(2)


def read_csv(path):
    # utf-8-sig strips the byte-order mark that Excel puts on its CSV exports.
    try:
        text = Path(path).read_text(encoding="utf-8-sig")
    except OSError as err:
        fail_file(path, err.strerror or "cannot be read")
    except UnicodeDecodeError:
        fail_file(path, "is not UTF-8 text")
    return io.StringIO(text, newline="")


def valid_timestamp(value):
    # Round-trip so non-zero-padded parts like 9:15:00 are rejected;
    # strptime accepts them but SQLite's strftime() returns NULL on them.
    fmt = "%Y-%m-%d %H:%M:%S"
    try:
        return datetime.strptime(value, fmt).strftime(fmt) == value
    except (ValueError, TypeError):
        return False


def load_pageviews(path):
    rows, seen = [], set()
    with read_csv(path) as f:
        reader = csv.DictReader(f)
        if reader.fieldnames != ["visitor_id", "view_ts", "page"]:
            fail(path, 1, f"expected columns visitor_id,view_ts,page, got {reader.fieldnames}")
        for row in reader:
            i = reader.line_num
            # DictReader parks any surplus fields under the None key.
            if None in row:
                fail(path, i, "has more fields than the header")
            visitor = (row["visitor_id"] or "").strip()
            if not visitor:
                fail(path, i, "visitor_id is empty")
            if not valid_timestamp(row["view_ts"]):
                fail(path, i, f"view_ts {row['view_ts']!r} is not YYYY-MM-DD HH:MM:SS")
            # The window ordering needs one view per visitor per second to be
            # deterministic, so same-second duplicates are rejected outright.
            key = (visitor, row["view_ts"])
            if key in seen:
                fail(path, i, f"second view for {visitor} at {row['view_ts']}")
            seen.add(key)
            page = (row["page"] or "").strip()
            if not page.startswith("/"):
                fail(path, i, f"page {row['page']!r} must start with /")
            rows.append((visitor, row["view_ts"], page))
    if not rows:
        fail(path, 1, "no data rows after the header")
    return rows


def build_db(pageviews_path):
    pageviews = load_pageviews(pageviews_path)
    db = sqlite3.connect(":memory:")
    db.execute("CREATE TABLE pageviews (visitor_id TEXT NOT NULL, view_ts TEXT NOT NULL, page TEXT NOT NULL)")
    db.executemany("INSERT INTO pageviews VALUES (?, ?, ?)", pageviews)
    return db


def print_table(headers, rows):
    cells = [[("" if v is None else str(v)) for v in row] for row in rows]
    widths = [max(len(h), *(len(r[i]) for r in cells)) if cells else len(h)
              for i, h in enumerate(headers)]
    print("  ".join(h.ljust(widths[i]) for i, h in enumerate(headers)))
    print("  ".join("-" * w for w in widths))
    for row in cells:
        print("  ".join(row[i].ljust(widths[i]) for i in range(len(headers))))


def run_query(db, sql_path):
    cursor = db.execute(sql_path.read_text(encoding="utf-8"))
    headers = [d[0] for d in cursor.description]
    return headers, cursor.fetchall()


def run_all(db):
    for sql_path in sorted(SQL_DIR.glob("*.sql")):
        print(f"=== {sql_path.name} ===")
        headers, rows = run_query(db, sql_path)
        print_table(headers, rows)
        print()


def run_tests(db):
    failures = 0

    def check(label, got, want):
        nonlocal failures
        if got == want:
            print(f"PASS  {label}")
        else:
            failures += 1
            print(f"FAIL  {label}\n      got:  {got!r}\n      want: {want!r}")

    check("page views loaded",
          db.execute("SELECT COUNT(*) FROM pageviews").fetchone()[0], 17)

    _, gaps = run_query(db, SQL_DIR / "01-view-gaps.sql")
    check("ben gap seconds around the 30-minute line",
          [r[3] for r in gaps if r[0] == "ben"], [None, 1799, 1801, 1800])
    check("ben session flags (29:59 keeps, 30:00 splits)",
          [r[4] for r in gaps if r[0] == "ben"], [1, 0, 1, 1])

    _, ids = run_query(db, SQL_DIR / "02-session-ids.sql")
    check("sessions per visitor",
          {v: max(r[1] for r in ids if r[0] == v) for v in ("ana", "ben", "cai", "dee", "eva")},
          {"ana": 2, "ben": 3, "cai": 1, "dee": 2, "eva": 1})

    _, sessions = run_query(db, SQL_DIR / "03-session-summary.sql")
    check("total sessions", len(sessions), 9)
    check("dee session over midnight",
          [(r[2], r[3], r[5]) for r in sessions if r[0] == "dee" and r[1] == 1],
          [("2026-08-05 23:45:00", "2026-08-06 00:10:00", 3)])
    check("ben longest session is one second under the timeout",
          [r[4] for r in sessions if r[0] == "ben" and r[1] == 1], [29.98])
    check("eva session survives the shuffled CSV rows",
          [(r[5], r[6], r[7]) for r in sessions if r[0] == "eva"],
          [(3, "/home", "/faq")])

    _, rollup = run_query(db, SQL_DIR / "04-visitor-rollup.sql")
    check("bounces per visitor",
          {r[0]: r[3] for r in rollup},
          {"ana": 0, "ben": 2, "cai": 1, "dee": 1, "eva": 0})

    _, site = run_query(db, SQL_DIR / "05-site-metrics.sql")
    check("site metrics row",
          site, [(5, 9, 17, 4, "44.4%", 1.89, 10.89)])

    print()
    if failures:
        print(f"{failures} check(s) failed")
        sys.exit(1)
    print("all checks passed")


def main():
    parser = argparse.ArgumentParser(description="Run the sessionization queries against the sample page views.")
    parser.add_argument("--test", action="store_true", help="run the assertion suite instead of the reports")
    parser.add_argument("--pageviews", type=Path, default=PAGEVIEWS_CSV, help="path to an alternate page view CSV")
    args = parser.parse_args()

    db = build_db(args.pageviews)
    if args.test:
        run_tests(db)
    else:
        run_all(db)


if __name__ == "__main__":
    main()
