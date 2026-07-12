#!/usr/bin/env python3
"""Thin driver for the procurement spend Pareto build.

All analytical logic lives in the sql/ files. This driver only connects DuckDB, runs the
sql/ files in order (00 through 99) to load, transform, analyze, and export the result,
then verifies out/vendor_pareto.csv against the committed expected/vendor_pareto.csv
row for row.

Usage:
    python run.py          run the SQL end to end, then verify
    python run.py verify   re-run only the out-vs-expected diff
"""

import os
import sys
from pathlib import Path

import duckdb

BASE = Path(__file__).resolve().parent
OUT = BASE / "out" / "vendor_pareto.csv"
EXPECTED = BASE / "expected" / "vendor_pareto.csv"


def run_sql():
    """Execute every sql/ file in filename order against a fresh DuckDB connection."""
    os.chdir(BASE)
    (BASE / "out").mkdir(exist_ok=True)
    con = duckdb.connect()
    try:
        for path in sorted((BASE / "sql").glob("*.sql")):
            con.execute(path.read_text(encoding="utf-8"))
    finally:
        con.close()


def _rows(path):
    return Path(path).read_text(encoding="utf-8").splitlines()


def verify():
    """Compare out/ to expected/ line for line. Print PASS, or the first difference."""
    if not OUT.exists():
        print("FAIL: out/vendor_pareto.csv does not exist. Run `python run.py` first.")
        return 1
    if not EXPECTED.exists():
        print("FAIL: expected/vendor_pareto.csv does not exist.")
        return 1

    got = _rows(OUT)
    exp = _rows(EXPECTED)
    if got == exp:
        print(f"PASS: out/vendor_pareto.csv matches expected/ ({len(got) - 1} vendor rows).")
        return 0

    print("FAIL: out/vendor_pareto.csv differs from expected/vendor_pareto.csv.")
    if len(got) != len(exp):
        print(f"  row count: out={len(got)} expected={len(exp)}")
    for i, (a, b) in enumerate(zip(exp, got), start=1):
        if a != b:
            print(f"  first differing line ({i}):")
            print(f"    expected: {a}")
            print(f"    out:      {b}")
            break
    return 1


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "verify":
        sys.exit(verify())
    run_sql()
    sys.exit(verify())


if __name__ == "__main__":
    main()
