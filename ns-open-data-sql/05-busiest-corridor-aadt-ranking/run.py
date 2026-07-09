#!/usr/bin/env python3
"""Thin driver for the busiest-corridor AADT ranking.

All analytical logic lives in the sql/ files. This script only executes each SQL
file in order (00 through 99) and then compares the generated out/ file to the
golden expected/ file. It holds no ranking or business logic of its own.

Usage:
    python run.py            run the SQL end to end, then verify against expected/
    python run.py verify     re-run only the out-vs-expected comparison
"""
import os
import sys

import duckdb

HERE = os.path.dirname(os.path.abspath(__file__))
SQL_DIR = os.path.join(HERE, "sql")
OUT_FILE = os.path.join(HERE, "out", "corridor_ranking.csv")
EXPECTED_FILE = os.path.join(HERE, "expected", "corridor_ranking.csv")

SQL_FILES = [
    "00_schema.sql",
    "01_load.sql",
    "02_transform.sql",
    "03_analysis.sql",
    "99_export.sql",
]


def build():
    """Run each SQL file in order against a fresh in-memory database."""
    os.makedirs(os.path.join(HERE, "out"), exist_ok=True)
    # SQL paths are relative (data/raw/..., out/...), so run from this folder.
    os.chdir(HERE)
    con = duckdb.connect()
    try:
        for name in SQL_FILES:
            with open(os.path.join(SQL_DIR, name), "r", encoding="utf-8") as handle:
                con.execute(handle.read())
            print("ran " + name)
    finally:
        con.close()


def read_lines(path):
    with open(path, "r", encoding="utf-8", newline="") as handle:
        return handle.read().splitlines()


def verify():
    """Compare out/ to expected/ row for row. Return 0 on match, 1 otherwise."""
    if not os.path.exists(OUT_FILE):
        print("FAIL: out/corridor_ranking.csv is missing; run 'python run.py' first")
        return 1
    if not os.path.exists(EXPECTED_FILE):
        print("FAIL: expected/corridor_ranking.csv is missing")
        return 1

    out = read_lines(OUT_FILE)
    expected = read_lines(EXPECTED_FILE)

    if out == expected:
        print("PASS: out/corridor_ranking.csv matches expected/ (" + str(len(out)) + " lines)")
        return 0

    print("FAIL: out/corridor_ranking.csv differs from expected/corridor_ranking.csv")
    if len(out) != len(expected):
        print("  line count: out=" + str(len(out)) + " expected=" + str(len(expected)))
    shown = 0
    for i in range(min(len(out), len(expected))):
        if out[i] != expected[i]:
            print("  first difference at line " + str(i + 1) + ":")
            print("    out:      " + out[i])
            print("    expected: " + expected[i])
            shown += 1
            if shown >= 5:
                break
    return 1


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "run"
    if mode == "verify":
        sys.exit(verify())
    if mode != "run":
        print("usage: python run.py [verify]")
        sys.exit(2)
    build()
    sys.exit(verify())


if __name__ == "__main__":
    main()
