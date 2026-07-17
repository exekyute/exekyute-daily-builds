"""Thin driver for the 311 call service-levels pipeline.

This file holds no analytical logic. It executes the SQL files in order (00 to
99), which do all of the loading, cleaning, rolling up, and exporting, then it
diffs the generated golden against the committed copy in expected/.

Usage:
    python run.py            run the SQL end to end, then verify out vs expected
    python run.py verify     re-run only the out-vs-expected diff
    python run.py show       print the per-year summary and the monthly series
"""

import os
import sys

import duckdb

HERE = os.path.dirname(os.path.abspath(__file__))
SQL_DIR = os.path.join(HERE, "sql")
DB_PATH = os.path.join(HERE, "calls.duckdb")
OUT_PATH = os.path.join(HERE, "out", "monthly_service_levels.csv")
EXPECTED_PATH = os.path.join(HERE, "expected", "monthly_service_levels.csv")

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
        print("FAIL: out/monthly_service_levels.csv does not exist. Run: python run.py")
        return False
    if not os.path.exists(EXPECTED_PATH):
        print("FAIL: expected/monthly_service_levels.csv does not exist.")
        return False

    actual = read_rows(OUT_PATH)
    expected = read_rows(EXPECTED_PATH)

    if actual == expected:
        print("PASS: out/monthly_service_levels.csv matches expected/ ({} rows).".format(
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
    display-only projections of columns the SQL already computed, so the rollups
    still live entirely in sql/."""
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

        print("\nPer year (offered, handled, abandoned, and the year rates):\n")
        summary = con.sql(
            "SELECT DISTINCT year, year_offered, year_handled, year_abandoned, "
            "year_processed_in_ivr, year_total_talk_time, year_abandonment_rate, "
            "year_answer_rate "
            "FROM result ORDER BY year")
        print_table(summary.columns, summary.fetchall())

        print("\nBy month (offered vs handled vs abandoned, talk time, and rates):\n")
        detail = con.sql(
            "SELECT month_start, year, month, offered, handled, abandoned, "
            "processed_in_ivr, total_talk_time, abandonment_rate, answer_rate, "
            "avg_talk_time "
            "FROM result ORDER BY month_start")
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
