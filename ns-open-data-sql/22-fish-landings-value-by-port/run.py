"""Thin driver for the fish landings value build. No business logic here:
every rule lives in sql/, this file only sequences the SQL, copies the BI
mart into bi/exports/, and diffs out/ against the golden expected/.

Commands:
    python run.py            run the SQL end to end, then verify
    python run.py verify     golden diff only
    python run.py show       print the headline table
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
OUT_CSV = os.path.join(HERE, "out", "fish_landings.csv")
EXPECTED_CSV = os.path.join(HERE, "expected", "fish_landings.csv")
OUT_MART = os.path.join(HERE, "out", "mart_fish_landings.csv")
BI_MART = os.path.join(HERE, "bi", "exports", "mart_fish_landings.csv")


def run_sql():
    import duckdb

    os.chdir(HERE)
    os.makedirs(os.path.join(HERE, "out"), exist_ok=True)
    con = duckdb.connect()
    for rel in SQL_FILES:
        with open(os.path.join(HERE, rel), "r", encoding="utf-8") as f:
            con.execute(f.read())
        print(f"ran {rel}")
    con.close()
    os.makedirs(os.path.dirname(BI_MART), exist_ok=True)
    shutil.copyfile(OUT_MART, BI_MART)
    print("copied out/mart_fish_landings.csv -> bi/exports/mart_fish_landings.csv")


def verify():
    if not os.path.exists(OUT_CSV):
        print("out/fish_landings.csv not found; run `python run.py` first")
        return 1
    if not os.path.exists(EXPECTED_CSV):
        print("expected/fish_landings.csv not found; no golden to verify against")
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
    print(f"PASS: out/fish_landings.csv matches expected/fish_landings.csv "
          f"({len(got)} lines)")
    return 0


def show():
    if not os.path.exists(OUT_CSV):
        print("out/fish_landings.csv not found; run `python run.py` first")
        return 1
    with open(OUT_CSV, "r", encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))

    def num(v, dp=2):
        return f"{float(v):,.{dp}f}" if v else ""

    def pct(v):
        return f"{v}%" if v else ""

    print()
    print("Landed value summary, 2017 to 2024")
    print("-" * 96)
    print(f"  {'measure':<26} {'records':>8} {'kilograms':>20} "
          f"{'dollars':>20} {'share':>8}")
    print("-" * 96)
    for r in rows:
        if r["section"] in ("summary", "totals_tie"):
            label = r["measure"].replace("_", " ")
            if r["section"] == "totals_tie":
                label = label + " (ties)"
            # The published county figure sits in its own column, and the
            # figure next to it is the port-level shortfall, not a share.
            money = r["dollars"] or r["published_dollars"]
            trail = r["share_pct"] or r["delta_pct"]
            print(f"  {label:<26} {r['records']:>8} {num(r['kgs']):>20} "
                  f"{num(money):>20} {pct(trail):>8}")
    print("  (the last figure on the published row is how far the port rows")
    print("   fall short of the province's own county total, not a share)")
    print()

    print("Rows accounted for")
    print("-" * 96)
    for r in rows:
        if r["section"] == "row_classes":
            label = r["measure"].replace("_", " ")
            print(f"  {label:<30} {r['records']:>8}")
    print()

    print(f"Top ports by landed value")
    print("-" * 108)
    print(f"  {'#':>3} {'port':<30} {'county':<14} {'kilograms':>18} "
          f"{'dollars':>18} {'$/kg':>8} {'share':>7} {'cum':>7}")
    print("-" * 108)
    for r in rows:
        if r["section"] == "top_ports":
            print(f"  {r['rank']:>3} {r['port']:<30} {r['county']:<14} "
                  f"{num(r['kgs']):>18} {num(r['dollars']):>18} "
                  f"{num(r['price_per_kg'], 4):>8} "
                  f"{pct(r['share_pct']):>7} {pct(r['cumulative_share_pct']):>7}")
    print()

    print("Landed value by year")
    print("-" * 96)
    print(f"  {'year':<6} {'records':>8} {'kilograms':>20} {'dollars':>20} "
          f"{'$/kg':>9} {'YoY %':>9}")
    print("-" * 96)
    for r in rows:
        if r["section"] == "by_year":
            print(f"  {r['year']:<6} {r['records']:>8} {num(r['kgs']):>20} "
                  f"{num(r['dollars']):>20} {num(r['price_per_kg'], 4):>9} "
                  f"{pct(r['delta_pct']):>9}")
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
