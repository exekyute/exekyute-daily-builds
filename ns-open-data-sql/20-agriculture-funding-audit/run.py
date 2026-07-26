"""Thin driver for the agriculture funding audit. No business logic here:
every rule lives in sql/, this file only sequences the SQL, copies the BI
mart into bi/exports/, and diffs out/ against the golden expected/.

Commands:
    python run.py            run the SQL end to end, then verify
    python run.py verify     golden diff only
    python run.py show       print the concentration summary and top recipients
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
OUT_CSV = os.path.join(HERE, "out", "funding_audit.csv")
EXPECTED_CSV = os.path.join(HERE, "expected", "funding_audit.csv")
OUT_MART = os.path.join(HERE, "out", "mart_funding_audit.csv")
BI_MART = os.path.join(HERE, "bi", "exports", "mart_funding_audit.csv")


def run_sql():
    import duckdb

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
    print("copied out/mart_funding_audit.csv -> bi/exports/mart_funding_audit.csv")


def verify():
    if not os.path.exists(OUT_CSV):
        print("out/funding_audit.csv not found; run `python run.py` first")
        return 1
    if not os.path.exists(EXPECTED_CSV):
        print("expected/funding_audit.csv not found; no golden to verify against")
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
    print(f"PASS: out/funding_audit.csv matches expected/funding_audit.csv "
          f"({len(got)} lines)")
    return 0


def show():
    if not os.path.exists(OUT_CSV):
        print("out/funding_audit.csv not found; run `python run.py` first")
        return 1
    with open(OUT_CSV, "r", encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))

    def money(v):
        return f"{float(v):,.2f}" if v else ""

    print()
    print("Concentration summary")
    print("-" * 66)
    for r in rows:
        if r["section"] == "summary":
            label = r["measure"].replace("_", " ")
            share = f"{r['share_pct']}%" if r["share_pct"] else ""
            print(f"  {label:<36} {money(r['amount']):>18} {share:>7}")
    for r in rows:
        if r["section"] == "totals_tie":
            label = r["measure"].replace("_", " ")
            print(f"  {label:<36} {money(r['amount']):>18} {'ties':>7}")
    print()

    print("Top recipients by total dollars")
    print("-" * 92)
    header = (f"  {'#':>3} {'recipient':<44} {'pmts':>5} "
              f"{'dollars':>14} {'share':>8} {'cum':>8}")
    print(header)
    print("-" * 92)
    for r in rows:
        if r["section"] == "top_recipients":
            print(f"  {r['rank']:>3} {r['recipient']:<44} {r['payments']:>5} "
                  f"{money(r['amount']):>14} {r['share_pct'] + '%':>8} "
                  f"{r['cumulative_share_pct'] + '%':>8}")
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
