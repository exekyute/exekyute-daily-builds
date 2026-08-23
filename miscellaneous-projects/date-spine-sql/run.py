"""Load the sample sales data into SQLite and run the date spine queries.

Usage:
    python run.py                              run every query in sql/
    python run.py --test                       run the assertion suite
    python run.py --sales data/other.csv       load a different sales file
"""

import argparse
import csv
import io
import math
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).parent
SALES_CSV = HERE / "data" / "sales.csv"
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
    # Round-trip so non-zero-padded dates like 2026-7-3 are rejected;
    # strptime accepts them but SQLite's DATE() returns NULL on them.
    try:
        return datetime.strptime(value, "%Y-%m-%d").strftime("%Y-%m-%d") == value
    except (ValueError, TypeError):
        return False


def load_sales(path):
    rows = []
    with read_csv(path) as f:
        reader = csv.DictReader(f)
        if reader.fieldnames != ["sale_date", "store", "amount"]:
            fail(path, 1, f"expected columns sale_date,store,amount, got {reader.fieldnames}")
        for row in reader:
            i = reader.line_num
            if not valid_date(row["sale_date"]):
                fail(path, i, f"sale_date {row['sale_date']!r} is not YYYY-MM-DD")
            if not (row["store"] or "").strip():
                fail(path, i, "store is empty")
            try:
                amount = float(row["amount"])
            except (ValueError, TypeError):
                fail(path, i, f"amount {row['amount']!r} is not a number")
            if not math.isfinite(amount):
                fail(path, i, f"amount {row['amount']!r} is not a finite number")
            if amount <= 0:
                fail(path, i, f"amount {amount} must be greater than zero")
            rows.append((row["sale_date"], row["store"].strip(), amount))
    if not rows:
        fail(path, 1, "no data rows after the header")
    return rows


def build_db(sales_path):
    sales = load_sales(sales_path)
    db = sqlite3.connect(":memory:")
    db.execute("CREATE TABLE sales (sale_date TEXT NOT NULL, store TEXT NOT NULL, amount REAL NOT NULL)")
    db.executemany("INSERT INTO sales VALUES (?, ?, ?)", sales)
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

    check("sales rows loaded",
          db.execute("SELECT COUNT(*) FROM sales").fetchone()[0], 55)

    _, daily = run_query(db, SQL_DIR / "01-daily-totals.sql")
    check("store-days with sales", len(daily), 50)

    _, spine = run_query(db, SQL_DIR / "02-date-spine.sql")
    check("calendar days generated", len(spine), 31)
    check("calendar bounds",
          (spine[0][0], spine[-1][0]), ("2026-07-01", "2026-07-31"))

    _, grid = run_query(db, SQL_DIR / "03-gap-filled-daily.sql")
    check("store-days on the grid", len(grid), 62)
    check("zero-sales store-days", sum(1 for r in grid if r[2] == 0), 12)
    check("Harbourfront closed days",
          [r[1] for r in grid if r[0] == "Harbourfront" and r[2] == 0],
          ["2026-07-04", "2026-07-05", "2026-07-19"])

    _, running = run_query(db, SQL_DIR / "04-running-totals.sql")
    check("month-end running totals",
          {r[0]: r[3] for r in running if r[1] == "2026-07-31"},
          {"Harbourfront": 6535.0, "Westside": 3195.0})
    check("Westside running total before opening",
          [r[3] for r in running if r[0] == "Westside" and r[1] == "2026-07-07"], [0])

    _, rolling = run_query(db, SQL_DIR / "05-rolling-average.sql")
    check("Harbourfront 7-day averages on 2026-07-21",
          [(r[3], r[4]) for r in rolling if r[0] == "Harbourfront" and r[1] == "2026-07-21"],
          [(199.29, 227.86)])

    print()
    if failures:
        print(f"{failures} check(s) failed")
        sys.exit(1)
    print("all checks passed")


def main():
    parser = argparse.ArgumentParser(description="Run the date spine queries against the sample sales data.")
    parser.add_argument("--test", action="store_true", help="run the assertion suite instead of the reports")
    parser.add_argument("--sales", type=Path, default=SALES_CSV, help="path to an alternate sales CSV")
    args = parser.parse_args()

    db = build_db(args.sales)
    if args.test:
        run_tests(db)
    else:
        run_all(db)


if __name__ == "__main__":
    main()
