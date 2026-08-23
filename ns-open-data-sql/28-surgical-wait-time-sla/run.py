"""Thin driver for the surgical wait-time SLA tracker. No business logic here:
every rule, threshold, and ranking lives in sql/. This file only sequences the
SQL, copies the BI mart into bi/exports/, diffs out/ against the golden
expected/, and prints the headline table.

Commands:
    python run.py            run the SQL end to end, then verify
    python run.py verify     golden diff only
    python run.py show       print the breach summary
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
OUT_CSV = os.path.join(HERE, "out", "wait_time_sla.csv")
EXPECTED_CSV = os.path.join(HERE, "expected", "wait_time_sla.csv")
OUT_MART = os.path.join(HERE, "out", "mart_wait_times.csv")
BI_MART = os.path.join(HERE, "bi", "exports", "mart_wait_times.csv")

PROCEDURES_SHOWN = 15


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
    print("copied out/mart_wait_times.csv -> bi/exports/mart_wait_times.csv")


def verify():
    if not os.path.exists(OUT_CSV):
        print("out/wait_time_sla.csv not found; run `python run.py` first")
        return 1
    if not os.path.exists(EXPECTED_CSV):
        print("expected/wait_time_sla.csv not found; no golden to verify against")
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
    print(f"PASS: out/wait_time_sla.csv matches expected/wait_time_sla.csv "
          f"({len(got)} lines)")
    return 0


def clip(text, width):
    return text if len(text) <= width else text[:width - 2] + ".."


def show():
    if not os.path.exists(OUT_CSV):
        print("out/wait_time_sla.csv not found; run `python run.py` first")
        return 1
    with open(OUT_CSV, "r", encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))

    def section(name):
        return [r for r in rows if r["section"] == name]

    print()
    print("Targets and coverage")
    print("-" * 72)
    for r in section("constants") + section("coverage"):
        label = r["measure"].replace("_", " ")
        shown = r["value"] or r["period"]
        print(f"  {label:<44} {shown:>14}")
    print()

    print("Rows held out of the facility grain")
    print("-" * 72)
    for r in section("exclusions"):
        print(f"  {r['measure'].replace('_', ' '):<44} {r['value']:>14}")
    print()

    print("Breach rates and tail-gap spread")
    print("-" * 72)
    for r in section("breach_summary"):
        label = r["measure"].replace("_", " ")
        rows_n = r["surgery_rows"] or r["consult_rows"]
        breaches = r["surgery_breaches"] or r["consult_breaches"]
        pct = r["surgery_breach_pct"] or r["consult_breach_pct"]
        detail = f"  {breaches}/{rows_n} lines = {pct}%" if pct else ""
        print(f"  {label:<32} {r['value']:>8}{detail}")
    print()

    print("Facilities ranked by surgery-median breach rate")
    print("-" * 100)
    print(f"  {'#':>3} {'facility':<36} {'zone':<7} {'lines':>6} "
          f"{'breach':>7} {'rate':>8} {'min?':>5} {'worst':>7}")
    print("-" * 100)
    for r in section("worst_facilities"):
        print(f"  {r['rank']:>3} {clip(r['facility'], 36):<36} {r['zone']:<7} "
              f"{r['surgery_rows']:>6} {r['surgery_breaches']:>7} "
              f"{r['surgery_breach_pct'] + '%':>8} {r['meets_min_rows']:>5} "
              f"{r['surgery_median']:>7}")
    print()

    procedures = section("worst_procedures")
    print(f"Procedures ranked by surgery-median breach rate "
          f"(first {PROCEDURES_SHOWN} of {len(procedures)})")
    print("-" * 100)
    print(f"  {'#':>3} {'procedure':<46} {'lines':>6} {'breach':>7} "
          f"{'rate':>8} {'worst':>7} {'gap':>6}")
    print("-" * 100)
    for r in procedures[:PROCEDURES_SHOWN]:
        print(f"  {r['rank']:>3} {clip(r['procedure'], 46):<46} "
              f"{r['surgery_rows']:>6} {r['surgery_breaches']:>7} "
              f"{r['surgery_breach_pct'] + '%':>8} {r['surgery_median']:>7} "
              f"{r['surgery_tail_gap']:>6}")
    print()

    print("Published provincial reference series, quarter over quarter")
    print("-" * 100)
    print(f"  {'period':<9} {'lines':>6} {'breach':>7} {'rate':>8} "
          f"{'qoq':>8}  {'longest published surgery median that quarter'}")
    print("-" * 100)
    for r in section("provincial_trend"):
        qoq = (r["qoq_surgery_breach_pct"] + " pp") if r["qoq_surgery_breach_pct"] else ""
        print(f"  {r['period']:<9} {r['surgery_rows']:>6} "
              f"{r['surgery_breaches']:>7} {r['surgery_breach_pct'] + '%':>8} "
              f"{qoq:>8}  {clip(r['procedure'], 42)} at {r['surgery_median']} days")
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
