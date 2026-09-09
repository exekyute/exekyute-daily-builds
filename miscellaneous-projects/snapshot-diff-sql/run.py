"""Load two price-list snapshots into SQLite and run the diff queries.

Usage:
    python run.py                                   run every query in sql/
    python run.py --test                            run the assertion suite
    python run.py --before data/other.csv           load an earlier snapshot
    python run.py --after data/other.csv            load a later snapshot
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
BEFORE_CSV = HERE / "data" / "prices-2026-08-01.csv"
AFTER_CSV = HERE / "data" / "prices-2026-09-01.csv"
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


def norm_key(text):
    # Case and spacing are the two ways one SKU arrives spelled twice.
    return " ".join(text.split()).casefold()


def load_prices(path):
    rows, seen, running = [], {}, 0
    with read_csv(path) as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None:
            fail_file(path, "is empty")
        if reader.fieldnames != ["sku", "description", "price"]:
            fail(path, 1, f"expected columns sku,description,price, got {reader.fieldnames}")
        for row in reader:
            i = reader.line_num
            if None in row:
                fail(path, i, "has more fields than the header")
            if any(v is None for v in row.values()):
                fail(path, i, "has fewer fields than the header")
            sku = row["sku"].strip()
            if not sku:
                fail(path, i, "sku is empty")
            # EXCEPT and INTERSECT return distinct rows, so a SKU listed
            # twice has no meaning in a diff, which is why both tables
            # declare it a primary key. That key would reject the row too;
            # catching it here names the line instead of raising.
            first = seen.get(norm_key(sku))
            if first == sku:
                fail(path, i, f"sku {sku!r} appears twice; EXCEPT and INTERSECT return distinct rows, "
                              "so a repeated SKU has no meaning in a diff")
            if first is not None:
                fail(path, i, f"sku {sku!r} matches {first!r} apart from case or spacing; "
                              "the diff compares SKU text exactly, so both spellings would survive")
            seen[norm_key(sku)] = sku
            # Internal whitespace is collapsed as well as trimmed: a
            # line break inside a quoted
            # cell would otherwise survive into the fixed-width report and
            # split the row across two lines.
            description = " ".join(row["description"].split())
            if not description:
                fail(path, i, "description is empty")
            raw = row["price"].strip()
            # An empty price is a real state in a price list, a product whose
            # price is not set yet, and it is the state the diff has to
            # handle rather than reject.
            if not raw:
                rows.append((sku, description, None))
                continue
            if raw.startswith("-"):
                fail(path, i, f"price {raw!r} carries a minus sign; a price list has no negative lines")
            if not re.fullmatch(r"[0-9]+(\.[0-9]{1,2})?", raw):
                fail(path, i, f"price {raw!r} is not a money amount")
            cents = int(Decimal(raw) * 100)
            if cents >= 10 ** 13:
                fail(path, i, f"price {raw!r} is beyond anything plausible for one line")
            running += cents
            if running >= 10 ** 14:
                fail(path, i, "the lines together total beyond anything plausible")
            rows.append((sku, description, cents))
    if not rows:
        fail(path, 1, "no data rows after the header")
    return rows


def build_db(before_path, after_path):
    before = load_prices(before_path)
    after = load_prices(after_path)
    db = sqlite3.connect(":memory:")
    for table in ("prices_before", "prices_after"):
        db.execute(f"""CREATE TABLE {table} (
            sku TEXT PRIMARY KEY,
            description TEXT NOT NULL,
            price_cents INTEGER)""")
    db.executemany("INSERT INTO prices_before VALUES (?, ?, ?)", before)
    db.executemany("INSERT INTO prices_after VALUES (?, ?, ?)", after)
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

    check("both snapshots loaded",
          (db.execute("SELECT COUNT(*) FROM prices_before").fetchone()[0],
           db.execute("SELECT COUNT(*) FROM prices_after").fetchone()[0]),
          (13, 13))

    _, shape = run_query(db, SQL_DIR / "01-snapshots-shape.sql")
    check("thirteen lines each, eleven SKUs shared, fifteen in either",
          shape, [(13, 13, 2, 2, 11, 15)])

    _, trap = run_query(db, SQL_DIR / "02-the-trap.sql")
    check("every shared SKU compared", len(trap), 11)
    check("a price arriving from unset reads unchanged to the naive rule",
          [(r[3], r[4], r[5], r[6]) for r in trap if r[0] == "B-200"],
          [("not set", "12.00", "unchanged", "changed")])
    check("a price leaving for unset reads unchanged to the naive rule",
          [(r[3], r[4], r[5], r[6]) for r in trap if r[0] == "B-201"],
          [("9.75", "not set", "unchanged", "changed")])
    check("unset on both sides is genuinely unchanged, and both rules agree",
          [(r[3], r[4], r[5], r[6]) for r in trap if r[0] == "B-202"],
          [("not set", "not set", "unchanged", "unchanged")])
    check("four changes under the naive rule, six under the honest one",
          (sum(1 for r in trap if r[5] == "changed"),
           sum(1 for r in trap if r[6] == "changed")),
          (4, 6))

    _, moved = run_query(db, SQL_DIR / "03-added-and-removed.sql")
    check("two SKUs arrived and two left",
          moved,
          [("added", "E-500", "Roller Chain 40", "31.00"),
           ("added", "E-501", "Chain Link 40", "2.80"),
           ("removed", "C-301", "Drive Belt 5L", "16.50"),
           ("removed", "C-302", "Timing Belt", "22.00")])

    _, changed = run_query(db, SQL_DIR / "04-changed.sql")
    check("EXCEPT recovers all six changes, including the two NULL crossings",
          [(r[0], r[3], r[4], r[5]) for r in changed],
          [("A-102", "1.25", "1.40", "price"),
           ("A-103", "0.45", "0.40", "price"),
           ("A-104", "0.30", "0.30", "description"),
           ("B-200", "not set", "12.00", "price"),
           ("B-201", "9.75", "not set", "price"),
           ("C-303", "26.00", "28.50", "description price")])
    check("a description edit at a steady price still counts as a change",
          [(r[1], r[2]) for r in changed if r[0] == "A-104"],
          [("Flat Washer M8", "Flat Washer M8 Zinc")])

    check("the NULL-safe verdict in 02 names exactly the SKUs that 04 returns",
          sorted(r[0] for r in trap if r[6] == "changed"),
          sorted(r[0] for r in changed))

    _, recon = run_query(db, SQL_DIR / "05-reconciliation.sql")
    check("the four buckets partition the fifteen SKUs exactly",
          recon, [(2, 2, 6, 5, 15, "balances", 2)])

    print()
    if failures:
        print(f"{failures} check(s) failed")
        sys.exit(1)
    print("all checks passed")


def main():
    parser = argparse.ArgumentParser(description="Run the diff queries against the sample snapshots.")
    parser.add_argument("--test", action="store_true", help="run the assertion suite instead of the reports")
    parser.add_argument("--before", type=Path, default=BEFORE_CSV, help="path to the earlier snapshot CSV")
    parser.add_argument("--after", type=Path, default=AFTER_CSV, help="path to the later snapshot CSV")
    args = parser.parse_args()
    if args.test and (args.before.resolve() != BEFORE_CSV.resolve()
                      or args.after.resolve() != AFTER_CSV.resolve()):
        parser.error("--test checks hand-computed answers for the sample snapshots; "
                     "run it without --before or --after")

    db = build_db(args.before, args.after)
    if args.test:
        run_tests(db)
    else:
        run_all(db)


if __name__ == "__main__":
    main()
