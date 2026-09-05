"""Load orders and tax rates into SQLite and run the as-of join queries.

Usage:
    python run.py                                   run every query in sql/
    python run.py --test                            run the assertion suite
    python run.py --orders data/other.csv           load different orders
    python run.py --rates data/other.csv            load a different rate table
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
ORDERS_CSV = HERE / "data" / "orders.csv"
RATES_CSV = HERE / "data" / "tax_rates.csv"
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


def parse_date(path, row_num, field, raw):
    # Round-trip so non-zero-padded dates are rejected; strptime accepts them
    # but string comparison against them breaks the as-of ordering.
    try:
        parsed = datetime.strptime(raw, "%Y-%m-%d")
        if parsed.strftime("%Y-%m-%d") != raw:
            raise ValueError
    except (ValueError, TypeError):
        fail(path, row_num, f"{field} {raw!r} is not YYYY-MM-DD")
    return parsed.date()


def check_row_width(path, row_num, row):
    if None in row:
        fail(path, row_num, "has more fields than the header")
    if any(v is None for v in row.values()):
        fail(path, row_num, "has fewer fields than the header")


def load_orders(path):
    rows, seen, running = [], set(), 0
    with read_csv(path) as f:
        reader = csv.DictReader(f)
        if reader.fieldnames != ["order_id", "order_date", "customer", "net_amount"]:
            fail(path, 1, f"expected columns order_id,order_date,customer,net_amount, got {reader.fieldnames}")
        for row in reader:
            i = reader.line_num
            check_row_width(path, i, row)
            order_id = row["order_id"].strip()
            if not order_id:
                fail(path, i, "order_id is empty")
            if order_id in seen:
                fail(path, i, f"order_id {order_id!r} appears twice")
            seen.add(order_id)
            raw_date = row["order_date"].strip()
            parse_date(path, i, "order_date", raw_date)
            customer = row["customer"].strip()
            if not customer:
                fail(path, i, "customer is empty")
            raw = row["net_amount"].strip()
            if raw.startswith("-"):
                fail(path, i, f"net_amount {raw!r} is negative; credits are a different ledger")
            if not re.fullmatch(r"[0-9]+(\.[0-9]{1,2})?", raw):
                fail(path, i, f"net_amount {raw!r} is not a money amount")
            cents = int(Decimal(raw) * 100)
            if cents == 0:
                fail(path, i, "net_amount is zero; there is nothing to tax")
            if cents >= 10 ** 14:
                fail(path, i, f"net_amount {raw!r} is beyond anything plausible for one order")
            # Each order is capped, but the tax queries sum net times rate
            # across the whole file, so the total gets the same cap or a
            # long enough file could overflow SQLite's integers mid-query.
            running += cents
            if running >= 10 ** 14:
                fail(path, i, "the orders together total beyond anything plausible")
            rows.append((order_id, raw_date, customer, cents))
    if not rows:
        fail(path, 1, "no data rows after the header")
    return rows


def load_rates(path):
    rows, prev = [], None
    with read_csv(path) as f:
        reader = csv.DictReader(f)
        if reader.fieldnames != ["effective_date", "rate_percent"]:
            fail(path, 1, f"expected columns effective_date,rate_percent, got {reader.fieldnames}")
        for row in reader:
            i = reader.line_num
            check_row_width(path, i, row)
            raw_date = row["effective_date"].strip()
            day = parse_date(path, i, "effective_date", raw_date)
            # One rate per date, in order: a duplicated or out-of-order
            # effective date makes "the newest rate at or before" ambiguous.
            if prev is not None and day <= prev:
                fail(path, i, f"effective_date {raw_date} is not after the row above; one rate per date, in order, or the as-of pick is ambiguous")
            prev = day
            raw = row["rate_percent"].strip()
            if not re.fullmatch(r"[0-9]+(\.[0-9]{1,2})?", raw):
                fail(path, i, f"rate_percent {raw!r} is not a percentage")
            rate_bp = int(Decimal(raw) * 100)
            if rate_bp >= 10000:
                fail(path, i, f"rate_percent {raw!r} is not a plausible tax rate")
            rows.append((raw_date, rate_bp))
    if not rows:
        fail(path, 1, "no data rows after the header")
    return rows


def build_db(orders_path, rates_path):
    orders = load_orders(orders_path)
    rates = load_rates(rates_path)
    db = sqlite3.connect(":memory:")
    db.execute("""CREATE TABLE orders (
        order_id TEXT PRIMARY KEY,
        order_date TEXT NOT NULL,
        customer TEXT NOT NULL,
        net_cents INTEGER NOT NULL)""")
    db.execute("CREATE TABLE tax_rates (effective_date TEXT PRIMARY KEY, rate_bp INTEGER NOT NULL)")
    db.executemany("INSERT INTO orders VALUES (?, ?, ?, ?)", orders)
    db.executemany("INSERT INTO tax_rates VALUES (?, ?)", rates)
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
          db.execute("SELECT COUNT(*) FROM orders").fetchone()[0], 15)
    check("rate versions loaded",
          db.execute("SELECT COUNT(*) FROM tax_rates").fetchone()[0], 3)

    _, shape = run_query(db, SQL_DIR / "01-tables-shape.sql")
    check("both tables at a glance",
          shape,
          [(15, "2025-12-15", "2026-09-04", 13440.0, 3, "2026-01-01", "2026-07-01")])

    _, naive = run_query(db, SQL_DIR / "02-naive-join.sql")
    check("the naive join turns fifteen orders into twenty-nine rows",
          (len(naive), sum(r[2] for r in naive)), (14, 29))
    check("the naive join silently drops the pre-rate order",
          [r for r in naive if r[0] == "O-1001"], [])
    check("a third-era order collects all three rates",
          [(r[2], r[3]) for r in naive if r[0] == "O-1015"], [(3, 222.75)])

    _, asof = run_query(db, SQL_DIR / "03-asof-join.sql")
    check("every order surfaces, including the unpriceable one",
          (len(asof), [(r[4], r[5], r[6], r[8]) for r in asof if r[0] == "O-1001"]),
          (15, [(None, None, None, "no rate in force")]))
    check("the day before a change keeps the old rate",
          [(r[4], r[5], r[6]) for r in asof if r[0] == "O-1005"],
          [("2026-01-01", 5.0, 50.0)])
    check("the effective date itself carries the new rate",
          [(r[4], r[5], r[6]) for r in asof if r[0] == "O-1006"],
          [("2026-04-01", 6.0, 60.0)])
    check("a rate cut picks latest, not highest",
          [(r[4], r[5], r[6]) for r in asof if r[0] == "O-1011"],
          [("2026-07-01", 5.5, 44.0)])

    _, eras = run_query(db, SQL_DIR / "04-rate-eras.sql")
    check("the era construction agrees with the correlated pick",
          eras,
          [("2026-01-01", "2026-04-01", 5.0, 4, 3640.0, 182.0),
           ("2026-04-01", "2026-07-01", 6.0, 5, 4400.0, 264.0),
           ("2026-07-01", "open", 5.5, 5, 5000.0, 275.0)])
    check("both constructions land on the same 721.00",
          (round(sum(r[5] for r in eras), 2),
           round(sum(r[6] for r in asof if r[6] is not None), 2)),
          (721.0, 721.0))

    _, summary = run_query(db, SQL_DIR / "05-tax-summary.sql")
    check("the reconciliation line",
          summary,
          [(15, 14, 1, 13040.0, 721.0, 29, 1491.0, 770.0)])

    print()
    if failures:
        print(f"{failures} check(s) failed")
        sys.exit(1)
    print("all checks passed")


def main():
    parser = argparse.ArgumentParser(description="Run the as-of join queries against the sample tables.")
    parser.add_argument("--test", action="store_true", help="run the assertion suite instead of the reports")
    parser.add_argument("--orders", type=Path, default=ORDERS_CSV, help="path to an alternate orders CSV")
    parser.add_argument("--rates", type=Path, default=RATES_CSV, help="path to an alternate rates CSV")
    args = parser.parse_args()
    if args.test and (args.orders.resolve() != ORDERS_CSV.resolve()
                      or args.rates.resolve() != RATES_CSV.resolve()):
        parser.error("--test checks hand-computed answers for the sample tables; run it without --orders or --rates")

    db = build_db(args.orders, args.rates)
    if args.test:
        run_tests(db)
    else:
        run_all(db)


if __name__ == "__main__":
    main()
