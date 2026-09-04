"""Load the ledger into SQLite and run the balance drift queries.

Usage:
    python run.py                                   run every query in sql/
    python run.py --test                            run the assertion suite
    python run.py --ledger data/other.csv           load a different ledger
"""

import argparse
import csv
import io
import re
import sqlite3
import sys
from datetime import datetime
from decimal import Decimal
from pathlib import Path

HERE = Path(__file__).parent
LEDGER_CSV = HERE / "data" / "ledger.csv"
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
        fail(path, row_num, f"txn_date {raw!r} is not YYYY-MM-DD")
    return parsed.date()


def parse_money(path, row_num, field, raw):
    if not re.fullmatch(r"-?[0-9]+(\.[0-9]{1,2})?", raw):
        fail(path, row_num, f"{field} {raw!r} is not a money amount")
    cents = int(Decimal(raw) * 100)
    if abs(cents) >= 10 ** 15:
        fail(path, row_num, f"{field} {raw!r} is beyond anything plausible for this ledger")
    return cents


def load_ledger(path):
    # The loader checks form only: ids gapless, dates ordered, money shaped.
    # The one thing it deliberately does NOT check is the balance arithmetic
    # itself; broken arithmetic is data here, and finding it is the queries'
    # whole job.
    rows, prev_id, prev_date, running = [], None, None, 0
    with read_csv(path) as f:
        reader = csv.DictReader(f)
        if reader.fieldnames != ["txn_id", "txn_date", "description", "amount", "recorded_balance"]:
            fail(path, 1, f"expected columns txn_id,txn_date,description,amount,recorded_balance, got {reader.fieldnames}")
        for row in reader:
            i = reader.line_num
            if None in row:
                fail(path, i, "has more fields than the header")
            if any(v is None for v in row.values()):
                fail(path, i, "has fewer fields than the header")
            raw_id = row["txn_id"].strip()
            if not re.fullmatch(r"[0-9]+", raw_id):
                fail(path, i, f"txn_id {row['txn_id']!r} is not a whole number")
            txn_id = int(raw_id)
            if txn_id >= 10 ** 9:
                fail(path, i, f"txn_id {txn_id} is beyond anything plausible for this ledger")
            # The running balance only means anything in exact sequence: a
            # missing row is indistinguishable from drift, so the loader
            # refuses to guess across a gap, and the sequence must start at
            # 1 or the file has been truncated above its own opening line.
            if prev_id is None and txn_id != 1:
                fail(path, i, f"the ledger must start at txn_id 1, found {txn_id}; earlier rows are missing")
            if prev_id is not None and txn_id != prev_id + 1:
                fail(path, i, f"txn_id {txn_id} is not consecutive; expected {prev_id + 1}")
            prev_id = txn_id
            raw_date = row["txn_date"].strip()
            day = parse_date(path, i, raw_date)
            if prev_date is not None and day < prev_date:
                fail(path, i, f"txn_date {raw_date} is earlier than the row above")
            prev_date = day
            description = row["description"].strip()
            if not description:
                fail(path, i, "description is empty")
            amount = parse_money(path, i, "amount", row["amount"].strip())
            recorded = parse_money(path, i, "recorded_balance", row["recorded_balance"].strip())
            # Each value is capped, but the rebuild sums all of them, so the
            # running total gets the same cap or a long enough ledger could
            # overflow SQLite's integers mid-query instead of failing here.
            running += amount
            if abs(running) >= 10 ** 15:
                fail(path, i, "the running balance is beyond anything plausible for this ledger")
            rows.append((txn_id, raw_date, description, amount, recorded))
    if not rows:
        fail(path, 1, "no data rows after the header")
    if len(rows) < 2:
        fail_file(path, "a ledger needs an opening line and at least one transaction")
    return rows


def build_db(ledger_path):
    ledger = load_ledger(ledger_path)
    db = sqlite3.connect(":memory:")
    db.execute("""CREATE TABLE ledger (
        txn_id INTEGER PRIMARY KEY,
        txn_date TEXT NOT NULL,
        description TEXT NOT NULL,
        amount_cents INTEGER NOT NULL,
        recorded_cents INTEGER NOT NULL)""")
    db.executemany("INSERT INTO ledger VALUES (?, ?, ?, ?, ?)", ledger)
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

    check("ledger rows loaded",
          db.execute("SELECT COUNT(*) FROM ledger").fetchone()[0], 31)

    _, shape = run_query(db, SQL_DIR / "01-ledger-shape.sql")
    check("the shape line ends on a 30.00 closing gap",
          shape,
          [(31, "2026-07-31", "2026-09-04", 1000.0, 3150.0, 3120.0, -30.0)])

    _, rebuild = run_query(db, SQL_DIR / "02-rebuild-balance.sql")
    check("every row rebuilt", len(rebuild), 31)
    check("the ledger ties until the first break",
          [r[6] for r in rebuild if r[0] == 12], [0.0])
    check("the first break carries plus one hundred to the next break",
          [r[6] for r in rebuild if r[0] in (13, 23)], [100.0, 100.0])
    check("the second break nets the drift to minus thirty",
          [r[6] for r in rebuild if r[0] in (24, 31)], [-30.0, -30.0])
    check("payroll mid-regime shows the carried drift, not a new error",
          [(r[4], r[5]) for r in rebuild if r[0] == 18], [(1403.0, 1503.0)])

    _, breaks = run_query(db, SQL_DIR / "03-break-points.sql")
    check("exactly two rows break their own arithmetic",
          breaks,
          [(13, "2026-08-16", "Invoice 1045 payment", 250.0, 2335.5, 2435.5, 100.0),
           (24, "2026-08-31", "Vendor payment", -75.0, 2363.0, 2233.0, -130.0)])

    _, regimes = run_query(db, SQL_DIR / "04-drift-regimes.sql")
    check("three drift regimes, each opened by nothing or a break",
          regimes,
          [(1, 1, 12, "2026-07-31", "2026-08-15", 12, 0.0),
           (2, 13, 23, "2026-08-16", "2026-08-30", 11, 100.0),
           (3, 24, 31, "2026-08-31", "2026-09-04", 8, -30.0)])

    _, note = run_query(db, SQL_DIR / "05-audit-note.sql")
    check("the audit note dates the first break",
          [(r[0], r[1], r[2], r[3], r[4]) for r in note],
          [("ledger breaks its own arithmetic", 13, "2026-08-16", "Invoice 1045 payment", 100.0)])
    check("two breaks, 230.00 of error, 19 rows off, 30.00 showing",
          [(r[5], r[6], r[7], r[8]) for r in note],
          [(2, 230.0, 19, -30.0)])

    print()
    if failures:
        print(f"{failures} check(s) failed")
        sys.exit(1)
    print("all checks passed")


def main():
    parser = argparse.ArgumentParser(description="Run the drift queries against the sample ledger.")
    parser.add_argument("--test", action="store_true", help="run the assertion suite instead of the reports")
    parser.add_argument("--ledger", type=Path, default=LEDGER_CSV, help="path to an alternate ledger CSV")
    args = parser.parse_args()
    if args.test and args.ledger.resolve() != LEDGER_CSV.resolve():
        parser.error("--test checks hand-computed answers for the sample ledger; run it without --ledger")

    db = build_db(args.ledger)
    if args.test:
        run_tests(db)
    else:
        run_all(db)


if __name__ == "__main__":
    main()
