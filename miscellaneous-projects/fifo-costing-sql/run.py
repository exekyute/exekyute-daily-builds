"""Load the sample purchases and sales into SQLite and run the FIFO queries.

Usage:
    python run.py                                    run every query in sql/
    python run.py --test                             run the assertion suite
    python run.py --purchases data/other.csv         load a different purchase file
    python run.py --sales data/other.csv             load a different sales file
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
PURCHASES_CSV = HERE / "data" / "purchases.csv"
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
    # Round-trip so non-zero-padded dates are rejected; strptime accepts them
    # but SQLite's date functions return NULL on them.
    try:
        return datetime.strptime(value, "%Y-%m-%d").strftime("%Y-%m-%d") == value
    except (ValueError, TypeError):
        return False


def parse_cents(path, row_num, label, raw):
    # Money loads as integer cents so floats never touch a sum.
    try:
        amount = Decimal(raw)
    except (InvalidOperation, TypeError):
        fail(path, row_num, f"{label} {raw!r} is not a number")
    if not amount.is_finite():
        fail(path, row_num, f"{label} {raw!r} is not a finite number")
    cents = amount.scaleb(2)
    if cents != cents.to_integral_value():
        fail(path, row_num, f"{label} {raw!r} has more than 2 decimal places")
    if amount <= 0:
        fail(path, row_num, f"{label} {raw!r} must be greater than zero")
    if cents > Decimal(10) ** 15:
        fail(path, row_num, f"{label} {raw!r} is beyond any plausible price")
    return int(cents)


def parse_int(path, row_num, label, raw, minimum=1):
    try:
        value = int(raw)
    except (ValueError, TypeError):
        fail(path, row_num, f"{label} {raw!r} is not an integer")
    if not minimum <= value < 2 ** 63:
        fail(path, row_num, f"{label} {value} is out of range")
    return value


def load_book(path, id_column, date_column, money_column):
    rows, seen = [], set()
    expected = [id_column, "product", date_column, "qty", money_column]
    with read_csv(path) as f:
        reader = csv.DictReader(f)
        if reader.fieldnames != expected:
            fail(path, 1, f"expected columns {','.join(expected)}, got {reader.fieldnames}")
        for row in reader:
            i = reader.line_num
            if None in row:
                fail(path, i, "has more fields than the header")
            row_id = parse_int(path, i, id_column, row[id_column])
            if row_id in seen:
                fail(path, i, f"duplicate {id_column} {row_id}")
            seen.add(row_id)
            product = (row["product"] or "").strip()
            if not product:
                fail(path, i, "product is empty")
            if not valid_date(row[date_column]):
                fail(path, i, f"{date_column} {row[date_column]!r} is not YYYY-MM-DD")
            qty = parse_int(path, i, "qty", row["qty"])
            cents = parse_cents(path, i, money_column, row[money_column])
            # Cap the line value so integer-cent arithmetic can never leave
            # int64 territory once SQL starts summing and multiplying.
            if qty * cents > 10 ** 15:
                fail(path, i, "line value is beyond anything plausible")
            rows.append((row_id, product, row[date_column], qty, cents))
    if not rows:
        fail(path, 1, "no data rows after the header")
    if sum(r[3] for r in rows) > 10 ** 15 or sum(r[3] * r[4] for r in rows) > 10 ** 15:
        fail_file(path, "totals are beyond anything plausible")
    return rows


def build_db(purchases_path, sales_path):
    purchases = load_book(purchases_path, "purchase_id", "purchase_date", "unit_cost")
    sales = load_book(sales_path, "sale_id", "sale_date", "unit_price")
    db = sqlite3.connect(":memory:")
    db.execute("CREATE TABLE purchases (purchase_id INTEGER PRIMARY KEY, product TEXT NOT NULL, purchase_date TEXT NOT NULL, qty INTEGER NOT NULL, unit_cost_cents INTEGER NOT NULL)")
    db.execute("CREATE TABLE sales (sale_id INTEGER PRIMARY KEY, product TEXT NOT NULL, sale_date TEXT NOT NULL, qty INTEGER NOT NULL, unit_price_cents INTEGER NOT NULL)")
    db.executemany("INSERT INTO purchases VALUES (?, ?, ?, ?, ?)", purchases)
    db.executemany("INSERT INTO sales VALUES (?, ?, ?, ?, ?)", sales)
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

    counts = tuple(db.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
                   for t in ("purchases", "sales"))
    check("rows loaded (purchases, sales)", counts, (5, 5))

    _, layers = run_query(db, SQL_DIR / "01-layers.sql")
    check("arabica layer ranges",
          [(r[5], r[6]) for r in layers if r[0] == "arabica-beans"],
          [(0, 100), (100, 180), (180, 300)])

    _, ranges = run_query(db, SQL_DIR / "02-sale-ranges.sql")
    check("the 70-unit sale spans units 60 to 130",
          [(r[5], r[6]) for r in ranges if r[1] == 2], [(60, 130)])

    _, alloc = run_query(db, SQL_DIR / "03-fifo-allocation.sql")
    check("allocation rows", len(alloc), 8)
    check("sale 2 splits across two layers",
          [(r[4], r[5], r[6]) for r in alloc if r[1] == 2],
          [(40, "4.00", "160.00"), (30, "4.50", "135.00")])
    check("sale 5 splits across the cup layers",
          [(r[4], r[5], r[6]) for r in alloc if r[1] == 5],
          [(300, "0.10", "30.00"), (150, "0.12", "18.00")])

    _, margins = run_query(db, SQL_DIR / "04-sale-margins.sql")
    check("per-sale margins",
          [(r[0], r[4], r[5], r[6], r[7]) for r in margins],
          [(1, "480.00", "240.00", "240.00", "50.0%"),
           (2, "560.00", "295.00", "265.00", "47.3%"),
           (3, "742.50", "393.00", "349.50", "47.1%"),
           (4, "50.00", "20.00", "30.00", "60.0%"),
           (5, "112.50", "48.00", "64.50", "57.3%")])

    _, proof = run_query(db, SQL_DIR / "05-inventory-proof.sql")
    check("all proofs ok", [r[3] for r in proof], ["ok", "ok", "ok", "ok"])
    check("arabica conservation identity",
          [r[2] for r in proof if r[0].startswith("purchases") and r[1] == "arabica-beans"],
          ["1264.00 = 928.00 + 336.00"])
    check("cups conservation identity",
          [r[2] for r in proof if r[0].startswith("purchases") and r[1] == "paper-cups"],
          ["98.00 = 68.00 + 30.00"])

    print()
    if failures:
        print(f"{failures} check(s) failed")
        sys.exit(1)
    print("all checks passed")


def main():
    parser = argparse.ArgumentParser(description="Run the FIFO costing queries against the sample data.")
    parser.add_argument("--test", action="store_true", help="run the assertion suite instead of the reports")
    parser.add_argument("--purchases", type=Path, default=PURCHASES_CSV, help="path to an alternate purchases CSV")
    parser.add_argument("--sales", type=Path, default=SALES_CSV, help="path to an alternate sales CSV")
    args = parser.parse_args()

    db = build_db(args.purchases, args.sales)
    if args.test:
        run_tests(db)
    else:
        run_all(db)


if __name__ == "__main__":
    main()
