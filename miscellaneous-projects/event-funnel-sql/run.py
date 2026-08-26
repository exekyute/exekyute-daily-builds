"""Load the sample event log into SQLite and run the funnel queries.

Usage:
    python run.py                                 run every query in sql/
    python run.py --test                          run the assertion suite
    python run.py --events data/other.csv         load a different event log
"""

import argparse
import csv
import io
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).parent
EVENTS_CSV = HERE / "data" / "events.csv"
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
    # Round-trip so non-zero-padded parts like 9:30 are rejected;
    # strptime accepts them but SQLite's strftime() returns NULL on them.
    fmt = "%Y-%m-%d %H:%M"
    try:
        return datetime.strptime(value, fmt).strftime(fmt) == value
    except (ValueError, TypeError):
        return False


def load_events(path):
    rows = []
    with read_csv(path) as f:
        reader = csv.DictReader(f)
        if reader.fieldnames != ["user_id", "event_ts", "event_name"]:
            fail(path, 1, f"expected columns user_id,event_ts,event_name, got {reader.fieldnames}")
        for row in reader:
            i = reader.line_num
            if None in row:
                fail(path, i, "has more fields than the header")
            user = (row["user_id"] or "").strip()
            if not user:
                fail(path, i, "user_id is empty")
            if not valid_timestamp(row["event_ts"]):
                fail(path, i, f"event_ts {row['event_ts']!r} is not YYYY-MM-DD HH:MM")
            name = (row["event_name"] or "").strip()
            if not name:
                fail(path, i, "event_name is empty")
            rows.append((user, row["event_ts"], name))
    if not rows:
        fail(path, 1, "no data rows after the header")
    return rows


def build_db(events_path):
    events = load_events(events_path)
    db = sqlite3.connect(":memory:")
    db.execute("CREATE TABLE events (user_id TEXT NOT NULL, event_ts TEXT NOT NULL, event_name TEXT NOT NULL)")
    db.executemany("INSERT INTO events VALUES (?, ?, ?)", events)
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

    check("events loaded",
          db.execute("SELECT COUNT(*) FROM events").fetchone()[0], 24)

    _, counts = run_query(db, SQL_DIR / "01-event-counts.sql")
    check("raw purchase and project counts",
          {r[0]: (r[1], r[2]) for r in counts if r[0] in ("purchased", "project_created", "help_viewed")},
          {"purchased": (5, 5), "project_created": (7, 6), "help_viewed": (1, 1)})

    _, funnel = run_query(db, SQL_DIR / "02-ordered-funnel.sql")
    check("funnel entrants", len(funnel), 7)
    check("ana same-minute signup and project both count",
          [(r[1], r[2]) for r in funnel if r[0] == "ana"],
          [("2026-08-01 09:00", "2026-08-01 09:00")])
    check("dee stops at project despite her purchase",
          [(r[2], r[4]) for r in funnel if r[0] == "dee"],
          [("2026-08-04 10:00", None)])

    _, versus = run_query(db, SQL_DIR / "03-naive-vs-ordered.sql")
    check("naive vs ordered disagreements",
          [(r[0], r[1], r[2], r[3]) for r in versus if r[3] != ""],
          [("dee", "purchased", "project_created", "events fired out of order"),
           ("gus", "purchased", "nothing", "never signed up")])

    _, gaps = run_query(db, SQL_DIR / "04-stage-gaps.sql")
    check("median hours per transition",
          [(r[0], r[1], r[2]) for r in gaps],
          [("signup to project_created", 6, 13.25),
           ("project_created to teammate_invited", 4, 34.5),
           ("teammate_invited to purchased", 3, 76.0)])

    _, summary = run_query(db, SQL_DIR / "05-funnel-summary.sql")
    check("funnel summary",
          summary,
          [("signup", 7, "100.0%", "100.0%"),
           ("project_created", 6, "85.7%", "85.7%"),
           ("teammate_invited", 4, "57.1%", "66.7%"),
           ("purchased", 3, "42.9%", "75.0%")])

    print()
    if failures:
        print(f"{failures} check(s) failed")
        sys.exit(1)
    print("all checks passed")


def main():
    parser = argparse.ArgumentParser(description="Run the funnel queries against the sample event log.")
    parser.add_argument("--test", action="store_true", help="run the assertion suite instead of the reports")
    parser.add_argument("--events", type=Path, default=EVENTS_CSV, help="path to an alternate events CSV")
    args = parser.parse_args()

    db = build_db(args.events)
    if args.test:
        run_tests(db)
    else:
        run_all(db)


if __name__ == "__main__":
    main()
