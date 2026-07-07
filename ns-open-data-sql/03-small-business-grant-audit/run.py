#!/usr/bin/env python3
"""Thin driver for the small-business grant audit.

All analytical logic lives in the sql/ files. This script only connects DuckDB,
runs each sql file in order, then checks the generated output against the golden
copy in expected/. It holds no aggregation or business rules of its own.

    python run.py          run the sql end to end, then verify the golden diff
    python run.py verify    re-run only the out-vs-expected diff
"""

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SQL_DIR = HERE / "sql"
OUT_FILE = HERE / "out" / "grants_by_type_year.csv"
EXPECTED_FILE = HERE / "expected" / "grants_by_type_year.csv"


def build():
    """Run every sql file (00 to 99) in order against a fresh DuckDB."""
    import duckdb

    (HERE / "out").mkdir(exist_ok=True)
    con = duckdb.connect()
    try:
        for sql_file in sorted(SQL_DIR.glob("*.sql")):
            con.execute(sql_file.read_text(encoding="utf-8"))
            print(f"ran {sql_file.name}")
    finally:
        con.close()


def verify():
    """Compare out/ against expected/ line for line. PASS only if identical."""
    if not OUT_FILE.exists():
        print(f"FAIL: {OUT_FILE.name} was not generated")
        return 1
    if not EXPECTED_FILE.exists():
        print(f"FAIL: expected/{EXPECTED_FILE.name} is missing")
        return 1

    got = OUT_FILE.read_text(encoding="utf-8").splitlines()
    want = EXPECTED_FILE.read_text(encoding="utf-8").splitlines()

    if got == want:
        print(f"PASS: out/{OUT_FILE.name} matches expected/{EXPECTED_FILE.name} ({len(got)} lines)")
        return 0

    print("FAIL: out/ differs from expected/")
    if len(got) != len(want):
        print(f"  line count: out has {len(got)}, expected has {len(want)}")
    for i, (g, w) in enumerate(zip(got, want), start=1):
        if g != w:
            print(f"  first difference at line {i}:")
            print(f"    out:      {g}")
            print(f"    expected: {w}")
            break
    return 1


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "run"
    if mode == "verify":
        return verify()
    if mode == "run":
        build()
        return verify()
    print(f"unknown mode: {mode!r}. Use 'python run.py' or 'python run.py verify'.")
    return 2


if __name__ == "__main__":
    sys.exit(main())
