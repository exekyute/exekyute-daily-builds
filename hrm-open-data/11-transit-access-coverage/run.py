"""Thin driver for the transit access coverage pipeline.

All analytical logic lives in sql/. This file only executes the SQL files in
order (00 to 99), copies the two frozen marts into bi/exports/, and diffs the
generated output against the golden copies in expected/. The SQL writes three
files: the per-stop mart, the per-lot park and ride mart, and the coverage
summary.

  python run.py            run the pipeline, then verify against expected/
  python run.py verify     golden diff only
  python run.py show       print the coverage summary and the park and ride lots
"""

import csv
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))

SQL_FILES = [
    "00_schema.sql",
    "01_load.sql",
    "02_transform.sql",
    "03_analysis.sql",
    "99_export.sql",
]

OUT_DIR = os.path.join(HERE, "out")
EXPECTED_DIR = os.path.join(HERE, "expected")
STOPS_CSV = os.path.join(OUT_DIR, "mart_stops.csv")
PARKRIDE_CSV = os.path.join(OUT_DIR, "mart_parkride.csv")
SUMMARY_CSV = os.path.join(OUT_DIR, "access_summary.csv")
BI_DIR = os.path.join(HERE, "bi", "exports")
BI_MARTS = ["mart_stops.csv", "mart_parkride.csv"]


def run_pipeline():
    import duckdb

    os.chdir(HERE)  # SQL files use paths relative to this folder
    os.makedirs(OUT_DIR, exist_ok=True)
    con = duckdb.connect()
    try:
        for name in SQL_FILES:
            path = os.path.join(HERE, "sql", name)
            with open(path, "r", encoding="utf-8") as f:
                con.execute(f.read())
            print("ran sql/" + name)
        print("")
        for (line,) in con.execute(
                "SELECT line FROM headline ORDER BY ord").fetchall():
            print(line)
        print("")
    finally:
        con.close()

    os.makedirs(BI_DIR, exist_ok=True)
    for name in BI_MARTS:
        shutil.copyfile(os.path.join(OUT_DIR, name), os.path.join(BI_DIR, name))
    print("copied marts to bi/exports/ (%s)" % ", ".join(BI_MARTS))


def verify():
    failures = 0
    checked = 0
    for name in sorted(os.listdir(EXPECTED_DIR)):
        if not name.endswith(".csv"):
            continue
        exp_path = os.path.join(EXPECTED_DIR, name)
        got_path = os.path.join(OUT_DIR, name)
        if not os.path.exists(got_path):
            print("FAIL: out/%s is missing (run: python run.py)" % name)
            return 1
        with open(exp_path, "r", encoding="utf-8") as f:
            exp = f.read().splitlines()
        with open(got_path, "r", encoding="utf-8") as f:
            got = f.read().splitlines()
        checked += 1
        for i in range(max(len(exp), len(got))):
            e = exp[i] if i < len(exp) else "<missing line>"
            g = got[i] if i < len(got) else "<missing line>"
            if e != g:
                print("FAIL: %s line %d" % (name, i + 1))
                print("  expected: " + e)
                print("  got:      " + g)
                failures += 1
                break
    if checked == 0:
        print("FAIL: expected/ holds no golden files to compare against")
        return 1
    if failures == 0:
        print("PASS: %d file(s) match expected/ row for row" % checked)
        return 0
    return 1


def print_table(header, rows):
    """Aligned plain-ASCII table. Numeric columns right-align. No box-drawing
    characters, so it prints cleanly on the default Windows code page."""
    cells = [[("" if c is None else str(c)) for c in r] for r in rows]

    def is_num(t):
        if t == "":
            return True
        try:
            float(t)
            return True
        except ValueError:
            return False

    numeric = [all(is_num(r[i]) for r in cells) for i in range(len(header))]
    widths = [len(h) for h in header]
    for r in cells:
        for i, t in enumerate(r):
            widths[i] = max(widths[i], len(t))

    def line(vals):
        return "  ".join(
            (t.rjust(widths[i]) if numeric[i] else t.ljust(widths[i]))
            for i, t in enumerate(vals))

    print(line(header))
    print("  ".join("-" * w for w in widths))
    for r in cells:
        print(line(r))


def read_csv_rows(path):
    with open(path, "r", encoding="utf-8", newline="") as f:
        rows = list(csv.reader(f))
    return rows[0], rows[1:]


def show():
    summary_src = SUMMARY_CSV if os.path.exists(SUMMARY_CSV) \
        else os.path.join(EXPECTED_DIR, "access_summary.csv")
    parkride_src = PARKRIDE_CSV if os.path.exists(PARKRIDE_CSV) \
        else os.path.join(EXPECTED_DIR, "mart_parkride.csv")
    if not os.path.exists(summary_src):
        print("Nothing to show yet. Run: python run.py")
        return 1

    # The coverage summary is one wide row; print it tall (metric, value) so it
    # reads cleanly in a terminal. This is a display reshape of columns the SQL
    # already produced, not new logic.
    header, rows = read_csv_rows(summary_src)
    print("Transit access coverage summary")
    print("")
    print_table(["metric", "value"], list(zip(header, rows[0])))

    print("")
    print("Park and ride lots (name and posted capacity)")
    print("")
    ph, prows = read_csv_rows(parkride_src)
    name_i = ph.index("name")
    cap_i = ph.index("capacity")
    print_table(["name", "capacity"], [[r[name_i], r[cap_i]] for r in prows])
    print("")
    return 0


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "run"
    if mode == "verify":
        sys.exit(verify())
    if mode == "show":
        sys.exit(show())
    if mode == "run":
        run_pipeline()
        sys.exit(verify())
    print("usage: python run.py [verify|show]")
    sys.exit(2)


if __name__ == "__main__":
    main()
