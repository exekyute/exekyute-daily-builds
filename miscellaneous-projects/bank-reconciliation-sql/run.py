"""Load the sample ledger and bank statement into SQLite and reconcile them.

Usage:
    python run.py                                 run every query in sql/
    python run.py --test                          run the assertion suite
    python run.py --ledger data/other.csv         load a different ledger file
    python run.py --bank data/other.csv           load a different statement file
"""

import argparse
import csv
import io
import sqlite3
import sys
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

HERE = Path(__file__).parent
LEDGER_CSV = HERE / "data" / "ledger.csv"
BANK_CSV = HERE / "data" / "bank.csv"
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
    # Round-trip so non-zero-padded dates like 2026-7-4 are rejected;
    # strptime accepts them but SQLite's julianday() returns NULL on them.
    try:
        return datetime.strptime(value, "%Y-%m-%d").strftime("%Y-%m-%d") == value
    except (ValueError, TypeError):
        return False


def parse_cents(path, row_num, raw):
    # Money loads as integer cents so floats never touch a sum.
    try:
        amount = Decimal(raw)
    except (InvalidOperation, TypeError):
        fail(path, row_num, f"amount {raw!r} is not a number")
    if not amount.is_finite():
        fail(path, row_num, f"amount {raw!r} is not a finite number")
    cents = amount.scaleb(2)
    # Compare by value, not by written exponent, so 0.500 loads as 50 cents.
    if cents != cents.to_integral_value():
        fail(path, row_num, f"amount {raw!r} has more than 2 decimal places")
    if amount == 0:
        fail(path, row_num, "amount is zero")
    if abs(cents) > Decimal(10) ** 15:
        fail(path, row_num, f"amount {raw!r} is beyond any plausible balance")
    return int(cents)


def load_book(path, id_column, date_column):
    rows, seen = [], set()
    with read_csv(path) as f:
        reader = csv.DictReader(f)
        expected = [id_column, date_column, "description", "amount"]
        if reader.fieldnames != expected:
            fail(path, 1, f"expected columns {','.join(expected)}, got {reader.fieldnames}")
        for row in reader:
            i = reader.line_num
            if None in row:
                fail(path, i, "has more fields than the header")
            try:
                row_id = int(row[id_column])
            except (ValueError, TypeError):
                fail(path, i, f"{id_column} {row[id_column]!r} is not an integer")
            if not 0 < row_id < 2 ** 63:
                fail(path, i, f"{id_column} {row_id} is out of range")
            if row_id in seen:
                fail(path, i, f"duplicate {id_column} {row_id}")
            seen.add(row_id)
            if not valid_date(row[date_column]):
                fail(path, i, f"{date_column} {row[date_column]!r} is not YYYY-MM-DD")
            if not (row["description"] or "").strip():
                fail(path, i, "description is empty")
            cents = parse_cents(path, i, row["amount"])
            rows.append((row_id, row[date_column], row["description"].strip(), cents))
    if not rows:
        fail(path, 1, "no data rows after the header")
    return rows


def build_db(ledger_path, bank_path):
    ledger = load_book(ledger_path, "entry_id", "entry_date")
    bank = load_book(bank_path, "txn_id", "txn_date")
    db = sqlite3.connect(":memory:")
    db.execute("CREATE TABLE ledger (entry_id INTEGER PRIMARY KEY, entry_date TEXT NOT NULL, description TEXT NOT NULL, cents INTEGER NOT NULL)")
    db.execute("CREATE TABLE bank (txn_id INTEGER PRIMARY KEY, txn_date TEXT NOT NULL, description TEXT NOT NULL, cents INTEGER NOT NULL)")
    db.executemany("INSERT INTO ledger VALUES (?, ?, ?, ?)", ledger)
    db.executemany("INSERT INTO bank VALUES (?, ?, ?, ?)", bank)
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

    check("rows loaded (ledger, bank)",
          (db.execute("SELECT COUNT(*) FROM ledger").fetchone()[0],
           db.execute("SELECT COUNT(*) FROM bank").fetchone()[0]), (12, 13))

    _, sides = run_query(db, SQL_DIR / "01-side-by-side.sql")
    check("book totals", [(r[0], r[2]) for r in sides],
          [("bank", "1428.17"), ("ledger", "2040.30")])

    _, exact = run_query(db, SQL_DIR / "02-exact-matches.sql")
    check("exact matches", len(exact), 5)
    check("duplicate 85.00 pair matches one-to-one",
          sorted((r[0], r[1]) for r in exact if r[3] == "-85.00"),
          [(3, 503), (4, 504)])

    _, tol = run_query(db, SQL_DIR / "03-tolerance-matches.sql")
    check("tolerance matches, days apart",
          sorted(r[4] for r in tol), [1, 3, 3])
    check("tolerance amounts",
          sorted(r[5] for r in tol), ["-450.00", "-600.00", "1105.90"])
    check("the 5-day 200.00 pair stays unmatched",
          [r for r in tol if r[5] == "-200.00"], [])

    _, unmatched = run_query(db, SQL_DIR / "04-unmatched.sql")
    check("unmatched rows per side",
          (sum(1 for r in unmatched if r[0] == "ledger"),
           sum(1 for r in unmatched if r[0] == "bank")), (4, 5))
    check("transposition pair lands on both sides",
          sorted((r[0], r[1]) for r in unmatched if r[4] in ("-120.00", "-102.00")),
          [("bank", 512), ("ledger", 11)])

    _, report = run_query(db, SQL_DIR / "05-reconciliation-report.sql")
    check("reconciliation report row",
          report,
          [("2040.30", "1428.17", "612.13", 5, 3, "244.60", "-367.53", "612.13", "0.00")])

    print()
    if failures:
        print(f"{failures} check(s) failed")
        sys.exit(1)
    print("all checks passed")


def main():
    parser = argparse.ArgumentParser(description="Reconcile the sample ledger against the sample bank statement.")
    parser.add_argument("--test", action="store_true", help="run the assertion suite instead of the reports")
    parser.add_argument("--ledger", type=Path, default=LEDGER_CSV, help="path to an alternate ledger CSV")
    parser.add_argument("--bank", type=Path, default=BANK_CSV, help="path to an alternate bank statement CSV")
    args = parser.parse_args()

    db = build_db(args.ledger, args.bank)
    if args.test:
        run_tests(db)
    else:
        run_all(db)


if __name__ == "__main__":
    main()
