"""Thin driver for the co-op registry longevity pipeline.

All analytical logic lives in sql/. This script only executes the SQL
files in order, copies the Power BI mart into bi/exports/, and diffs the
result against the golden output. No business rules live here.

Usage:
    python run.py            # run the SQL end to end, then verify
    python run.py verify     # golden diff only
    python run.py show       # print the cohort survivorship table
"""

import csv
import os
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SQL_DIR = ROOT / "sql"
OUT_DIR = ROOT / "out"
OUT_CSV = OUT_DIR / "coop_longevity.csv"
MART_OUT = OUT_DIR / "mart_coop_longevity.csv"
MART_BI = ROOT / "bi" / "exports" / "mart_coop_longevity.csv"
EXPECTED_CSV = ROOT / "expected" / "coop_longevity.csv"

SQL_FILES = [
    "00_schema.sql",
    "01_load.sql",
    "02_transform.sql",
    "03_analysis.sql",
    "99_export.sql",
]


def run_pipeline():
    import duckdb

    os.chdir(ROOT)  # SQL files use paths relative to the project folder
    OUT_DIR.mkdir(exist_ok=True)
    con = duckdb.connect()
    for name in SQL_FILES:
        sql = (SQL_DIR / name).read_text(encoding="utf-8")
        con.execute(sql)
    con.close()
    MART_BI.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(MART_OUT, MART_BI)
    print(f"wrote {OUT_CSV.relative_to(ROOT)}")
    print(f"wrote {MART_BI.relative_to(ROOT)}")


def verify():
    if not OUT_CSV.exists():
        print(f"FAIL: {OUT_CSV.relative_to(ROOT)} not found; run `python run.py` first")
        return 1
    if not EXPECTED_CSV.exists():
        print(f"FAIL: {EXPECTED_CSV.relative_to(ROOT)} not found")
        return 1
    got = OUT_CSV.read_text(encoding="utf-8").splitlines()
    want = EXPECTED_CSV.read_text(encoding="utf-8").splitlines()
    for i, (g, w) in enumerate(zip(got, want), start=1):
        if g != w:
            print(f"FAIL: line {i} differs")
            print(f"  expected: {w}")
            print(f"  got:      {g}")
            return 1
    if len(got) != len(want):
        print(f"FAIL: line count differs (expected {len(want)}, got {len(got)})")
        return 1
    print(f"PASS ({len(got) - 1} data rows match expected/coop_longevity.csv)")
    return 0


def show():
    src = OUT_CSV if OUT_CSV.exists() else EXPECTED_CSV
    with open(src, newline="", encoding="utf-8") as f:
        rows = list(csv.reader(f))
    if not rows:
        print("no rows")
        return 1
    header, data = rows[0], rows[1:]
    widths = [len(h) for h in header]
    for row in data:
        for i, cell in enumerate(row):
            widths[i] = max(widths[i], len(cell))

    def is_numeric(col):
        vals = [r[col] for r in data if r[col] != ""]
        if not vals:
            return False
        try:
            for v in vals:
                float(v)
            return True
        except ValueError:
            return False

    numeric = [is_numeric(i) for i in range(len(header))]

    def fmt(row):
        cells = []
        for i, cell in enumerate(row):
            cells.append(cell.rjust(widths[i]) if numeric[i] else cell.ljust(widths[i]))
        return "  ".join(cells).rstrip()

    print(fmt(header))
    print("  ".join("-" * w for w in widths))
    for row in data:
        print(fmt(row))
    return 0


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "run"
    if mode == "run":
        run_pipeline()
        sys.exit(verify())
    elif mode == "verify":
        sys.exit(verify())
    elif mode == "show":
        sys.exit(show())
    else:
        print(f"unknown mode: {mode} (use run, verify, or show)")
        sys.exit(2)


if __name__ == "__main__":
    main()
