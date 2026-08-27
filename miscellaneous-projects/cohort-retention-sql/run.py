"""Load the sample activity log into SQLite and run the cohort queries.

Usage:
    python run.py                                    run every query in sql/
    python run.py --test                             run the assertion suite
    python run.py --activity data/other.csv          load a different log
"""

import argparse
import csv
import io
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).parent
ACTIVITY_CSV = HERE / "data" / "activity.csv"
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


def valid_date(value):
    # Round-trip so non-zero-padded dates like 2026-7-8 are rejected;
    # strptime accepts them but SQLite's date functions return NULL on them.
    try:
        return datetime.strptime(value, "%Y-%m-%d").strftime("%Y-%m-%d") == value
    except (ValueError, TypeError):
        return False


def load_activity(path):
    rows, seen = [], set()
    with read_csv(path) as f:
        reader = csv.DictReader(f)
        if reader.fieldnames != ["user_id", "activity_date"]:
            fail(path, 1, f"expected columns user_id,activity_date, got {reader.fieldnames}")
        for row in reader:
            i = reader.line_num
            if None in row:
                fail(path, i, "has more fields than the header")
            user = (row["user_id"] or "").strip()
            if not user:
                fail(path, i, "user_id is empty")
            if not valid_date(row["activity_date"]):
                fail(path, i, f"activity_date {row['activity_date']!r} is not YYYY-MM-DD")
            key = (user, row["activity_date"])
            if key in seen:
                fail(path, i, f"second activity for {user} on {row['activity_date']}")
            seen.add(key)
            rows.append((user, row["activity_date"]))
    if not rows:
        fail(path, 1, "no data rows after the header")
    return rows


def build_db(activity_path):
    activity = load_activity(activity_path)
    db = sqlite3.connect(":memory:")
    db.execute("CREATE TABLE activity (user_id TEXT NOT NULL, activity_date TEXT NOT NULL)")
    db.executemany("INSERT INTO activity VALUES (?, ?)", activity)
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

    check("activity rows loaded",
          db.execute("SELECT COUNT(*) FROM activity").fetchone()[0], 19)

    _, weekly = run_query(db, SQL_DIR / "01-weekly-activity.sql")
    check("weekly active users",
          [(r[0], r[1]) for r in weekly],
          [("2026-07-06", 3), ("2026-07-13", 5), ("2026-07-20", 4), ("2026-07-27", 5)])

    _, cohorts = run_query(db, SQL_DIR / "02-cohorts.sql")
    check("cohort sizes and join ranges",
          cohorts,
          [("2026-07-06", 3, "2026-07-06", "2026-07-12"),
           ("2026-07-13", 3, "2026-07-13", "2026-07-19"),
           ("2026-07-20", 2, "2026-07-20", "2026-07-23")])

    _, offsets = run_query(db, SQL_DIR / "03-user-week-offsets.sql")
    check("user-week cells", len(offsets), 17)
    check("cai the Sunday joiner lands in the first cohort",
          [r[1] for r in offsets if r[0] == "cai"], ["2026-07-06"])
    check("ana skips week 2, eva's same-week pair collapses",
          ([r[2] for r in offsets if r[0] == "ana"],
           [r[2] for r in offsets if r[0] == "eva"]),
          ([0, 1, 3], [0, 2]))

    _, counts = run_query(db, SQL_DIR / "04-retention-counts.sql")
    check("observable cells", len(counts), 9)
    check("first cohort week 2 is a real zero",
          [(r[2], r[3]) for r in counts if r[0] == "2026-07-06" and r[1] == 2],
          [(0, "0.0%")])
    check("youngest cohort has no unobservable cells",
          [r[1] for r in counts if r[0] == "2026-07-20"], [0, 1])

    _, grid = run_query(db, SQL_DIR / "05-retention-grid.sql")
    check("retention grid",
          grid,
          [("2026-07-06", 3, "100.0%", "66.7%", "0.0%", "66.7%"),
           ("2026-07-13", 3, "100.0%", "66.7%", "66.7%", None),
           ("2026-07-20", 2, "100.0%", "50.0%", None, None)])

    print()
    if failures:
        print(f"{failures} check(s) failed")
        sys.exit(1)
    print("all checks passed")


def main():
    parser = argparse.ArgumentParser(description="Run the cohort retention queries against the sample activity log.")
    parser.add_argument("--test", action="store_true", help="run the assertion suite instead of the reports")
    parser.add_argument("--activity", type=Path, default=ACTIVITY_CSV, help="path to an alternate activity CSV")
    args = parser.parse_args()

    db = build_db(args.activity)
    if args.test:
        run_tests(db)
    else:
        run_all(db)


if __name__ == "__main__":
    main()
