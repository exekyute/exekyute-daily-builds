"""Load the sample pricing data into SQLite and run the price history queries.

Usage:
    python run.py                                    run every query in sql/
    python run.py --test                             run the assertion suite
    python run.py --snapshots data/other.csv         load a different snapshot file
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
DATA = HERE / "data"
SNAPSHOTS_CSV = DATA / "price_snapshots.csv"
ORDERS_CSV = DATA / "orders.csv"
PRICE_LIST_CSV = DATA / "price_list.csv"
SQL_DIR = HERE / "sql"


def fail(path, row_num, message):
    print(f"{path.name} row {row_num}: {message}", file=sys.stderr)
    sys.exit(2)


def fail_file(path, message):
    print(f"{path.name}: {message}", file=sys.stderr)
    sys.exit(2)


def valid_date(value):
    # Round-trip so non-zero-padded dates like 2026-7-3 are rejected;
    # strptime accepts them but SQLite's DATE() returns NULL on them.
    try:
        return datetime.strptime(value, "%Y-%m-%d").strftime("%Y-%m-%d") == value
    except (ValueError, TypeError):
        return False


def parse_money(path, row_num, label, raw):
    try:
        value = float(raw)
    except (ValueError, TypeError):
        fail(path, row_num, f"{label} {raw!r} is not a number")
    if not math.isfinite(value) or value <= 0:
        fail(path, row_num, f"{label} {raw!r} must be a positive number")
    return value


def open_csv(path, expected_columns):
    # utf-8-sig strips the byte-order mark that Excel puts on its CSV exports.
    path = Path(path)
    try:
        text = path.read_text(encoding="utf-8-sig")
    except OSError as err:
        fail_file(path, err.strerror or "cannot be read")
    except UnicodeDecodeError:
        fail_file(path, "is not UTF-8 text")
    f = io.StringIO(text, newline="")
    reader = csv.DictReader(f)
    if reader.fieldnames != expected_columns:
        fail(path, 1, f"expected columns {','.join(expected_columns)}, got {reader.fieldnames}")
    return f, reader


def load_snapshots(path):
    rows, seen = [], set()
    f, reader = open_csv(path, ["product", "snapshot_date", "price"])
    with f:
        for row in reader:
            i = reader.line_num
            product = (row["product"] or "").strip()
            if not product:
                fail(path, i, "product is empty")
            if not valid_date(row["snapshot_date"]):
                fail(path, i, f"snapshot_date {row['snapshot_date']!r} is not YYYY-MM-DD")
            key = (product, row["snapshot_date"])
            if key in seen:
                fail(path, i, f"duplicate snapshot for {product} on {row['snapshot_date']}")
            seen.add(key)
            price = parse_money(path, i, "price", row["price"])
            rows.append((product, row["snapshot_date"], price))
    if not rows:
        fail(path, 1, "no data rows after the header")
    return rows


def load_orders(path):
    rows, seen = [], set()
    f, reader = open_csv(path, ["order_id", "product", "order_date", "qty"])
    with f:
        for row in reader:
            i = reader.line_num
            try:
                order_id = int(row["order_id"])
            except (ValueError, TypeError):
                fail(path, i, f"order_id {row['order_id']!r} is not an integer")
            if order_id in seen:
                fail(path, i, f"duplicate order_id {order_id}")
            seen.add(order_id)
            product = (row["product"] or "").strip()
            if not product:
                fail(path, i, "product is empty")
            if not valid_date(row["order_date"]):
                fail(path, i, f"order_date {row['order_date']!r} is not YYYY-MM-DD")
            try:
                qty = int(row["qty"])
            except (ValueError, TypeError):
                fail(path, i, f"qty {row['qty']!r} is not an integer")
            if qty <= 0:
                fail(path, i, f"qty {qty} must be greater than zero")
            rows.append((order_id, product, row["order_date"], qty))
    if not rows:
        fail(path, 1, "no data rows after the header")
    return rows


def load_price_list(path):
    rows = []
    f, reader = open_csv(path, ["product", "valid_from", "valid_to", "price"])
    with f:
        for row in reader:
            i = reader.line_num
            product = (row["product"] or "").strip()
            if not product:
                fail(path, i, "product is empty")
            if not valid_date(row["valid_from"]):
                fail(path, i, f"valid_from {row['valid_from']!r} is not YYYY-MM-DD")
            valid_to = (row["valid_to"] or "").strip() or None
            if valid_to is not None:
                if not valid_date(valid_to):
                    fail(path, i, f"valid_to {valid_to!r} is not YYYY-MM-DD or blank")
                if valid_to < row["valid_from"]:
                    fail(path, i, f"valid_to {valid_to} is before valid_from {row['valid_from']}")
            price = parse_money(path, i, "price", row["price"])
            rows.append((product, row["valid_from"], valid_to, price))
    if not rows:
        fail(path, 1, "no data rows after the header")
    return rows


def build_db(snapshots_path):
    snapshots = load_snapshots(snapshots_path)
    orders = load_orders(ORDERS_CSV)
    price_list = load_price_list(PRICE_LIST_CSV)
    db = sqlite3.connect(":memory:")
    db.execute("CREATE TABLE price_snapshots (product TEXT NOT NULL, snapshot_date TEXT NOT NULL, price REAL NOT NULL)")
    db.execute("CREATE TABLE orders (order_id INTEGER PRIMARY KEY, product TEXT NOT NULL, order_date TEXT NOT NULL, qty INTEGER NOT NULL)")
    db.execute("CREATE TABLE price_list (product TEXT NOT NULL, valid_from TEXT NOT NULL, valid_to TEXT, price REAL NOT NULL)")
    db.executemany("INSERT INTO price_snapshots VALUES (?, ?, ?)", snapshots)
    db.executemany("INSERT INTO orders VALUES (?, ?, ?, ?)", orders)
    db.executemany("INSERT INTO price_list VALUES (?, ?, ?, ?)", price_list)
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
                   for t in ("price_snapshots", "orders", "price_list"))
    check("rows loaded (snapshots, orders, price list)", counts, (29, 8, 8))

    _, changes = run_query(db, SQL_DIR / "01-price-changes.sql")
    check("price change events", len(changes), 7)
    check("beans-340 change amounts",
          [r[4] for r in changes if r[0] == "beans-340"], [None, "+1.50", "-1.50"])

    _, history = run_query(db, SQL_DIR / "02-price-history.sql")
    check("price versions", len(history), 7)
    check("current versions", sum(1 for r in history if r[3] is None), 3)
    check("beans-340 history",
          [r[1:] for r in history if r[0] == "beans-340"],
          [(1, "2026-07-01", "2026-07-10", "14.00"),
           (2, "2026-07-11", "2026-07-21", "15.50"),
           (3, "2026-07-22", None, "14.00")])

    _, as_of = run_query(db, SQL_DIR / "03-price-as-of.sql")
    check("prices as of 2026-07-20",
          {r[0]: r[1] for r in as_of},
          {"cold-brew": "6.95", "beans-340": "15.50", "oat-milk": "3.25"})

    _, repriced = run_query(db, SQL_DIR / "04-order-repricing.sql")
    check("order line totals",
          {r[0]: r[5] for r in repriced},
          {1001: "13.00", 1002: "15.50", 1003: "9.75", 1004: "6.50",
           1005: "6.95", 1006: "28.00", 1007: None, 1008: "14.00"})
    check("priced order total",
          round(sum(float(r[5]) for r in repriced if r[5] is not None), 2), 93.70)

    _, issues = run_query(db, SQL_DIR / "05-history-checks.sql")
    check("price list issues by type",
          {k: sum(1 for r in issues if r[1] == k) for k in ("overlap", "gap", "multiple current rows")},
          {"overlap": 2, "gap": 1, "multiple current rows": 1})
    check("oat-milk gap detail",
          [r[2] for r in issues if r[1] == "gap"], ["2026-07-27 to 2026-07-28 uncovered"])

    print()
    if failures:
        print(f"{failures} check(s) failed")
        sys.exit(1)
    print("all checks passed")


def main():
    parser = argparse.ArgumentParser(description="Run the price history queries against the sample data.")
    parser.add_argument("--test", action="store_true", help="run the assertion suite instead of the reports")
    parser.add_argument("--snapshots", type=Path, default=SNAPSHOTS_CSV, help="path to an alternate snapshot CSV")
    args = parser.parse_args()

    db = build_db(args.snapshots)
    if args.test:
        run_tests(db)
    else:
        run_all(db)


if __name__ == "__main__":
    main()
