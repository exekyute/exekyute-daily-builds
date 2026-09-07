"""Load the sales table into SQLite and run the ranking queries.

Usage:
    python run.py                                   run every query in sql/
    python run.py --test                            run the assertion suite
    python run.py --sales data/other.csv            load a different table
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


def norm_key(text):
    # Case and spacing are the two ways the same name arrives spelled twice.
    return " ".join(text.split()).casefold()


def load_sales(path):
    rows, seen, regions, running = [], {}, {}, 0
    with read_csv(path) as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None:
            fail_file(path, "is empty")
        if reader.fieldnames != ["region", "rep", "sales"]:
            fail(path, 1, f"expected columns region,rep,sales, got {reader.fieldnames}")
        for row in reader:
            i = reader.line_num
            if None in row:
                fail(path, i, "has more fields than the header")
            if any(v is None for v in row.values()):
                fail(path, i, "has fewer fields than the header")
            region = row["region"].strip()
            if not region:
                fail(path, i, "region is empty")
            # Regions are grouped by their exact text, so a second spelling
            # would quietly become a second region with its own top three.
            first_region = regions.setdefault(norm_key(region), region)
            if region != first_region:
                fail(path, i, f"region {region!r} matches {first_region!r} apart from case or spacing; "
                              "each spelling would rank as its own region")
            rep = row["rep"].strip()
            if not rep:
                fail(path, i, "rep is empty")
            # Every report keys on the rep name alone, so a name reused in a
            # second region would read as one person holding two ranks.
            first_rep = seen.get(norm_key(rep))
            if first_rep == rep:
                fail(path, i, f"rep {rep!r} appears twice; the reports identify reps by name")
            if first_rep is not None:
                fail(path, i, f"rep {rep!r} matches {first_rep!r} apart from case or spacing; "
                              "the reports identify reps by name")
            seen[norm_key(rep)] = rep
            raw = row["sales"].strip()
            # The sign is checked on the text so a signed zero cannot pass.
            if raw.startswith("-"):
                fail(path, i, f"sales {raw!r} is negative; returns net out before ranking")
            if not re.fullmatch(r"[0-9]+(\.[0-9]{1,2})?", raw):
                fail(path, i, f"sales {raw!r} is not a money amount")
            cents = int(Decimal(raw) * 100)
            if cents >= 10 ** 13:
                fail(path, i, f"sales {raw!r} is beyond anything plausible for one rep")
            running += cents
            if running >= 10 ** 14:
                fail(path, i, "the reps together total beyond anything plausible")
            rows.append((region, rep, cents))
    if not rows:
        fail(path, 1, "no data rows after the header")
    if len(rows) < 4:
        fail_file(path, f"a top-three cutoff needs something to cut, found {len(rows)} reps")
    return rows


def build_db(sales_path):
    # 02 uses a named WINDOW clause, which arrived in SQLite 3.28.
    if sqlite3.sqlite_version_info < (3, 28):
        print(f"needs SQLite 3.28 or newer for named window clauses, found {sqlite3.sqlite_version}",
              file=sys.stderr)
        sys.exit(2)
    sales = load_sales(sales_path)
    db = sqlite3.connect(":memory:")
    db.execute("""CREATE TABLE sales (
        region TEXT NOT NULL,
        rep TEXT PRIMARY KEY,
        sales_cents INTEGER NOT NULL)""")
    db.executemany("INSERT INTO sales VALUES (?, ?, ?)", sales)
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

    check("reps loaded",
          db.execute("SELECT COUNT(*) FROM sales").fetchone()[0], 21)

    _, shape = run_query(db, SQL_DIR / "01-region-shape.sql")
    check("four regions, three of them carrying ties",
          shape,
          [("East", 5, "212000.00", "47000.00", 1, 3, 3),
           ("North", 7, "313000.00", "52000.00", 1, 5, 4),
           ("South", 5, "233000.00", "50000.00", 3, 3, 3),
           ("West", 4, "162999.99", "46000.00", 1, 4, 0)])

    _, ranks = run_query(db, SQL_DIR / "02-three-ranks.sql")
    check("every rep ranked", len(ranks), 21)
    check("a three-way tie for first shares one rank and splits the row numbers",
          [(r[1], r[3], r[4], r[5]) for r in ranks if r[0] == "South" and r[2] == "50000.00"],
          [("Harper Vaughn", 1, 1, 1), ("Indra Blake", 2, 1, 1), ("Jules Kerr", 3, 1, 1)])
    check("RANK skips after a tie where DENSE_RANK does not",
          [(r[1], r[3], r[4], r[5]) for r in ranks if r[0] == "South" and r[2] != "50000.00"],
          [("Kai Osei", 4, 4, 2), ("Lane Whitfield", 5, 5, 3)])
    check("the three-way tie for second straddles the cutoff",
          [(r[1], r[3], r[4], r[5]) for r in ranks if r[0] == "East" and r[2] == "43000.00"],
          [("Noor Ali", 2, 2, 2), ("Omar Diaz", 3, 2, 2), ("Piper Lund", 4, 2, 2)])
    check("one cent of daylight leaves nothing for the rules to disagree about",
          [(r[1], r[2], r[3], r[4], r[5]) for r in ranks if r[0] == "West"],
          [("Rowan Fitz", "46000.00", 1, 1, 1), ("Sage Bright", "42000.00", 2, 2, 2),
           ("Tobin Clark", "41999.99", 3, 3, 3), ("Uma Rey", "33000.00", 4, 4, 4)])

    _, top = run_query(db, SQL_DIR / "03-top-three.sql")
    check("seventeen reps are selected by at least one rule", len(top), 17)
    check("the rep with identical sales that ROW_NUMBER alone excludes",
          [(r[6], r[7], r[8]) for r in top if r[1] == "Piper Lund"],
          [("", "yes", "yes")])
    check("all three rules agree on every West rep they select",
          [(r[6], r[7], r[8]) for r in top if r[0] == "West"],
          [("yes", "yes", "yes")] * 3)

    _, gaps = run_query(db, SQL_DIR / "04-disagreements.sql")
    check("five disagreements, one of them decided by the alphabet",
          [(r[1], r[6], r[7]) for r in gaps],
          [("Piper Lund", "cut by the tiebreak at equal sales", 2),
           ("Quinn Reyes", "inside the top three amounts, past the third place", 0),
           ("Devon Park", "inside the top three amounts, past the third place", 0),
           ("Kai Osei", "inside the top three amounts, past the third place", 0),
           ("Lane Whitfield", "inside the top three amounts, past the third place", 0)])

    _, cost = run_query(db, SQL_DIR / "05-bonus-cost.sql")
    check("the same sentence funds twelve, thirteen, or seventeen people",
          [(r[0], r[1], r[2]) for r in cost],
          [("ROW_NUMBER", 12, "12000.00"), ("RANK", 13, "13000.00"), ("DENSE_RANK", 17, "17000.00")])

    print()
    if failures:
        print(f"{failures} check(s) failed")
        sys.exit(1)
    print("all checks passed")


def main():
    parser = argparse.ArgumentParser(description="Run the ranking queries against the sample sales table.")
    parser.add_argument("--test", action="store_true", help="run the assertion suite instead of the reports")
    parser.add_argument("--sales", type=Path, default=SALES_CSV, help="path to an alternate sales CSV")
    args = parser.parse_args()
    if args.test and args.sales.resolve() != SALES_CSV.resolve():
        parser.error("--test checks hand-computed answers for the sample table; run it without --sales")

    db = build_db(args.sales)
    if args.test:
        run_tests(db)
    else:
        run_all(db)


if __name__ == "__main__":
    main()
