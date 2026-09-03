"""Load the product revenue table into SQLite and run the ABC queries.

Usage:
    python run.py                                   run every query in sql/
    python run.py --test                            run the assertion suite
    python run.py --products data/other.csv         load a different catalog
"""

import argparse
import csv
import io
import re
import sqlite3
import sys
from decimal import Decimal
from pathlib import Path

HERE = Path(__file__).parent
PRODUCTS_CSV = HERE / "data" / "products.csv"
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


def load_products(path):
    rows, seen = [], set()
    with read_csv(path) as f:
        reader = csv.DictReader(f)
        if reader.fieldnames != ["product", "revenue"]:
            fail(path, 1, f"expected columns product,revenue, got {reader.fieldnames}")
        for row in reader:
            i = reader.line_num
            if None in row:
                fail(path, i, "has more fields than the header")
            if any(v is None for v in row.values()):
                fail(path, i, "has fewer fields than the header")
            product = row["product"].strip()
            if not product:
                fail(path, i, "product name is empty")
            if product in seen:
                fail(path, i, f"product {product!r} appears twice; duplicates double-count revenue")
            seen.add(product)
            raw = row["revenue"].strip()
            # Money becomes integer cents so the running totals stay exact;
            # the shape check rejects exponents, thousands separators, and
            # anything past two decimal places before Decimal ever parses it.
            if not re.fullmatch(r"-?[0-9]+(\.[0-9]{1,2})?", raw):
                fail(path, i, f"revenue {row['revenue']!r} is not a money amount")
            # The sign is checked on the text, not the parsed value, so a
            # signed zero like -0.00 cannot sail through as a legal zero.
            if raw.startswith("-"):
                fail(path, i, f"revenue {raw!r} is negative; net returns out of revenue before ranking")
            cents = int(Decimal(raw) * 100)
            if cents >= 10 ** 15:
                fail(path, i, f"revenue {raw!r} is beyond anything plausible for one product")
            rows.append((product, cents))
    if not rows:
        fail(path, 1, "no data rows after the header")
    if len(rows) < 5:
        fail_file(path, f"ABC classes on fewer than 5 products are just a sorted list, found {len(rows)}")
    if sum(cents for _, cents in rows) == 0:
        fail_file(path, "every product has zero revenue; there is no total to take shares of")
    return rows


def build_db(products_path):
    products = load_products(products_path)
    db = sqlite3.connect(":memory:")
    db.execute("CREATE TABLE products (product TEXT PRIMARY KEY, revenue_cents INTEGER NOT NULL)")
    db.executemany("INSERT INTO products VALUES (?, ?)", products)
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

    check("products loaded",
          db.execute("SELECT COUNT(*) FROM products").fetchone()[0], 20)

    _, shape = run_query(db, SQL_DIR / "01-catalog-shape.sql")
    check("the total and both extremes",
          [(r[1], r[2], r[3], r[4], r[5]) for r in shape],
          [(100000.0, "Espresso Machine", 32000.0, "Spare Gasket", 20.0)])

    _, ranking = run_query(db, SQL_DIR / "02-revenue-ranking.sql")
    check("twenty ranked rows", len(ranking), 20)
    check("the top product holds just under a third of the total",
          [(r[1], r[3]) for r in ranking if r[0] == 1],
          [("Espresso Machine", 32.0)])
    check("the tie at 60.00 breaks on product name",
          [(r[0], r[1]) for r in ranking if r[2] == 60.0],
          [(17, "Bean Scoop"), (18, "Descaler")])

    _, cumulative = run_query(db, SQL_DIR / "03-cumulative-share.sql")
    check("four products reach exactly 80 percent",
          [(r[3], r[4]) for r in cumulative if r[0] == 4],
          [(80000.0, 80.0)])
    check("seven products reach exactly 95 percent",
          [(r[3], r[4]) for r in cumulative if r[0] == 7],
          [(95000.0, 95.0)])
    check("the tied rows carry distinct running shares",
          [r[4] for r in cumulative if r[0] in (17, 18)],
          [99.89, 99.95])

    _, classes = run_query(db, SQL_DIR / "04-abc-classes.sql")
    check("the best seller starts at zero and is an A by construction",
          [(r[3], r[5]) for r in classes if r[0] == 1], [(0.0, "A")])
    check("landing exactly on 80.00 keeps the A",
          [(r[3], r[4], r[5]) for r in classes if r[0] == 4], [(70.0, 80.0, "A")])
    check("starting exactly at 80.00 opens B",
          [(r[3], r[4], r[5]) for r in classes if r[0] == 5], [(80.0, 86.0, "B")])
    check("reaching exactly 95.00 is still a B",
          [(r[3], r[4], r[5]) for r in classes if r[0] == 7], [(91.0, 95.0, "B")])
    check("starting exactly at 95.00 opens C",
          [(r[3], r[4], r[5]) for r in classes if r[0] == 8], [(95.0, 96.4, "C")])
    check("the tail is C from rank 8 on",
          sorted({r[5] for r in classes if r[0] >= 8}), ["C"])

    _, summary = run_query(db, SQL_DIR / "05-class-summary.sql")
    check("the class roll-up is the Pareto sentence",
          summary,
          [("A", 4, 20.0, 80000.0, 80.0),
           ("B", 3, 15.0, 15000.0, 15.0),
           ("C", 13, 65.0, 5000.0, 5.0)])

    print()
    if failures:
        print(f"{failures} check(s) failed")
        sys.exit(1)
    print("all checks passed")


def main():
    parser = argparse.ArgumentParser(description="Run the ABC queries against the sample product catalog.")
    parser.add_argument("--test", action="store_true", help="run the assertion suite instead of the reports")
    parser.add_argument("--products", type=Path, default=PRODUCTS_CSV, help="path to an alternate products CSV")
    args = parser.parse_args()
    if args.test and args.products != PRODUCTS_CSV:
        parser.error("--test checks hand-computed answers for the sample catalog; run it without --products")

    db = build_db(args.products)
    if args.test:
        run_tests(db)
    else:
        run_all(db)


if __name__ == "__main__":
    main()
