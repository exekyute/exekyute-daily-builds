"""Load the category tree and expenses into SQLite and run the rollup queries.

Usage:
    python run.py                                     run every query in sql/
    python run.py --test                              run the assertion suite
    python run.py --categories data/other.csv         load a different tree
    python run.py --draft data/other.csv              check a different draft tree
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
CATEGORIES_CSV = HERE / "data" / "categories.csv"
EXPENSES_CSV = HERE / "data" / "expenses.csv"
DRAFT_CSV = HERE / "data" / "draft-categories.csv"
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
        fail(path, row_num, f"amount {raw!r} is beyond any plausible expense")
    return int(cents)


def parse_int(path, row_num, label, raw):
    try:
        value = int(raw)
    except (ValueError, TypeError):
        fail(path, row_num, f"{label} {raw!r} is not an integer")
    if not 0 < value < 2 ** 63:
        fail(path, row_num, f"{label} {value} is out of range")
    return value


def load_categories(path, strict):
    detailed, seen = [], set()
    with read_csv(path) as f:
        reader = csv.DictReader(f)
        if reader.fieldnames != ["category_id", "parent_id", "name"]:
            fail(path, 1, f"expected columns category_id,parent_id,name, got {reader.fieldnames}")
        for row in reader:
            i = reader.line_num
            if None in row:
                fail(path, i, "has more fields than the header")
            category_id = parse_int(path, i, "category_id", row["category_id"])
            if category_id in seen:
                fail(path, i, f"duplicate category_id {category_id}")
            seen.add(category_id)
            parent_raw = (row["parent_id"] or "").strip()
            parent_id = parse_int(path, i, "parent_id", parent_raw) if parent_raw else None
            if not (row["name"] or "").strip():
                fail(path, i, "name is empty")
            detailed.append((i, category_id, parent_id, row["name"].strip()))
    if not detailed:
        fail(path, 1, "no data rows after the header")
    if strict:
        # The live tree must be a real tree: every parent exists and no chain
        # of parents loops back on itself. The draft file skips this on
        # purpose, because finding exactly these problems in SQL is what the
        # hierarchy checks are for.
        parents = {cid: pid for _, cid, pid, _ in detailed}
        for i, cid, pid, _ in detailed:
            if pid is not None and pid not in parents:
                fail(path, i, f"parent_id {pid} does not exist")
        for i, cid, pid, _ in detailed:
            chain, cur = {cid}, pid
            while cur is not None:
                if cur in chain:
                    fail(path, i, f"category {cid} sits in a parent cycle")
                chain.add(cur)
                cur = parents[cur]
    return [(cid, pid, name) for _, cid, pid, name in detailed]


def load_expenses(path, known_categories):
    rows, seen = [], set()
    with read_csv(path) as f:
        reader = csv.DictReader(f)
        if reader.fieldnames != ["expense_id", "category_id", "expense_date", "amount"]:
            fail(path, 1, f"expected columns expense_id,category_id,expense_date,amount, got {reader.fieldnames}")
        for row in reader:
            i = reader.line_num
            if None in row:
                fail(path, i, "has more fields than the header")
            expense_id = parse_int(path, i, "expense_id", row["expense_id"])
            if expense_id in seen:
                fail(path, i, f"duplicate expense_id {expense_id}")
            seen.add(expense_id)
            category_id = parse_int(path, i, "category_id", row["category_id"])
            if category_id not in known_categories:
                fail(path, i, f"category_id {category_id} has no row in categories.csv")
            if not valid_date(row["expense_date"]):
                fail(path, i, f"expense_date {row['expense_date']!r} is not YYYY-MM-DD")
            cents = parse_cents(path, i, row["amount"])
            rows.append((expense_id, category_id, row["expense_date"], cents))
    if not rows:
        fail(path, 1, "no data rows after the header")
    return rows


def build_db(categories_path, expenses_path, draft_path):
    categories = load_categories(categories_path, strict=True)
    expenses = load_expenses(expenses_path, {c[0] for c in categories})
    draft = load_categories(draft_path, strict=False)
    db = sqlite3.connect(":memory:")
    db.execute("CREATE TABLE categories (category_id INTEGER PRIMARY KEY, parent_id INTEGER, name TEXT NOT NULL)")
    db.execute("CREATE TABLE expenses (expense_id INTEGER PRIMARY KEY, category_id INTEGER NOT NULL, expense_date TEXT NOT NULL, cents INTEGER NOT NULL)")
    db.execute("CREATE TABLE draft_categories (category_id INTEGER PRIMARY KEY, parent_id INTEGER, name TEXT NOT NULL)")
    db.executemany("INSERT INTO categories VALUES (?, ?, ?)", categories)
    db.executemany("INSERT INTO expenses VALUES (?, ?, ?, ?)", expenses)
    db.executemany("INSERT INTO draft_categories VALUES (?, ?, ?)", draft)
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
                   for t in ("categories", "expenses", "draft_categories"))
    check("rows loaded (categories, expenses, draft)", counts, (11, 11, 7))

    _, tree = run_query(db, SQL_DIR / "01-tree.sql")
    check("tree rows in outline order", len(tree), 11)
    check("electricity sits three levels deep",
          [(r[1], r[2]) for r in tree if r[0] == 5],
          [(3, "Operations > Facilities > Utilities > Electricity")])
    check("first root in outline order", tree[0][2], "Marketing")

    _, direct = run_query(db, SQL_DIR / "02-direct-spend.sql")
    check("direct spend keeps mid-node charges and zero rows",
          {r[0]: r[2] for r in direct if r[0] in
           ("Operations > Facilities", "Operations > Facilities > Utilities", "Operations > Facilities > Rent")},
          {"Operations > Facilities": "0.00",
           "Operations > Facilities > Utilities": "55.25",
           "Operations > Facilities > Rent": "2460.00"})

    _, rollup = run_query(db, SQL_DIR / "03-subtree-rollup.sql")
    check("subtree totals",
          {r[0]: r[2] for r in rollup if r[0] in
           ("Operations", "Operations > Facilities", "Operations > Facilities > Utilities", "Marketing")},
          {"Operations": "3540.04",
           "Operations > Facilities": "3199.55",
           "Operations > Facilities > Utilities": "739.55",
           "Marketing": "2450.00"})
    check("leaf subtree equals its direct spend",
          [r[2] for r in rollup if r[0] == "Operations > Supplies > Cleaning"], ["129.99"])

    _, proof = run_query(db, SQL_DIR / "04-rollup-check.sql")
    check("rollup proofs",
          proof,
          [("root subtrees equal the grand total", "5990.04 vs 5990.04", "ok"),
           ("every parent equals its own spend plus its children", "0 violations", "ok")])

    _, issues = run_query(db, SQL_DIR / "05-hierarchy-checks.sql")
    check("draft hierarchy issues",
          [(r[0], r[1]) for r in issues],
          [("cycle", 104), ("cycle", 105), ("cycle", 106),
           ("self-parent", 107), ("unknown parent", 103)])

    print()
    if failures:
        print(f"{failures} check(s) failed")
        sys.exit(1)
    print("all checks passed")


def main():
    parser = argparse.ArgumentParser(description="Run the hierarchy rollup queries against the sample tree.")
    parser.add_argument("--test", action="store_true", help="run the assertion suite instead of the reports")
    parser.add_argument("--categories", type=Path, default=CATEGORIES_CSV, help="path to an alternate category CSV")
    parser.add_argument("--expenses", type=Path, default=EXPENSES_CSV, help="path to an alternate expense CSV")
    parser.add_argument("--draft", type=Path, default=DRAFT_CSV, help="path to an alternate draft tree CSV")
    args = parser.parse_args()

    db = build_db(args.categories, args.expenses, args.draft)
    if args.test:
        run_tests(db)
    else:
        run_all(db)


if __name__ == "__main__":
    main()
