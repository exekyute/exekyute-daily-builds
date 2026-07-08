#!/usr/bin/env python3
"""Thin driver for the hatchery stocking summary.

All analytical logic lives in the SQL files under sql/. This script only:
  1. runs the SQL files in order (00 -> 99), which loads the snapshot,
     cleans it, builds the summary, and writes out/stocking_summary.csv; then
  2. checks that file against the golden copy in expected/.

Usage:
  python run.py          run the SQL end to end, then verify
  python run.py verify   re-run the golden diff only
"""
import os
import sys

import duckdb

HERE = os.path.dirname(os.path.abspath(__file__))
SQL_DIR = os.path.join(HERE, "sql")
OUT_FILE = os.path.join(HERE, "out", "stocking_summary.csv")
EXPECTED_FILE = os.path.join(HERE, "expected", "stocking_summary.csv")

SQL_STEPS = [
    "00_schema.sql",
    "01_load.sql",
    "02_transform.sql",
    "03_analysis.sql",
    "99_export.sql",
]


def build():
    """Run every SQL step in order against a fresh in-memory database."""
    os.makedirs(os.path.join(HERE, "out"), exist_ok=True)
    con = duckdb.connect()
    try:
        for step in SQL_STEPS:
            with open(os.path.join(SQL_DIR, step), "r", encoding="utf-8") as fh:
                con.execute(fh.read())
    finally:
        con.close()


def verify():
    """Compare out/ to expected/ line for line."""
    if not os.path.exists(OUT_FILE):
        print("FAIL: out/stocking_summary.csv is missing. Run: python run.py")
        return 1
    if not os.path.exists(EXPECTED_FILE):
        print("FAIL: expected/stocking_summary.csv is missing.")
        return 1
    with open(OUT_FILE, "r", encoding="utf-8", newline="") as fh:
        got = fh.read().splitlines()
    with open(EXPECTED_FILE, "r", encoding="utf-8", newline="") as fh:
        want = fh.read().splitlines()
    if got == want:
        print("PASS: out/stocking_summary.csv matches expected/ (%d lines)." % len(got))
        return 0
    print("FAIL: out/stocking_summary.csv does not match expected/.")
    if len(got) != len(want):
        print("  line count: out=%d expected=%d" % (len(got), len(want)))
    for i in range(min(len(got), len(want))):
        if got[i] != want[i]:
            print("  first differing line (%d):" % (i + 1))
            print("    expected: " + want[i])
            print("    out:      " + got[i])
            break
    return 1


def main():
    # Run from the project folder so the relative paths in the SQL resolve,
    # no matter where python was invoked from.
    os.chdir(HERE)
    args = sys.argv[1:]
    if args and args[0] == "verify":
        return verify()
    build()
    return verify()


if __name__ == "__main__":
    sys.exit(main())
