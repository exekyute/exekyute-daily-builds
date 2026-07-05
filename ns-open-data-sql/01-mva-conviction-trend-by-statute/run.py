"""Thin driver for the MVA conviction-trend pipeline.

This file holds no analytical logic. It executes the SQL files in order (00 to
99), which do all of the loading, transforming, ranking, and exporting, then it
diffs the generated output against the golden copy in expected/.

Usage:
    python run.py            run the SQL end to end, then verify out vs expected
    python run.py verify     re-run only the out-vs-expected diff
    python run.py show       print the ranked result as a table in the terminal
"""

import os
import sys

import duckdb

HERE = os.path.dirname(os.path.abspath(__file__))
SQL_DIR = os.path.join(HERE, "sql")
DB_PATH = os.path.join(HERE, "mva.duckdb")
OUT_PATH = os.path.join(HERE, "out", "convictions_ranked.csv")
EXPECTED_PATH = os.path.join(HERE, "expected", "convictions_ranked.csv")

SQL_FILES = [
    "00_schema.sql",
    "01_load.sql",
    "02_transform.sql",
    "03_analysis.sql",
    "99_export.sql",
]


def read_rows(path):
    with open(path, "r", encoding="utf-8", newline="") as handle:
        return handle.read().splitlines()


def verify():
    """Compare out/ to expected/ line for line. Returns True on an exact match."""
    if not os.path.exists(OUT_PATH):
        print("FAIL: out/convictions_ranked.csv does not exist. Run: python run.py")
        return False
    if not os.path.exists(EXPECTED_PATH):
        print("FAIL: expected/convictions_ranked.csv does not exist.")
        return False

    actual = read_rows(OUT_PATH)
    expected = read_rows(EXPECTED_PATH)

    if actual == expected:
        print("PASS: out/convictions_ranked.csv matches expected/ ({} rows).".format(
            max(len(actual) - 1, 0)))
        return True

    print("FAIL: out/ and expected/ differ.")
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


def build():
    """Run the SQL files in order, then print the headline the SQL produced."""
    os.makedirs(os.path.join(HERE, "out"), exist_ok=True)
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
    """Print the result as a formatted table. Read-only, no logic: these are
    display-only projections of columns the SQL already computed, so the ranking
    and aggregation still live entirely in sql/."""
    src = OUT_PATH if os.path.exists(OUT_PATH) else EXPECTED_PATH
    if not os.path.exists(src):
        print("Nothing to show yet. Run: python run.py")
        return

    con = duckdb.connect()
    try:
        con.register(
            "result",
            con.sql("SELECT * FROM read_csv('{}', header = true)".format(
                src.replace("\\", "/"))))

        print("\nRanked by trend over the window (fastest rising first):\n")
        summary = con.sql(
            "SELECT DISTINCT window_rank, window_trend, offence_statute, description, "
            "first_year, first_convictions, last_year, last_convictions, window_pct_change "
            "FROM result ORDER BY window_rank")
        print_table(summary.columns, summary.fetchall())

        print("\nYear by year (per-year rank and year-over-year move):\n")
        detail = con.sql(
            "SELECT window_rank, offence_statute, year_convicted, convictions, "
            "rank_in_year, yoy_change, yoy_pct_change "
            "FROM result ORDER BY window_rank, offence_statute, year_convicted")
        print_table(detail.columns, detail.fetchall())
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
