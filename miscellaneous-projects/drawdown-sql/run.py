"""Load the daily portfolio values into SQLite and run the drawdown queries.

Usage:
    python run.py                                   run every query in sql/
    python run.py --test                            run the assertion suite
    python run.py --values data/other.csv           load a different series
"""

import argparse
import csv
import io
import re
import sqlite3
import sys
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path

HERE = Path(__file__).parent
VALUES_CSV = HERE / "data" / "portfolio.csv"
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


def parse_date(path, row_num, raw):
    # Round-trip so non-zero-padded dates are rejected; strptime accepts them
    # but SQLite's date functions return NULL on them.
    try:
        parsed = datetime.strptime(raw, "%Y-%m-%d")
        if parsed.strftime("%Y-%m-%d") != raw:
            raise ValueError
    except (ValueError, TypeError):
        fail(path, row_num, f"value_date {raw!r} is not YYYY-MM-DD")
    return parsed.date()


def load_values(path):
    rows, prev = [], None
    with read_csv(path) as f:
        reader = csv.DictReader(f)
        if reader.fieldnames != ["value_date", "value"]:
            fail(path, 1, f"expected columns value_date,value, got {reader.fieldnames}")
        for row in reader:
            i = reader.line_num
            if None in row:
                fail(path, i, "has more fields than the header")
            if any(v is None for v in row.values()):
                fail(path, i, "has fewer fields than the header")
            raw_date = row["value_date"].strip()
            day = parse_date(path, i, raw_date)
            # Underwater durations count days, so the series must be one row
            # per day with no gaps or every stretch length quietly lies.
            if prev is not None and day != prev + timedelta(days=1):
                fail(path, i, f"dates must be consecutive; expected {(prev + timedelta(days=1)).isoformat()}")
            prev = day
            raw = row["value"].strip()
            if raw.startswith("-"):
                fail(path, i, f"value {raw!r} is negative; a portfolio value below zero breaks the percent math")
            if not re.fullmatch(r"[0-9]+(\.[0-9]{1,2})?", raw):
                fail(path, i, f"value {raw!r} is not a money amount")
            cents = int(Decimal(raw) * 100)
            if cents == 0:
                fail(path, i, "value is zero; a zero peak breaks the percent math")
            if cents >= 10 ** 15:
                fail(path, i, f"value {raw!r} is beyond anything plausible for this series")
            rows.append((raw_date, cents))
    if not rows:
        fail(path, 1, "no data rows after the header")
    if len(rows) < 2:
        fail_file(path, "a drawdown needs at least two days")
    return rows


def build_db(values_path):
    values = load_values(values_path)
    db = sqlite3.connect(":memory:")
    db.execute("CREATE TABLE portfolio (value_date TEXT PRIMARY KEY, value_cents INTEGER NOT NULL)")
    db.executemany("INSERT INTO portfolio VALUES (?, ?)", values)
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

    check("days loaded",
          db.execute("SELECT COUNT(*) FROM portfolio").fetchone()[0], 40)

    _, shape = run_query(db, SQL_DIR / "01-series-shape.sql")
    check("up 27.40 overall yet underwater 25 of 40 days",
          shape,
          [(40, "2026-07-01", "2026-08-09", 10000.0, 12740.0, 27.4,
            13000.0, "2026-07-30", 15, 25)])

    _, scored = run_query(db, SQL_DIR / "02-running-peak.sql")
    check("every day scored", len(scored), 40)
    check("a dip below the peak reads underwater",
          [(r[2], r[3], r[4]) for r in scored if r[0] == "2026-07-03"],
          [(10200.0, 1.0, "underwater")])
    check("a flat day at the peak is not underwater",
          [(r[2], r[3], r[4]) for r in scored if r[0] == "2026-07-08"],
          [(11400.0, 0.0, "")])
    check("the trough of the big slide",
          [(r[2], r[3], r[4]) for r in scored if r[0] == "2026-07-15"],
          [(12000.0, 15.0, "underwater")])
    check("re-touching the old peak ends the drawdown",
          [(r[2], r[3], r[4]) for r in scored if r[0] == "2026-07-22"],
          [(12000.0, 0.0, "")])

    _, stretches = run_query(db, SQL_DIR / "03-underwater-stretches.sql")
    check("four underwater stretches, one still open",
          stretches,
          [("2026-07-03", 10200.0, "2026-07-03", 10098.0, 1.0, 1, "2026-07-04"),
           ("2026-07-11", 12000.0, "2026-07-15", 10200.0, 15.0, 11, "2026-07-22"),
           ("2026-07-25", 12500.0, "2026-07-26", 11875.0, 5.0, 3, "2026-07-28"),
           ("2026-07-31", 13000.0, "2026-08-04", 12090.0, 7.0, 10, "not yet")])

    _, worst = run_query(db, SQL_DIR / "04-max-drawdown.sql")
    check("the max drawdown row reads as a complete story",
          worst,
          [(12000.0, "2026-07-09", "2026-07-15", 10200.0, 15.0, 6, "2026-07-22", 7)])

    _, status = run_query(db, SQL_DIR / "05-current-status.sql")
    check("the statement line for the latest day",
          status,
          [("2026-08-09", 12740.0, 13000.0, "2026-07-30", "underwater", 10, 2.0)])

    print()
    if failures:
        print(f"{failures} check(s) failed")
        sys.exit(1)
    print("all checks passed")


def main():
    parser = argparse.ArgumentParser(description="Run the drawdown queries against the sample series.")
    parser.add_argument("--test", action="store_true", help="run the assertion suite instead of the reports")
    parser.add_argument("--values", type=Path, default=VALUES_CSV, help="path to an alternate values CSV")
    args = parser.parse_args()
    if args.test and args.values.resolve() != VALUES_CSV.resolve():
        parser.error("--test checks hand-computed answers for the sample series; run it without --values")

    db = build_db(args.values)
    if args.test:
        run_tests(db)
    else:
        run_all(db)


if __name__ == "__main__":
    main()
