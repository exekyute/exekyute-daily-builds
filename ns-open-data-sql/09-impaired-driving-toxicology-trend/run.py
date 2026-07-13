"""Thin driver for the impaired-driving toxicology trend project.

This file holds no analytical logic. Every query lives in sql/. The driver only:
  - runs the SQL files in order (00 -> 99), which loads, transforms, analyses,
    and writes out/toxicology_trend.csv, then
  - compares that output against expected/toxicology_trend.csv, row for row.

Usage:
  python run.py          run the SQL end to end, then verify against expected/
  python run.py verify   re-run only the golden diff (no SQL, no rebuild)
"""

import glob
import os
import sys

import duckdb

# Resolve paths relative to this file so `python run.py` works from any location.
HERE = os.path.dirname(os.path.abspath(__file__))
SQL_DIR = os.path.join(HERE, "sql")
OUT_FILE = os.path.join(HERE, "out", "toxicology_trend.csv")
EXPECTED_FILE = os.path.join(HERE, "expected", "toxicology_trend.csv")


def run_sql():
    """Execute every sql/*.sql file in filename order against a fresh database."""
    os.chdir(HERE)  # so relative paths inside the SQL files resolve
    os.makedirs(os.path.join(HERE, "out"), exist_ok=True)
    con = duckdb.connect()
    for path in sorted(glob.glob(os.path.join(SQL_DIR, "*.sql"))):
        with open(path, encoding="utf-8") as f:
            con.execute(f.read())
        print("ran", os.path.basename(path))
    con.close()


def verify():
    """Compare out/ to expected/ line for line. Return True on an exact match."""
    if not os.path.exists(OUT_FILE):
        print("FAIL: out/toxicology_trend.csv was not produced. Run: python run.py")
        return False
    if not os.path.exists(EXPECTED_FILE):
        print("FAIL: expected/toxicology_trend.csv is missing.")
        return False

    with open(OUT_FILE, encoding="utf-8") as f:
        actual = f.read().splitlines()
    with open(EXPECTED_FILE, encoding="utf-8") as f:
        expected = f.read().splitlines()

    if actual == expected:
        print("PASS: out/toxicology_trend.csv matches expected/ (%d rows)" % (len(actual) - 1))
        return True

    print("FAIL: out/ does not match expected/. First differences:")
    for i in range(max(len(actual), len(expected))):
        a = actual[i] if i < len(actual) else "<missing>"
        e = expected[i] if i < len(expected) else "<missing>"
        if a != e:
            print("  line %d expected: %s" % (i + 1, e))
            print("  line %d actual:   %s" % (i + 1, a))
            break
    return False


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "run"
    if mode == "verify":
        ok = verify()
    elif mode == "run":
        run_sql()
        ok = verify()
    else:
        print("Unknown argument: %s. Use no argument, or 'verify'." % mode)
        ok = False
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
