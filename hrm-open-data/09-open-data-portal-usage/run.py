"""Thin driver for the open-data portal usage pipeline.

This file holds no analytical logic. It executes the SQL files in order (00 to
99), which do all of the loading, transforming, aggregating, ranking, and
exporting, then it diffs the generated output against the golden copies in
expected/.

Usage:
    python run.py            run the SQL end to end, then verify out vs expected
    python run.py verify     re-run only the out-vs-expected diff
    python run.py show       print the monthly series and top datasets as tables
"""

import os
import sys

import duckdb

HERE = os.path.dirname(os.path.abspath(__file__))
SQL_DIR = os.path.join(HERE, "sql")
DB_PATH = os.path.join(HERE, "oda.duckdb")

SQL_FILES = [
    "00_schema.sql",
    "01_load.sql",
    "02_transform.sql",
    "03_analysis.sql",
    "99_export.sql",
]

# Each golden output: the generated file under out/ diffed against expected/.
OUTPUTS = [
    "mart_usage_monthly.csv",
    "mart_usage_by_dataset.csv",
]


def read_rows(path):
    with open(path, "r", encoding="utf-8", newline="") as handle:
        return handle.read().splitlines()


def verify_one(name):
    out_path = os.path.join(HERE, "out", name)
    expected_path = os.path.join(HERE, "expected", name)
    if not os.path.exists(out_path):
        print("FAIL: out/{} does not exist. Run: python run.py".format(name))
        return False
    if not os.path.exists(expected_path):
        print("FAIL: expected/{} does not exist.".format(name))
        return False

    actual = read_rows(out_path)
    expected = read_rows(expected_path)

    if actual == expected:
        print("PASS: out/{} matches expected/ ({} rows).".format(
            name, max(len(actual) - 1, 0)))
        return True

    print("FAIL: out/{} and expected/ differ.".format(name))
    print("  expected {} lines, got {} lines.".format(len(expected), len(actual)))
    limit = max(len(actual), len(expected))
    shown = 0
    for i in range(limit):
        a = actual[i] if i < len(actual) else "<missing>"
        e = expected[i] if i < len(expected) else "<missing>"
        if a != e:
            print("  line {}:".format(i + 1))
            print("    expected: {}".format(e))
            print("    actual:   {}".format(a))
            shown += 1
            if shown >= 5:
                print("  ... (further differences suppressed)")
                break
    return False


def verify():
    """Compare every out/ file to its expected/ twin. True only if all match."""
    return all([verify_one(name) for name in OUTPUTS])


def build():
    """Run the SQL files in order, then print the headline the SQL produced."""
    os.makedirs(os.path.join(HERE, "out"), exist_ok=True)
    os.makedirs(os.path.join(HERE, "bi", "exports"), exist_ok=True)
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)

    con = duckdb.connect(DB_PATH)
    try:
        for name in SQL_FILES:
            path = os.path.join(SQL_DIR, name)
            with open(path, "r", encoding="utf-8") as handle:
                con.execute(handle.read())
            print("ran {}".format(name))

        print("")
        for (line,) in con.execute("SELECT line FROM headline ORDER BY ord").fetchall():
            print(line)
        print("")
    finally:
        con.close()


def print_table(columns, rows):
    """Render an aligned ASCII table. Plain ASCII prints cleanly on any console,
    including the default Windows code page. Numeric columns are right-aligned."""
    cells = [["" if v is None else str(v) for v in row] for row in rows]

    def is_number(text):
        if text == "":
            return True
        try:
            float(text)
            return True
        except ValueError:
            return False

    numeric = [all(is_number(row[i]) for row in cells) for i in range(len(columns))]
    widths = [len(columns[i]) for i in range(len(columns))]
    for row in cells:
        for i, text in enumerate(row):
            widths[i] = max(widths[i], len(text))

    def line(values):
        parts = []
        for i, text in enumerate(values):
            parts.append(text.rjust(widths[i]) if numeric[i] else text.ljust(widths[i]))
        return "  ".join(parts)

    print(line(columns))
    print("  ".join("-" * w for w in widths))
    for row in cells:
        print(line(row))


def show():
    """Print the result as formatted tables. Read-only, no logic: these are
    display-only projections of columns the SQL already produced, so all of the
    aggregation and ranking still lives entirely in sql/."""
    monthly = os.path.join(HERE, "out", "mart_usage_monthly.csv")
    by_dataset = os.path.join(HERE, "out", "mart_usage_by_dataset.csv")
    if not os.path.exists(monthly):
        monthly = os.path.join(HERE, "expected", "mart_usage_monthly.csv")
    if not os.path.exists(by_dataset):
        by_dataset = os.path.join(HERE, "expected", "mart_usage_by_dataset.csv")
    if not os.path.exists(monthly) or not os.path.exists(by_dataset):
        print("Nothing to show yet. Run: python run.py")
        return

    con = duckdb.connect()
    try:
        con.register("monthly", con.sql(
            "SELECT * FROM read_csv('{}', header = true)".format(monthly.replace("\\", "/"))))
        con.register("by_dataset", con.sql(
            "SELECT * FROM read_csv('{}', header = true)".format(by_dataset.replace("\\", "/"))))

        print("\nTop 20 datasets by total usage:\n")
        top = con.sql(
            "SELECT usage_rank, dataset, total_usage, first_month, last_month "
            "FROM by_dataset ORDER BY total_usage DESC, dataset LIMIT 20")
        print_table(top.columns, top.fetchall())

        print("\nMonthly usage series (last 12 months):\n")
        recent = con.sql(
            "SELECT month_start, year, total_usage, distinct_datasets "
            "FROM monthly ORDER BY month_start DESC LIMIT 12")
        # Re-sort ascending for display so the series reads oldest to newest.
        recent = con.sql(
            "SELECT month_start, year, total_usage, distinct_datasets FROM ("
            "  SELECT month_start, year, total_usage, distinct_datasets "
            "  FROM monthly ORDER BY month_start DESC LIMIT 12"
            ") ORDER BY month_start")
        print_table(recent.columns, recent.fetchall())
        print("")
    finally:
        con.close()


def main():
    args = sys.argv[1:]

    if args and args[0] == "verify":
        sys.exit(0 if verify() else 1)

    if args and args[0] == "show":
        show()
        sys.exit(0)

    if args:
        print("unknown argument: {}. Use no argument, 'verify', or 'show'.".format(args[0]))
        sys.exit(2)

    build()
    sys.exit(0 if verify() else 1)


if __name__ == "__main__":
    main()
