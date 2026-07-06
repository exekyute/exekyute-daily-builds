"""Thin driver for the farm commodity-mix-shift SQL pipeline.

This file holds no analytical logic. Every aggregation, cleaning rule, and ranking lives in the
files under sql/. The driver only:
  - runs each sql/*.sql file in filename order (00 through 99),
  - prints the headline and the endpoint ranking the SQL computed,
  - and verifies out/commodity_mix.csv against expected/commodity_mix.csv row for row.

Usage:
  python run.py          run the SQL end to end, then verify out/ against expected/
  python run.py verify   re-run only the out-vs-expected diff
  python run.py show      run the SQL, then print the endpoint shift ranking (no verify)
"""

import os
import sys
from pathlib import Path

import duckdb

HERE = Path(__file__).resolve().parent
SQL_DIR = HERE / "sql"
OUT = HERE / "out" / "commodity_mix.csv"
EXPECTED = HERE / "expected" / "commodity_mix.csv"


def run_sql(con):
    """Execute every sql/*.sql file in filename order."""
    (HERE / "out").mkdir(exist_ok=True)
    for path in sorted(SQL_DIR.glob("*.sql")):
        print(f"  running {path.name}")
        con.execute(path.read_text(encoding="utf-8"))


def print_headline(con):
    """Print the two headline rows the SQL put in the headline table."""
    print()
    print("Headline (share of the registered-farm mix, first vs last fiscal year):")
    rows = con.execute(
        "SELECT metric, commodity, first_share_pct, last_share_pct, share_change_pp "
        "FROM headline ORDER BY share_change_pp DESC"
    ).fetchall()
    for metric, commodity, first_share, last_share, change in rows:
        sign = "+" if change >= 0 else ""
        print(f"  {metric:<18} {commodity:<26} {first_share:>6}% -> {last_share:>6}%  "
              f"({sign}{change} pp)")


def print_ranking(con):
    """Print the full endpoint ranking the SQL put in the commodity_growth table."""
    rows = con.execute(
        "SELECT commodity, first_share_pct, last_share_pct, share_change_pp, direction "
        "FROM commodity_growth ORDER BY share_change_pp DESC, commodity"
    ).fetchall()
    print()
    print("Commodity-mix shift, first vs last fiscal year (share of registered farms):")
    print("-" * 74)
    print(f"  {'commodity':<26}{'first':>8}{'last':>8}{'change_pp':>12}  direction")
    print("-" * 74)
    for commodity, first_share, last_share, change, direction in rows:
        sign = "+" if change >= 0 else ""
        print(f"  {commodity:<26}{first_share:>7}%{last_share:>7}%{sign + str(change):>12}  {direction}")
    print("-" * 74)
    print("  ('Other' is a residual bucket and is left out of the headline ranking.)")


def build():
    """Run every SQL step in order, then print the headline the SQL produced."""
    con = duckdb.connect()
    run_sql(con)
    print_headline(con)
    con.close()


def show():
    """Run every SQL step in order, then print the endpoint ranking and headline."""
    con = duckdb.connect()
    run_sql(con)
    print_ranking(con)
    print_headline(con)
    con.close()


def verify():
    """Compare out/commodity_mix.csv to expected/commodity_mix.csv line for line."""
    if not OUT.exists():
        print(f"FAIL: {OUT.relative_to(HERE)} does not exist; run `python run.py` first.")
        return 1
    if not EXPECTED.exists():
        print(f"FAIL: {EXPECTED.relative_to(HERE)} does not exist; nothing to compare against.")
        return 1

    got = OUT.read_text(encoding="utf-8").splitlines()
    want = EXPECTED.read_text(encoding="utf-8").splitlines()

    if got == want:
        print(f"PASS: out matches expected ({len(want)} lines).")
        return 0

    print("FAIL: out does not match expected. First differing rows:")
    for i in range(max(len(got), len(want))):
        g = got[i] if i < len(got) else "<missing>"
        w = want[i] if i < len(want) else "<missing>"
        if g != w:
            print(f"  line {i + 1}")
            print(f"    expected: {w}")
            print(f"    got:      {g}")
            break
    if len(got) != len(want):
        print(f"  (row count differs: expected {len(want)}, got {len(got)})")
    return 1


def main():
    # Anchor to the project folder so the relative paths in the SQL resolve the same way
    # no matter which directory the driver is launched from.
    os.chdir(HERE)
    mode = sys.argv[1] if len(sys.argv) > 1 else "run"
    if mode == "verify":
        sys.exit(verify())
    if mode == "show":
        show()
        sys.exit(0)
    if mode != "run":
        print(f"unknown command: {mode!r}. Use `python run.py`, `python run.py verify`, "
              f"or `python run.py show`.")
        sys.exit(2)
    build()
    print()
    sys.exit(verify())


if __name__ == "__main__":
    main()
