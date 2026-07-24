"""Thin driver for the HRM municipal-building-energy pipeline.

This file holds no analytical logic. It executes the SQL files in order (00 to
99), which do all of the loading, cleaning, aggregating, and exporting, then it
diffs the three generated golden results against the golden copies in expected/.
The SQL also writes the frozen BI mart under bi/exports/.

Usage:
    python run.py            run the SQL end to end, then verify out vs expected
    python run.py verify     re-run only the out-vs-expected diff
    python run.py show       print the results as aligned tables in the terminal
"""

import os
import sys

import duckdb

HERE = os.path.dirname(os.path.abspath(__file__))
SQL_DIR = os.path.join(HERE, "sql")
DB_PATH = os.path.join(HERE, "energy.duckdb")
OUT_DIR = os.path.join(HERE, "out")
EXPECTED_DIR = os.path.join(HERE, "expected")

SQL_FILES = [
    "00_schema.sql",
    "01_load.sql",
    "02_transform.sql",
    "03_analysis.sql",
    "99_export.sql",
]

# The golden results verified row for row. The mart under bi/exports/ is a
# deterministic export of the same tables and is not diffed here.
GOLDENS = [
    "cost_by_fuel.csv",
    "costliest_buildings.csv",
    "cost_per_unit_by_fuel.csv",
]


def read_rows(path):
    with open(path, "r", encoding="utf-8", newline="") as handle:
        return handle.read().splitlines()


def verify_one(name):
    """Diff out/name against expected/name. Returns True on an exact match."""
    out_path = os.path.join(OUT_DIR, name)
    exp_path = os.path.join(EXPECTED_DIR, name)
    if not os.path.exists(out_path):
        print("FAIL: out/{} does not exist. Run: python run.py".format(name))
        return False
    if not os.path.exists(exp_path):
        print("FAIL: expected/{} does not exist.".format(name))
        return False

    actual = read_rows(out_path)
    expected = read_rows(exp_path)

    if actual == expected:
        print("PASS: out/{} matches expected/ ({} rows).".format(
            name, max(len(actual) - 1, 0)))
        return True

    print("FAIL: out/{} and expected/ differ.".format(name))
    print("  expected {} lines, got {} lines.".format(len(expected), len(actual)))
    shown = 0
    for i in range(max(len(actual), len(expected))):
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
    """Verify every golden file. Returns True only if all match."""
    results = [verify_one(name) for name in GOLDENS]
    ok = all(results)
    print("")
    print("PASS: all {} golden results match.".format(len(GOLDENS)) if ok
          else "FAIL: at least one golden result differs.")
    return ok


def build():
    """Run the SQL files in order, then print the headline the SQL produced."""
    os.makedirs(OUT_DIR, exist_ok=True)
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
    """Print the results as formatted tables. Read-only, no logic: these are
    display-only projections of columns the SQL already computed, so the
    aggregation still lives entirely in sql/."""
    src_dir = OUT_DIR if os.path.exists(os.path.join(OUT_DIR, GOLDENS[0])) else EXPECTED_DIR
    if not os.path.exists(os.path.join(src_dir, GOLDENS[0])):
        print("Nothing to show yet. Run: python run.py")
        return

    con = duckdb.connect()
    try:
        def load(name):
            # Read every column as text so the table prints the exact fixed-decimal
            # strings the SQL wrote, rather than re-inferred floats. This keeps show
            # a faithful, logic-free view of the committed result.
            path = os.path.join(src_dir, name).replace("\\", "/")
            return con.sql(
                "SELECT * FROM read_csv('{}', header = true, all_varchar = true)".format(path))

        print("\nTotal cost by fuel (costliest fuel first):\n")
        fuel = load("cost_by_fuel.csv").project(
            "energy_type, unit_of_measure, meter_readings, building_count, "
            "consumption, cost, cost_share, fuel_rank").order("CAST(fuel_rank AS INTEGER), energy_type")
        print_table(fuel.columns, fuel.fetchall())

        print("\nCost per unit by fuel (units differ across fuels, so read each row on its own):\n")
        cpu = load("cost_per_unit_by_fuel.csv").order("energy_type")
        print_table(cpu.columns, cpu.fetchall())

        print("\nCostliest buildings by total cost (15 highest of 160; full list in "
              "out/costliest_buildings.csv):\n")
        bld = load("costliest_buildings.csv").order(
            "TRY_CAST(cost AS DOUBLE) DESC, building_name").limit(15)
        print_table(bld.columns, bld.fetchall())
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
