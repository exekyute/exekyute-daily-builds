"""Thin driver for the weather-station data-quality audit. No business logic
here: every rule lives in sql/, this file only sequences the SQL, copies the
BI mart into bi/exports/, and diffs out/ against the golden expected/.

Commands:
    python run.py            run the SQL end to end, then verify
    python run.py verify     golden diff only
    python run.py show       print the station quality scorecard
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
OUT_CSV = os.path.join(HERE, "out", "station_quality.csv")
EXPECTED_CSV = os.path.join(HERE, "expected", "station_quality.csv")
OUT_MART = os.path.join(HERE, "out", "mart_station_quality.csv")
BI_MART = os.path.join(HERE, "bi", "exports", "mart_station_quality.csv")


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
    print("copied out/mart_station_quality.csv -> "
          "bi/exports/mart_station_quality.csv")


def verify():
    if not os.path.exists(OUT_CSV):
        print("out/station_quality.csv not found; run `python run.py` first")
        return 1
    if not os.path.exists(EXPECTED_CSV):
        print("expected/station_quality.csv not found; no golden to verify against")
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
    print(f"PASS: out/station_quality.csv matches expected/station_quality.csv "
          f"({len(got)} lines)")
    return 0


def show():
    if not os.path.exists(OUT_CSV):
        print("out/station_quality.csv not found; run `python run.py` first")
        return 1
    with open(OUT_CSV, "r", encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))

    def section(name):
        return [r for r in rows if r["section"] == name]

    print()
    print("Audit window")
    print("-" * 74)
    for r in section("constants"):
        if r["measure"] in ("WINDOW_START", "WINDOW_END_EXCL"):
            print(f"  {r['measure'].lower():<32} {r['detail']}")
    for r in section("window"):
        print(f"  {r['measure']:<32} {r['detail']}")
    print()

    print("Headline")
    print("-" * 74)
    for r in section("headline"):
        label = r["measure"].replace("_", " ")
        site = f" {r['site_id']}" if r["site_id"] else ""
        pct = f"{r['uptime_pct']}%" if r["uptime_pct"] else ""
        left = r["slots_covered"] or r["readings_actual"]
        print(f"  {label + site:<40} {left:>10} of "
              f"{r['readings_expected']:>10} {pct:>9}")
    print()

    print("Station quality scorecard, worst completeness first")
    print("-" * 110)
    print(f"  {'#':>3} {'site':<8} {'cad_s':>6} {'covered':>8} {'expected':>9} "
          f"{'uptime':>8} {'gaps':>5} {'frozen':>7} {'oor':>4} {'missing':>8}  "
          f"{'flag':<8}")
    print("-" * 110)
    for r in section("completeness_ranking"):
        flag = r["detail"].rsplit(", ", 1)[-1]
        print(f"  {r['rank']:>3} {r['site_id']:<8} {r['cadence_seconds']:>6} "
              f"{r['slots_covered']:>8} {r['readings_expected']:>9} "
              f"{r['uptime_pct'] + '%':>8} {r['gap_count']:>5} "
              f"{r['frozen_run_count']:>7} {r['out_of_range_count']:>4} "
              f"{r['missing_values']:>8}  {flag:<8}")
    print()

    flagged = [r for r in section("station_scorecard") if r["detail"].startswith("flagged")]
    print("Flagged stations and why")
    print("-" * 110)
    for r in flagged:
        print(f"  {r['site_id']:<8} {r['uptime_pct'] + '%':>8}  "
              f"{r['detail'].split(': ', 1)[1]}")
    print()

    print("Longest reporting gaps")
    print("-" * 110)
    print(f"  {'#':>3} {'site':<8} {'date':<12} {'seconds':>9}  detail")
    print("-" * 110)
    for r in section("gap_detail")[:10]:
        print(f"  {r['rank']:>3} {r['site_id']:<8} {r['reading_date']:<12} "
              f"{r['seconds']:>9}  {r['detail']}")
    print()

    print("Frozen air-temperature runs")
    print("-" * 110)
    print(f"  {'#':>3} {'site':<8} {'date':<12} {'readings':>9}  detail")
    print("-" * 110)
    for r in section("frozen_detail"):
        print(f"  {r['rank']:>3} {r['site_id']:<8} {r['reading_date']:<12} "
              f"{r['readings_actual']:>9}  {r['detail']}")
    print()

    print("Out-of-range measure values")
    print("-" * 110)
    for r in section("out_of_range_detail"):
        print(f"  {r['rank']:>3} {r['site_id']:<8} {r['measure']:<20} {r['detail']}")
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
