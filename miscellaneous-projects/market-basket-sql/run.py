"""Load the sample order lines into SQLite and run the basket queries.

Usage:
    python run.py                                run every query in sql/
    python run.py --test                         run the assertion suite
    python run.py --lines data/other.csv         load a different line file
"""

import argparse
import csv
import io
import re
import sqlite3
import sys
from pathlib import Path

HERE = Path(__file__).parent
LINES_CSV = HERE / "data" / "order_lines.csv"
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


def load_lines(path):
    rows, seen = [], set()
    with read_csv(path) as f:
        reader = csv.DictReader(f)
        if reader.fieldnames != ["order_id", "product"]:
            fail(path, 1, f"expected columns order_id,product, got {reader.fieldnames}")
        for row in reader:
            i = reader.line_num
            if None in row:
                fail(path, i, "has more fields than the header")
            # Plain ASCII digits only: Python's int() would quietly read
            # '1_0' as 10 and merge the line into an unrelated order.
            raw_id = (row["order_id"] or "").strip()
            if not re.fullmatch(r"[0-9]+", raw_id):
                fail(path, i, f"order_id {row['order_id']!r} is not an integer")
            order_id = int(raw_id)
            if not 0 < order_id < 2 ** 63:
                fail(path, i, f"order_id {order_id} is out of range")
            product = (row["product"] or "").strip()
            if not product:
                fail(path, i, "product is empty")
            # One line per product per order; the pair join assumes it.
            key = (order_id, product)
            if key in seen:
                fail(path, i, f"second {product} line in order {order_id}")
            seen.add(key)
            rows.append((order_id, product))
    if not rows:
        fail(path, 1, "no data rows after the header")
    if len({r[0] for r in rows}) < 2:
        fail_file(path, "basket analysis needs at least 2 orders")
    return rows


def build_db(lines_path):
    lines = load_lines(lines_path)
    db = sqlite3.connect(":memory:")
    db.execute("CREATE TABLE order_lines (order_id INTEGER NOT NULL, product TEXT NOT NULL)")
    db.executemany("INSERT INTO order_lines VALUES (?, ?)", lines)
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

    check("lines and orders loaded",
          (db.execute("SELECT COUNT(*) FROM order_lines").fetchone()[0],
           db.execute("SELECT COUNT(DISTINCT order_id) FROM order_lines").fetchone()[0]),
          (42, 20))

    _, products = run_query(db, SQL_DIR / "01-product-counts.sql")
    check("product order counts",
          {r[0]: r[1] for r in products},
          {"espresso": 12, "croissant": 10, "cold-brew": 6, "cookie": 6,
           "muffin": 4, "tea": 4})

    _, pairs = run_query(db, SQL_DIR / "02-pair-counts.sql")
    check("distinct co-occurring pairs", len(pairs), 11)
    check("top raw pairs",
          [(r[0], r[1], r[2]) for r in pairs[:2]],
          [("croissant", "espresso", 6), ("cold-brew", "cookie", 5)])

    _, conf = run_query(db, SQL_DIR / "03-support-confidence.sql")
    check("every muffin came with a croissant",
          [(r[4], r[5]) for r in conf if (r[0], r[1]) == ("croissant", "muffin")],
          [("40.0%", "100.0%")])

    _, lift = run_query(db, SQL_DIR / "04-lift.sql")
    check("lift corrects the raw counts",
          {(r[0], r[1]): (r[4], r[5]) for r in lift
           if (r[0], r[1]) in (("croissant", "espresso"), ("cold-brew", "cookie"), ("espresso", "tea"))},
          {("croissant", "espresso"): (1.0, "about chance"),
           ("cold-brew", "cookie"): (2.78, "above chance"),
           ("espresso", "tea"): (0.42, "below chance")})
    check("the 2-order pairs lift high but stay unproven",
          [(r[2], r[4]) for r in lift if (r[0], r[1]) in (("cold-brew", "tea"), ("cookie", "tea"))],
          [(2, 1.67), (2, 1.67)])

    _, picks = run_query(db, SQL_DIR / "05-bundle-picks.sql")
    check("bundle picks pass both gates",
          [(r[0], r[1], r[2], r[3]) for r in picks],
          [("cold-brew", "cookie", 5, 2.78), ("croissant", "muffin", 4, 2.0)])

    print()
    if failures:
        print(f"{failures} check(s) failed")
        sys.exit(1)
    print("all checks passed")


def main():
    parser = argparse.ArgumentParser(description="Run the basket queries against the sample order lines.")
    parser.add_argument("--test", action="store_true", help="run the assertion suite instead of the reports")
    parser.add_argument("--lines", type=Path, default=LINES_CSV, help="path to an alternate order-line CSV")
    args = parser.parse_args()

    db = build_db(args.lines)
    if args.test:
        run_tests(db)
    else:
        run_all(db)


if __name__ == "__main__":
    main()
