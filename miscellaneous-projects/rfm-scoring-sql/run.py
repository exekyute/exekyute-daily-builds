"""Load the sample order history into SQLite and run the RFM queries.

Usage:
    python run.py                                 run every query in sql/
    python run.py --test                          run the assertion suite
    python run.py --orders data/other.csv         load a different order file
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
ORDERS_CSV = HERE / "data" / "orders.csv"
SQL_DIR = HERE / "sql"
# Matches the pinned report date inside 01 and 05; an order after it would
# score a negative recency, so the loader refuses to let one in.
AS_OF = "2026-08-30"


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


def parse_cents(path, row_num, raw):
    # Money loads as integer cents so floats never touch a sum.
    try:
        amount = Decimal(raw)
    except (InvalidOperation, TypeError):
        fail(path, row_num, f"amount {raw!r} is not a number")
    if not amount.is_finite():
        fail(path, row_num, f"amount {raw!r} is not a finite number")
    cents = amount.scaleb(2)
    if cents != cents.to_integral_value():
        fail(path, row_num, f"amount {raw!r} has more than 2 decimal places")
    if amount <= 0:
        fail(path, row_num, f"amount {raw!r} must be greater than zero")
    if cents > Decimal(10) ** 15:
        fail(path, row_num, f"amount {raw!r} is beyond any plausible order")
    return int(cents)


def load_orders(path):
    rows, seen = [], set()
    with read_csv(path) as f:
        reader = csv.DictReader(f)
        if reader.fieldnames != ["order_id", "customer_id", "order_date", "amount"]:
            fail(path, 1, f"expected columns order_id,customer_id,order_date,amount, got {reader.fieldnames}")
        for row in reader:
            i = reader.line_num
            if None in row:
                fail(path, i, "has more fields than the header")
            try:
                order_id = int(row["order_id"])
            except (ValueError, TypeError):
                fail(path, i, f"order_id {row['order_id']!r} is not an integer")
            if not 0 < order_id < 2 ** 63:
                fail(path, i, f"order_id {order_id} is out of range")
            if order_id in seen:
                fail(path, i, f"duplicate order_id {order_id}")
            seen.add(order_id)
            customer = (row["customer_id"] or "").strip()
            if not customer:
                fail(path, i, "customer_id is empty")
            if not valid_date(row["order_date"]):
                fail(path, i, f"order_date {row['order_date']!r} is not YYYY-MM-DD")
            if row["order_date"] > AS_OF:
                fail(path, i, f"order_date {row['order_date']} is after the pinned report date {AS_OF}")
            cents = parse_cents(path, i, row["amount"])
            rows.append((order_id, customer, row["order_date"], cents))
    if not rows:
        fail(path, 1, "no data rows after the header")
    if sum(r[3] for r in rows) > 10 ** 15:
        fail_file(path, "totals are beyond anything plausible")
    customers = {r[1] for r in rows}
    if len(customers) < 5:
        fail_file(path, f"quintile scoring needs at least 5 customers, found {len(customers)}")
    return rows


def build_db(orders_path):
    orders = load_orders(orders_path)
    db = sqlite3.connect(":memory:")
    db.execute("CREATE TABLE orders (order_id INTEGER PRIMARY KEY, customer_id TEXT NOT NULL, order_date TEXT NOT NULL, amount_cents INTEGER NOT NULL)")
    db.executemany("INSERT INTO orders VALUES (?, ?, ?, ?)", orders)
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

    check("orders loaded",
          db.execute("SELECT COUNT(*) FROM orders").fetchone()[0], 38)

    _, summary = run_query(db, SQL_DIR / "01-customer-summary.sql")
    check("customers", len(summary), 10)
    check("ana summary",
          [(r[1], r[3], r[4]) for r in summary if r[0] == "ana"],
          [(8, 2, "640.00")])
    check("cara has been gone 120 days",
          [r[3] for r in summary if r[0] == "cara"], [120])

    _, scores = run_query(db, SQL_DIR / "02-rfm-scores.sql")
    check("rfm codes",
          {r[0]: r[7] for r in scores},
          {"ana": "555", "kim": "554", "ivy": "444", "jon": "443",
           "hana": "335", "gus": "332", "eli": "223", "fay": "222",
           "dev": "111", "cara": "111"})

    _, mech = run_query(db, SQL_DIR / "03-ntile-mechanics.sql")
    check("dev and eli tie on count but split on score",
          [(r[0], r[1], r[3]) for r in mech if r[0] in ("dev", "eli")],
          [("dev", 2, 1), ("eli", 2, 2)])
    check("three tie pairs are marked",
          sum(1 for r in mech if r[4] == "tied with previous"), 3)

    _, segments = run_query(db, SQL_DIR / "04-segments.sql")
    check("segment per customer",
          {r[0]: r[3] for r in segments},
          {"ana": "champions", "kim": "champions", "ivy": "champions",
           "jon": "loyal", "hana": "big spender at risk", "gus": "regular",
           "fay": "at risk", "eli": "at risk", "dev": "lost", "cara": "lost"})

    _, rollup = run_query(db, SQL_DIR / "05-segment-rollup.sql")
    check("segment rollup",
          rollup,
          [("champions", 3, "1495.00", "49.3%", 9.0),
           ("big spender at risk", 1, "500.00", "16.5%", 31.0),
           ("at risk", 2, "410.00", "13.5%", 72.0),
           ("loyal", 1, "280.00", "9.2%", 12.0),
           ("regular", 1, "210.00", "6.9%", 46.0),
           ("lost", 2, "135.00", "4.5%", 111.0)])

    print()
    if failures:
        print(f"{failures} check(s) failed")
        sys.exit(1)
    print("all checks passed")


def main():
    parser = argparse.ArgumentParser(description="Run the RFM queries against the sample order history.")
    parser.add_argument("--test", action="store_true", help="run the assertion suite instead of the reports")
    parser.add_argument("--orders", type=Path, default=ORDERS_CSV, help="path to an alternate orders CSV")
    args = parser.parse_args()

    db = build_db(args.orders)
    if args.test:
        run_tests(db)
    else:
        run_all(db)


if __name__ == "__main__":
    main()
