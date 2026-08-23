"""Thin driver for the public-housing supply build. No business logic here:
every rule lives in sql/, this file only sequences the SQL, copies the BI
mart into bi/exports/, diffs out/ against the golden expected/, and prints
what the SQL already computed.

Commands:
    python run.py            run the SQL end to end, then verify
    python run.py verify     golden diff only
    python run.py show       print units by county and program type
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
OUT_CSV = os.path.join(HERE, "out", "housing_supply.csv")
EXPECTED_CSV = os.path.join(HERE, "expected", "housing_supply.csv")
OUT_MART = os.path.join(HERE, "out", "mart_housing.csv")
BI_MART = os.path.join(HERE, "bi", "exports", "mart_housing.csv")


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
    print("copied out/mart_housing.csv -> bi/exports/mart_housing.csv")


def verify():
    if not os.path.exists(OUT_CSV):
        print("out/housing_supply.csv not found; run `python run.py` first")
        return 1
    if not os.path.exists(EXPECTED_CSV):
        print("expected/housing_supply.csv not found; no golden to verify against")
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
    print(f"PASS: out/housing_supply.csv matches expected/housing_supply.csv "
          f"({len(got)} lines)")
    return 0


def show():
    if not os.path.exists(OUT_CSV):
        print("out/housing_supply.csv not found; run `python run.py` first")
        return 1
    with open(OUT_CSV, "r", encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))

    def num(v):
        return f"{int(v):,}" if v else ""

    def pct(v):
        return f"{v}%" if v else ""

    rule = "-" * 64

    for title, section in (("Summary", "summary"),
                           ("Row accounting", "exclusions"),
                           ("Reconciliation", "reconciliation")):
        print()
        print(title)
        print(rule)
        for r in rows:
            if r["section"] == section:
                label = r["measure"].replace("_", " ")
                county = f" ({r['county']})" if r["county"] else ""
                print(f"  {label + county:<42} {num(r['value']):>10} "
                      f"{pct(r['share_pct']):>8}")

    for title, section, key in (("Units by program type", "program_totals", "program_type"),
                                ("Units by county", "county_totals", "county")):
        print()
        print(title)
        print(rule)
        print(f"  {'#':>3} {key.replace('_', ' '):<24} {'properties':>12} "
              f"{'units':>10} {'share':>9}")
        print(rule)
        for r in rows:
            if r["section"] == section:
                print(f"  {r['rank']:>3} {r[key]:<24} "
                      f"{num(r['properties']):>12} {num(r['units']):>10} "
                      f"{pct(r['share_pct']):>9}")

    print()
    print("Units by county and program type")
    print(rule)
    print(f"  {'#':>3} {'county':<16} {'program':<10} {'properties':>10} "
          f"{'units':>8} {'share':>10}")
    print(rule)
    for r in rows:
        if r["section"] == "county_program":
            print(f"  {r['rank']:>3} {r['county']:<16} {r['program_type']:<10} "
                  f"{num(r['properties']):>10} {num(r['units']):>8} "
                  f"{pct(r['share_pct']):>10}")
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
