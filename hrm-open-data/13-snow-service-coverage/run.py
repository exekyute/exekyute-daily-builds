"""Thin driver for the snow service coverage pipeline.

All analytical logic lives in sql/. This file only executes the SQL files in
order (00 to 99), which load the three GeoJSON snapshots, clean them, roll them
up, and write the golden summary plus the three map layers. It then copies the
frozen summary into bi/exports/ for the dashboard and diffs the generated output
against the golden copy in expected/.

  python run.py            run the SQL end to end, then verify out vs expected
  python run.py verify     re-run only the golden diff
  python run.py show       print the coverage summary as an aligned table
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
SUMMARY_CSV = os.path.join(OUT_DIR, "coverage_summary.csv")
BI_SUMMARY_CSV = os.path.join(HERE, "bi", "exports", "summary.csv")


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

    os.makedirs(os.path.dirname(BI_SUMMARY_CSV), exist_ok=True)
    shutil.copyfile(SUMMARY_CSV, BI_SUMMARY_CSV)
    print("copied summary to bi/exports/summary.csv")


def verify():
    failures = 0
    checked = 0
    for name in sorted(os.listdir(EXPECTED_DIR)):
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
        print("PASS: %d file(s) match expected/ row for row (%d data rows)" % (
            checked, _data_rows()))
        return 0
    return 1


def _data_rows():
    if not os.path.exists(SUMMARY_CSV):
        return 0
    with open(SUMMARY_CSV, "r", encoding="utf-8") as f:
        return max(sum(1 for _ in f) - 1, 0)


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
    src = SUMMARY_CSV if os.path.exists(SUMMARY_CSV) \
        else os.path.join(EXPECTED_DIR, "coverage_summary.csv")
    if not os.path.exists(src):
        print("Nothing to show yet. Run: python run.py")
        return 1

    header, rows = read_csv_rows(src)
    labels = {
        "street_by_serve_by": "Street winter maintenance areas by servicing body",
        "sidewalk_by_machine": "Sidewalk winter maintenance areas by service zone",
        "ice_by_priority": "Ice-route length by priority (km)",
    }
    for section in ("street_by_serve_by", "sidewalk_by_machine", "ice_by_priority"):
        block = [r for r in rows if r[0] == section]
        if not block:
            continue
        print("")
        print(labels[section])
        print("")
        # drop the section column; it is constant within the block
        print_table(header[1:], [r[1:] for r in block])
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
