"""Load the daily sales log into SQLite and run the pivot queries.

Usage:
    python run.py                                   run every query in sql/
    python run.py --test                            run the assertion suite
    python run.py --sales data/other.csv            load a different sales log
"""

import argparse
import csv
import io
import re
import sqlite3
import sys
import unicodedata
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

HERE = Path(__file__).parent
SALES_CSV = HERE / "data" / "sales.csv"
SQL_DIR = HERE / "sql"
COLUMNS = ["sale_date", "amount"]


def fail(path, row_num, message):
    print(f"{path.name} row {row_num}: {message}", file=sys.stderr)
    sys.exit(2)


def fail_file(path, message):
    print(f"{Path(path).name}: {message}", file=sys.stderr)
    sys.exit(2)


def read_csv(path, columns):
    # utf-8-sig strips the byte-order mark that Excel puts on its CSV exports.
    try:
        text = Path(path).read_text(encoding="utf-8-sig")
    except OSError as err:
        fail_file(path, err.strerror or "cannot be read")
    except UnicodeDecodeError:
        fail_file(path, "is not UTF-8 text")
    # strict, because the lenient parser folds text that follows a closing
    # quote back into the field and hands over a garbled row without a word.
    reader = csv.reader(io.StringIO(text, newline=""), strict=True)
    try:
        header = next(reader)
    except StopIteration:
        fail_file(path, "is empty")
    except csv.Error as err:
        fail(path, 1, f"cannot be parsed ({err})")
    if header != columns:
        fail(path, 1, f"expected columns {','.join(columns)}, got {header}")
    return reader


def records(path, reader, columns):
    # Yields each record with the line it started on. reader.line_num is where
    # a record ended, which for a stray quote can be many lines on, and a
    # blank line before a record would shift the count as well.
    start = reader.line_num + 1
    try:
        for fields in reader:
            if not fields:
                start = reader.line_num + 1
                continue
            if any(ch in f for f in fields for ch in "\r\n"):
                fail(path, start, "a field runs across more than one line; "
                                  "most likely a quote that never closes")
            bad = next((ch for f in fields for ch in f
                        if unicodedata.category(ch) == "Cc"), None)
            if bad is not None:
                fail(path, start, f"contains the control character {bad!r}")
            if len(fields) > len(columns):
                fail(path, start, "has more fields than the header")
            if len(fields) < len(columns):
                fail(path, start, "has fewer fields than the header")
            yield start, dict(zip(columns, fields))
            start = reader.line_num + 1
    except csv.Error as err:
        fail(path, start, f"cannot be parsed ({err}); most likely a quote out of place")


def load_sales(path):
    rows, seen = [], set()
    reader = read_csv(path, COLUMNS)
    for i, row in records(path, reader, COLUMNS):
        stamp = row["sale_date"].strip()
        # Shape first, since a date missing its zero padding sorts out of
        # place and makes strftime return NULL; then whether it is real.
        if not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", stamp):
            fail(path, i, f"sale_date {stamp!r} is not YYYY-MM-DD")
        try:
            datetime.strptime(stamp, "%Y-%m-%d")
        except ValueError:
            fail(path, i, f"sale_date {stamp!r} is not a real date")
        # One row per trading day: two rows for one date would both land in
        # the same grid cell and be added together without anyone noticing.
        if stamp in seen:
            fail(path, i, f"sale_date {stamp} appears twice; the log holds one row per trading day")
        seen.add(stamp)
        raw = row["amount"].strip()
        if raw.startswith("-"):
            fail(path, i, f"amount {raw!r} carries a minus sign; refunds net out before the log")
        if not re.fullmatch(r"[0-9]+(\.[0-9]{1,2})?", raw):
            fail(path, i, f"amount {raw!r} is not a money amount")
        cents = int(Decimal(raw) * 100)
        if cents >= 10 ** 12:
            fail(path, i, f"amount {raw!r} is beyond anything plausible for one day")
        rows.append((stamp, cents))
    if not rows:
        fail(path, 1, "no data rows after the header")
    return rows


def build_db(sales_path):
    sales = load_sales(sales_path)
    db = sqlite3.connect(":memory:")
    db.execute("CREATE TABLE sales (sale_date TEXT PRIMARY KEY, cents INTEGER NOT NULL)")
    db.executemany("INSERT INTO sales VALUES (?, ?)", sales)
    return db


def print_table(headers, rows):
    cells = [[("" if v is None else str(v)) for v in row] for row in rows]
    widths = [max(len(h), *(len(r[i]) for r in cells)) if cells else len(h)
              for i, h in enumerate(headers)]
    print("  ".join(h.ljust(widths[i]) for i, h in enumerate(headers)).rstrip())
    print("  ".join("-" * w for w in widths))
    for row in cells:
        print("  ".join(row[i].ljust(widths[i]) for i in range(len(headers))).rstrip())


def run_query(db, sql_path):
    try:
        cursor = db.execute(sql_path.read_text(encoding="utf-8"))
    except sqlite3.Error as err:
        fail_file(sql_path, f"did not run: {err}")
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

    check("twenty-four trading days loaded",
          db.execute("SELECT COUNT(*) FROM sales").fetchone()[0], 24)

    _, shape = run_query(db, SQL_DIR / "01-sales-shape.sql")
    check("four weeks, one day open with no sales, 11,730.00 in all",
          shape, [(24, "2026-08-03", "2026-08-29", 4, 1, "11730.00")])

    _, naive = run_query(db, SQL_DIR / "02-naive-pivot.sql")
    check("the naive sun column is really Saturday",
          [r[7] for r in naive], ["710.00", "690.00", "720.00", "700.00"])
    check("the naive mon column is really Sunday, zero-filled when closed",
          [r[1] for r in naive], ["0.00", "540.00", "0.00", "0.00"])

    _, grid = run_query(db, SQL_DIR / "03-pivot.sql")
    check("four weeks, one row each", [r[0] for r in grid],
          ["2026-08-03", "2026-08-10", "2026-08-17", "2026-08-24"])
    check("every value lands under its own day",
          grid[0], ("2026-08-03", "420.00", "380.00", "410.00", "450.00", "620.00", "710.00", ""))
    check("a closed day is blank and the day that sold nothing is 0.00",
          (grid[2][3], grid[3][1], grid[0][7], grid[1][7]),
          ("0.00", "", "", "540.00"))

    _, totals = run_query(db, SQL_DIR / "04-totals.sql")
    check("each week totalled down the right",
          [(r[0], r[8]) for r in totals if r[0] != "all weeks"],
          [("2026-08-03", "2990.00"), ("2026-08-10", "3550.00"),
           ("2026-08-17", "2580.00"), ("2026-08-24", "2610.00")])
    check("the totals row sums each weekday and lands on the whole log",
          [r for r in totals if r[0] == "all weeks"],
          [("all weeks", "1260.00", "1540.00", "1230.00", "1830.00",
            "2510.00", "2820.00", "540.00", "11730.00")])
    check("the bottom-right cell equals the log total from query 01",
          totals[-1][8], shape[0][5])

    _, avgs = run_query(db, SQL_DIR / "05-weekday-averages.sql")
    check("the weekday averages run Monday to Sunday, not alphabetically",
          [r[0] for r in avgs], ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"])
    check("the two averages agree on every weekday the cafe never closed",
          [r[0] for r in avgs if r[3] != r[4]], ["Mon", "Sun"])
    check("closures counted as zero drag down Monday and Sunday",
          [(r[0], r[1], r[2], r[3], r[4]) for r in avgs if r[0] in ("Mon", "Sun")],
          [("Mon", 3, 4, "420.00", "315.00"), ("Sun", 1, 3, "540.00", "180.00")])

    # The sample cannot show the edge-week problem on its own, so these logs
    # are built for it. A blank in the first or last week can be a day the
    # log never reached, and query 05 must not count it as a closure.
    def scratch(rows):
        s = sqlite3.connect(":memory:")
        s.execute("CREATE TABLE sales (sale_date TEXT PRIMARY KEY, cents INTEGER NOT NULL)")
        s.executemany("INSERT INTO sales VALUES (?, ?)", rows)
        return s

    month = scratch([((date(2026, 8, 1) + timedelta(days=n)).isoformat(), 50000) for n in range(31)])
    _, m = run_query(month, SQL_DIR / "05-weekday-averages.sql")
    check("a month open every day, starting and ending mid-week, shows no closures",
          sorted({(r[3], r[4]) for r in m}), [("500.00", "500.00")])

    gap = scratch([((date(2026, 8, 3) + timedelta(days=n)).isoformat(), 10000)
                   for n in range(21) if not 7 <= n <= 13])
    _, g1 = run_query(gap, SQL_DIR / "01-sales-shape.sql")
    _, g5 = run_query(gap, SQL_DIR / "05-weekday-averages.sql")
    check("a week closed throughout still counts, in the week total and as closures",
          (g1[0][3], sorted({(r[2], r[4]) for r in g5})), (3, [(3, "66.67")]))

    tie = scratch([("2026-08-06", 82291), ("2026-08-13", 82292)])
    _, t5 = run_query(tie, SQL_DIR / "05-weekday-averages.sql")
    check("an average landing on exactly half a cent rounds up",
          [(r[0], r[3]) for r in t5 if r[0] == "Thu"], [("Thu", "822.92")])

    print()
    if failures:
        print(f"{failures} check(s) failed")
        sys.exit(1)
    print("all checks passed")


def main():
    parser = argparse.ArgumentParser(description="Run the pivot queries against the sample sales log.")
    parser.add_argument("--test", action="store_true", help="run the assertion suite instead of the reports")
    parser.add_argument("--sales", type=Path, default=SALES_CSV, help="path to an alternate sales CSV")
    args = parser.parse_args()
    # Reports are printed as UTF-8, since output piped or redirected on
    # Windows otherwise falls back to a codepage that cannot print all text.
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    if not args.sales.is_file():
        parser.error(f"--sales: '{args.sales}' is not a file")
    if args.test and args.sales.resolve() != SALES_CSV.resolve():
        parser.error("--test checks hand-computed answers for the sample log; run it without --sales")

    db = build_db(args.sales)
    if args.test:
        run_tests(db)
    else:
        run_all(db)


if __name__ == "__main__":
    main()
