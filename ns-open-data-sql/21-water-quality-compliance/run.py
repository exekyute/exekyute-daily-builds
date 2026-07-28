"""Thin driver for the water-quality guideline compliance build. No business
logic here: every rule, threshold, and accepted-value list lives in sql/.
This file only sequences the SQL, copies the BI mart into bi/exports/, and
diffs out/ against the golden expected/.

Commands:
    python run.py            run the SQL end to end, then verify
    python run.py verify     golden diff only
    python run.py show       print the compliance summary
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
OUT_CSV = os.path.join(HERE, "out", "water_compliance.csv")
EXPECTED_CSV = os.path.join(HERE, "expected", "water_compliance.csv")
OUT_MART = os.path.join(HERE, "out", "mart_water.csv")
BI_MART = os.path.join(HERE, "bi", "exports", "mart_water.csv")


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
    print("copied out/mart_water.csv -> bi/exports/mart_water.csv")


def verify():
    if not os.path.exists(OUT_CSV):
        print("out/water_compliance.csv not found; run `python run.py` first")
        return 1
    if not os.path.exists(EXPECTED_CSV):
        print("expected/water_compliance.csv not found; no golden to verify against")
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
    print(f"PASS: out/water_compliance.csv matches expected/water_compliance.csv "
          f"({len(got)} lines)")
    return 0


def table(rows, columns):
    """Aligned plain-ASCII table. columns is a list of (header, key, align)."""
    widths = []
    for header, key, _ in columns:
        widest = max([len(header)] + [len(r.get(key, "")) for r in rows])
        widths.append(widest)
    head = "  ".join(
        h.ljust(w) if a == "l" else h.rjust(w)
        for (h, _, a), w in zip(columns, widths)
    )
    rule = "  ".join("-" * w for w in widths)
    lines = ["  " + head, "  " + rule]
    for r in rows:
        lines.append("  " + "  ".join(
            r.get(k, "").ljust(w) if a == "l" else r.get(k, "").rjust(w)
            for (_, k, a), w in zip(columns, widths)
        ))
    return "\n".join(lines)


def show():
    if not os.path.exists(OUT_CSV):
        print("out/water_compliance.csv not found; run `python run.py` first")
        return 1
    with open(OUT_CSV, "r", encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))

    def section(name):
        return [r for r in rows if r["section"] == name]

    print()
    print("Compliance summary")
    print("-" * 74)
    for r in section("summary"):
        label = r["measure"].replace("_", " ")
        bits = []
        if r["n_samples"]:
            bits.append(f"{int(r['n_samples']):,}")
        if r["n_passing"]:
            bits.append(f"{int(r['n_passing']):,} passing")
        if r["pass_pct"]:
            bits.append(f"{r['pass_pct']}% pass rate")
        if r["n_non_detect"]:
            bits.append(f"{int(r['n_non_detect']):,} non-detect")
        if r["n_censored_above"] and r["n_censored_above"] != "0":
            bits.append(f"{int(r['n_censored_above']):,} unconfirmable")
        print(f"  {label:<32} {', '.join(bits)}")
    print()

    print("Pass rate by analyte, worst first")
    print(table(section("analyte_compliance"), [
        ("#", "rank", "r"),
        ("analyte", "analyte", "l"),
        ("dir", "direction", "l"),
        ("threshold", "threshold", "r"),
        ("unit", "guideline_unit", "l"),
        ("samples", "n_samples", "r"),
        ("passing", "n_passing", "r"),
        ("pass %", "pass_pct", "r"),
        ("nondet", "n_non_detect", "r"),
        ("unconf", "n_censored_above", "r"),
    ]))
    print()

    print("Pass rate by monitoring location, worst first")
    print(table(section("location_compliance"), [
        ("#", "rank", "r"),
        ("location id", "location_id", "l"),
        ("location", "location", "l"),
        ("samples", "n_samples", "r"),
        ("passing", "n_passing", "r"),
        ("pass %", "pass_pct", "r"),
        ("nondet", "n_non_detect", "r"),
        ("last sample", "last_sample_date", "l"),
        ("days", "days_since_last_sample", "r"),
    ]))
    print()

    print("Worst analyte and location cells")
    print(table(section("worst_cells"), [
        ("#", "rank", "r"),
        ("analyte", "analyte", "l"),
        ("location", "location", "l"),
        ("samples", "n_samples", "r"),
        ("passing", "n_passing", "r"),
        ("pass %", "pass_pct", "r"),
    ]))
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
