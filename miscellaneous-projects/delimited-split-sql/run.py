"""Load the product catalog into SQLite and run the tag-splitting queries.

Usage:
    python run.py                                   run every query in sql/
    python run.py --test                            run the assertion suite
    python run.py --products data/other.csv         load a different catalog
"""

import argparse
import csv
import io
import sqlite3
import sys
import unicodedata
from pathlib import Path

HERE = Path(__file__).parent
PRODUCTS_CSV = HERE / "data" / "products.csv"
SQL_DIR = HERE / "sql"
COLUMNS = ["product_id", "name", "tags"]
NBSP = "\u00a0"


def fail(path, row_num, message):
    print(f"{path.name} row {row_num}: {message}", file=sys.stderr)
    sys.exit(2)


def fail_file(path, message):
    print(f"{Path(path).name}: {message}", file=sys.stderr)
    sys.exit(2)


def read_csv(path, columns):
    # utf-8-sig strips the byte-order mark that Excel puts on its CSV exports.
    try:
        text = Path(path).read_text(encoding="utf-8-sig")
    except OSError as err:
        fail_file(path, err.strerror or "cannot be read")
    except UnicodeDecodeError:
        fail_file(path, "is not UTF-8 text")
    # strict, because the lenient parser folds text that follows a closing
    # quote back into the field and hands over a garbled row without a word.
    reader = csv.reader(io.StringIO(text, newline=""), strict=True)
    try:
        header = next(reader)
    except StopIteration:
        fail_file(path, "is empty")
    except csv.Error as err:
        fail(path, 1, f"cannot be parsed ({err})")
    if header != columns:
        fail(path, 1, f"expected columns {','.join(columns)}, got {header}")
    return reader


def records(path, reader, columns):
    # Yields each record with the line it started on. reader.line_num is where
    # a record ended, and for a stray quote that is wherever a later quote
    # finally closed it, possibly many lines on; a blank line before a record
    # would shift the count as well.
    start = reader.line_num + 1
    try:
        for fields in reader:
            if not fields:
                start = reader.line_num + 1
                continue
            # A field spanning lines is almost always an unclosed quote that
            # has swallowed the rows after it. It is checked before the field
            # count, because a swallowed row usually leaves the count wrong
            # too, and the quote is the problem worth naming.
            if any(ch in f for f in fields for ch in "\r\n"):
                fail(path, start, "a field runs across more than one line; "
                                  "most likely a quote that never closes")
            # Control characters have no place in a tag list, and a NUL is
            # worse than out of place: depending on where it falls, the split
            # cuts a tag short, drops the tags after it, or never finishes. A
            # tab is the one control character allowed, since query 03 trims
            # it off the ends of a tag the same way it trims a space.
            bad = next((ch for f in fields for ch in f
                        if unicodedata.category(ch) == "Cc" and ch != "\t"), None)
            if bad is not None:
                fail(path, start, f"contains the control character {bad!r}")
            if len(fields) > len(columns):
                fail(path, start, "has more fields than the header")
            if len(fields) < len(columns):
                fail(path, start, "has fewer fields than the header")
            yield start, dict(zip(columns, fields))
            start = reader.line_num + 1
    except csv.Error as err:
        fail(path, start, f"cannot be parsed ({err}); most likely a quote out of place")


def cell(path, row_num, row, column, collapse=True, required=True):
    value = unicodedata.normalize("NFC", row[column])
    if collapse:
        value = " ".join(value.split())
    if required and not value.strip():
        fail(path, row_num, f"{column} is empty")
    return value


def load_products(path):
    rows, seen = [], {}
    reader = read_csv(path, COLUMNS)
    for i, row in records(path, reader, COLUMNS):
        product = cell(path, i, row, "product_id")
        first = seen.get(product.casefold())
        if first == product:
            fail(path, i, f"product_id {product!r} appears twice")
        if first is not None:
            fail(path, i, f"product_id {product!r} matches {first!r} apart from letter case")
        seen[product.casefold()] = product
        name = cell(path, i, row, "name")
        # The spaces and capitals in a tag list are left as written, since
        # that mess is what the queries are about. The one change made is the
        # Unicode normalisation every field gets, so an accented letter typed
        # as one character or as a letter plus accent reads the same.
        tags = cell(path, i, row, "tags", collapse=False, required=False)
        rows.append((product, name, tags))
    if not rows:
        fail(path, 1, "no data rows after the header")
    return rows


def new_db():
    db = sqlite3.connect(":memory:")
    db.execute("CREATE TABLE products (product_id TEXT PRIMARY KEY, name TEXT NOT NULL, "
               "tags TEXT NOT NULL)")
    return db


def build_db(products_path):
    products = load_products(products_path)
    db = new_db()
    db.executemany("INSERT INTO products VALUES (?, ?, ?)", products)
    return db


def print_table(headers, rows):
    cells = [[("" if v is None else str(v)) for v in row] for row in rows]
    widths = [max(len(h), *(len(r[i]) for r in cells)) if cells else len(h)
              for i, h in enumerate(headers)]
    print("  ".join(h.ljust(widths[i]) for i, h in enumerate(headers)).rstrip())
    print("  ".join("-" * w for w in widths))
    for row in cells:
        print("  ".join(row[i].ljust(widths[i]) for i in range(len(headers))).rstrip())


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

    check("twelve products loaded",
          db.execute("SELECT COUNT(*) FROM products").fetchone()[0], 12)

    _, shape = run_query(db, SQL_DIR / "01-catalog-shape.sql")
    check("eleven tagged, one bare, twenty-four tags by counting commas",
          shape, [(12, 11, 1, 24, 3)])

    _, trap = run_query(db, SQL_DIR / "02-like-trap.sql")
    check("LIKE '%red%' returns eight products",
          [r[0] for r in trap],
          ["P-01", "P-02", "P-03", "P-04", "P-05", "P-06", "P-07", "P-09"])

    _, split = run_query(db, SQL_DIR / "03-split-tags.sql")
    check("the split yields twenty-four tag rows", len(split), 24)
    check("the split agrees with the comma count from query 01",
          len(split), shape[0][3])
    check("a list typed with spaces and capitals splits into clean tags",
          [(r[0], r[2], r[3]) for r in split if r[0] in ("P-04", "P-05")],
          [("P-04", 1, "white"), ("P-04", 2, "infrared"), ("P-04", 3, "wireless"),
           ("P-05", 1, "red"), ("P-05", 2, "large")])
    check("a single tag with no comma splits, and an empty list yields nothing",
          ([(r[0], r[3]) for r in split if r[0] == "P-09"],
           [r for r in split if r[0] == "P-11"]),
          ([("P-09", "red")], []))
    check("exactly four of the eight LIKE matches carry red as a tag",
          sorted({r[0] for r in split if r[3] == "red"}),
          ["P-01", "P-03", "P-05", "P-09"])

    _, three = run_query(db, SQL_DIR / "04-three-ways.sql")
    check("eleven tags compared, four of them in disagreement",
          (len(three), sum(r[4] != "agree" for r in three)), (11, 4))
    check("the substring LIKE over-matches red and nothing else",
          [(r[0], r[1], r[3]) for r in three if r[4] == "substring over-matches"],
          [("red", 4, 8)])
    check("the padded LIKE under-matches exactly the tags typed after a space",
          [(r[0], r[1], r[2]) for r in three if r[4] == "padded under-matches"],
          [("infrared", 2, 1), ("large", 4, 3), ("wireless", 2, 1)])

    _, counts = run_query(db, SQL_DIR / "05-tag-counts.sql")
    check("red was typed two ways and counts once",
          [(r[0], r[1], r[2]) for r in counts if r[0] == "red"], [("red", 4, 2)])
    check("the per-tag counts add back up to every tag mention",
          sum(r[1] for r in counts), 24)

    # The sample has only plain spaces around its tags. Text pasted from a web
    # page or a spreadsheet brings tabs and non-breaking spaces as well, which
    # SQLite's trim() leaves in place unless it is handed them explicitly. The
    # set is written out in four queries, so all four are run against a pasted
    # sample here, and reverting any of them to a one-argument trim() makes
    # this check fail.
    pasted = new_db()
    pasted.executemany("INSERT INTO products VALUES (?, ?, ?)",
                       [("X-1", "Lamp", "red,large"),
                        ("X-2", "Mug", "red,\tlarge"),
                        ("X-3", "Rug", "red\t,large"),
                        ("X-4", "Mat", "blue,\t,small"),
                        ("X-5", "Kettle", "red," + NBSP + "large"),
                        ("X-6", "Vase", "\t"),
                        ("X-7", "Cup", NBSP)])
    clean = {"blue", "large", "red", "small"}
    _, p_shape = run_query(pasted, SQL_DIR / "01-catalog-shape.sql")
    _, p_split = run_query(pasted, SQL_DIR / "03-split-tags.sql")
    _, p_three = run_query(pasted, SQL_DIR / "04-three-ways.sql")
    _, p_counts = run_query(pasted, SQL_DIR / "05-tag-counts.sql")
    check("pasted whitespace trims away in every query that carries the set",
          (p_shape, {r[3] for r in p_split},
           [r[0] for r in p_three], [(r[0], r[1]) for r in p_counts]),
          ([(7, 5, 2, 11, 3)], clean, sorted(clean),
           [("large", 4), ("red", 4), ("blue", 1), ("small", 1)]))

    print()
    if failures:
        print(f"{failures} check(s) failed")
        sys.exit(1)
    print("all checks passed")


def main():
    parser = argparse.ArgumentParser(description="Run the tag-splitting queries against the sample catalog.")
    parser.add_argument("--test", action="store_true", help="run the assertion suite instead of the reports")
    parser.add_argument("--products", type=Path, default=PRODUCTS_CSV, help="path to an alternate products CSV")
    args = parser.parse_args()
    # The loader accepts UTF-8 text beyond the controls it refuses, so the
    # reports have to be able to print it. Output piped or redirected on
    # Windows falls back to a codepage that cannot, even where the console
    # itself would manage.
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    if not args.products.is_file():
        parser.error(f"--products: '{args.products}' is not a file")
    if args.test and args.products.resolve() != PRODUCTS_CSV.resolve():
        parser.error("--test checks hand-computed answers for the sample catalog; run it without --products")

    db = build_db(args.products)
    if args.test:
        run_tests(db)
    else:
        run_all(db)


if __name__ == "__main__":
    main()
