"""Thin driver for the Open Data catalogue freshness audit.

This file holds no analytical logic. It executes the SQL files in order (00 to
99), which do all of the loading, cleaning, bucketing, and exporting, then it
copies the BI mart into bi/exports/ and diffs the generated audit against the
golden copy in expected/.

Usage:
    python run.py            run the SQL end to end, then verify out vs expected
    python run.py verify     re-run only the out-vs-expected diff
    python run.py show       print the freshness summary as a table
"""

import os
import shutil
import sys

import duckdb

HERE = os.path.dirname(os.path.abspath(__file__))
SQL_DIR = os.path.join(HERE, "sql")
DB_PATH = os.path.join(HERE, "freshness.duckdb")
OUT_PATH = os.path.join(HERE, "out", "freshness_audit.csv")
MART_PATH = os.path.join(HERE, "out", "mart_freshness.csv")
BI_MART_PATH = os.path.join(HERE, "bi", "exports", "mart_freshness.csv")
EXPECTED_PATH = os.path.join(HERE, "expected", "freshness_audit.csv")

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
        print("FAIL: out/freshness_audit.csv does not exist. Run: python run.py")
        return False
    if not os.path.exists(EXPECTED_PATH):
        print("FAIL: expected/freshness_audit.csv does not exist.")
        return False

    actual = read_rows(OUT_PATH)
    expected = read_rows(EXPECTED_PATH)

    if actual == expected:
        print("PASS: out/freshness_audit.csv matches expected/ ({} rows).".format(
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
    """Run the SQL files in order, copy the BI mart, then print the headline
    the SQL produced."""
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

    os.makedirs(os.path.dirname(BI_MART_PATH), exist_ok=True)
    shutil.copyfile(MART_PATH, BI_MART_PATH)
    print("copied out/mart_freshness.csv to bi/exports/mart_freshness.csv")


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
    """Print the freshness summary as formatted tables. Read-only, no logic:
    these are display-only projections of rows the SQL already computed, so the
    bucketing and aggregation still live entirely in sql/."""
    src = OUT_PATH if os.path.exists(OUT_PATH) else EXPECTED_PATH
    if not os.path.exists(src):
        print("Nothing to show yet. Run: python run.py")
        return

    con = duckdb.connect()
    try:
        con.register(
            "result",
            con.sql("SELECT * FROM read_csv('{}', header = true, all_varchar = true)".format(
                src.replace("\\", "/"))))

        sections = [
            ("overall", "Portal-wide freshness (all audited assets):"),
            ("bucket_summary", "Assets by freshness bucket:"),
            ("by_category", "By category (share stale or dormant):"),
            ("by_owner", "By owner (share stale or dormant):"),
            ("worst_offenders", "Worst offenders (oldest public datasets):"),
        ]
        for key, title in sections:
            probe = con.sql(
                "SELECT * FROM result WHERE section = '{}' ORDER BY "
                "CAST(row_rank AS INTEGER)".format(key))
            rows = probe.fetchall()
            keep = [
                i for i, name in enumerate(probe.columns)
                if name not in ("section", "row_rank")
                and any(row[i] not in (None, "") for row in rows)
            ]
            print("\n" + title + "\n")
            print_table([probe.columns[i] for i in keep],
                        [[row[i] for i in keep] for row in rows])
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
