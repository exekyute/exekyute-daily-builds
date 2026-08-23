"""Thin driver for the protected-areas land accounting. No business logic
here: every rule lives in sql/, this file only sequences the SQL, copies the
BI mart into bi/exports/, and diffs out/ against the golden expected/.

Commands:
    python run.py            run the SQL end to end, then verify
    python run.py verify     golden diff only
    python run.py show       print hectares by designation
"""

import csv
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SQL_FILES = [
    "sql/00_schema.sql",
    "sql/01_load.sql",
    "sql/02_transform.sql",
    "sql/03_analysis.sql",
    "sql/99_export.sql",
]
OUT_CSV = os.path.join(HERE, "out", "protected_areas.csv")
EXPECTED_CSV = os.path.join(HERE, "expected", "protected_areas.csv")
OUT_MART = os.path.join(HERE, "out", "mart_protected.csv")
BI_MART = os.path.join(HERE, "bi", "exports", "mart_protected.csv")


def run_sql():
    import duckdb

    os.chdir(HERE)
    os.makedirs(os.path.join(HERE, "out"), exist_ok=True)
    con = duckdb.connect()
    for rel in SQL_FILES:
        path = os.path.join(HERE, rel)
        with open(path, "r", encoding="utf-8") as f:
            con.execute(f.read())
        print(f"ran {rel}")
    con.close()
    os.makedirs(os.path.dirname(BI_MART), exist_ok=True)
    shutil.copyfile(OUT_MART, BI_MART)
    print("copied out/mart_protected.csv -> bi/exports/mart_protected.csv")


def verify():
    if not os.path.exists(OUT_CSV):
        print("out/protected_areas.csv not found; run `python run.py` first")
        return 1
    if not os.path.exists(EXPECTED_CSV):
        print("expected/protected_areas.csv not found; no golden to verify against")
        return 1
    with open(OUT_CSV, "r", encoding="utf-8", newline="") as f:
        got = f.read().splitlines()
    with open(EXPECTED_CSV, "r", encoding="utf-8", newline="") as f:
        want = f.read().splitlines()
    for i, (g, w) in enumerate(zip(got, want), start=1):
        if g != w:
            print(f"FAIL: first mismatch at line {i}")
            print(f"  expected: {w}")
            print(f"  got:      {g}")
            return 1
    if len(got) != len(want):
        print(f"FAIL: line count differs (expected {len(want)}, got {len(got)})")
        return 1
    print(f"PASS: out/protected_areas.csv matches expected/protected_areas.csv "
          f"({len(got)} lines)")
    return 0


def show():
    if not os.path.exists(OUT_CSV):
        print("out/protected_areas.csv not found; run `python run.py` first")
        return 1
    with open(OUT_CSV, "r", encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))

    def num(v):
        return f"{float(v):,.2f}" if v else ""

    def count(v):
        return f"{int(v):,}" if v else ""

    print()
    print("Protected land, headline figures")
    print("-" * 72)
    for r in rows:
        if r["section"] == "summary":
            label = r["measure"].replace("_", " ")
            value = num(r["hectares"]) or count(r["records"])
            share = f"{r['share_pct']}%" if r["share_pct"] else ""
            print(f"  {label:<38} {value:>18} {share:>10}")
    print()

    print("Hectares by designation type")
    print("-" * 88)
    print(f"  {'#':>3} {'designation':<48} {'records':>8} "
          f"{'hectares':>14} {'share':>9}")
    print("-" * 88)
    for r in rows:
        if r["section"] == "by_designation":
            print(f"  {r['rank']:>3} {r['designation']:<48} "
                  f"{count(r['records']):>8} {num(r['hectares']):>14} "
                  f"{r['share_pct'] + '%':>9}")
    print("-" * 88)
    for r in rows:
        if r["section"] == "totals_tie" and r["measure"] == "sum_by_designation":
            print(f"  {'':>3} {'total (ties to the grand total)':<48} "
                  f"{count(r['records']):>8} {num(r['hectares']):>14} "
                  f"{r['share_pct'] + '%':>9}")
    print()
    return 0


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "run"
    if cmd == "run":
        run_sql()
        sys.exit(verify())
    elif cmd == "verify":
        sys.exit(verify())
    elif cmd == "show":
        sys.exit(show())
    else:
        print(__doc__)
        sys.exit(2)


if __name__ == "__main__":
    main()
