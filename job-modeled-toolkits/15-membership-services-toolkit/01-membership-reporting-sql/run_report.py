"""Run the saved membership reports against the sample data.

This builds a small in-memory SQLite database from schema.sql, loads the members
from sample_members.csv, runs the reports in queries.sql, and prints the results.
It applies HST (13%) to dues with Decimal rounding, checks the totals against the
hand-checked figures in spec.md, and writes renewal_worklist.csv for the Excel
and dashboard tools to read.

Standard library only. Run it with: python run_report.py
"""

import csv
import os
import sqlite3
import sys
from decimal import Decimal, ROUND_HALF_UP

HERE = os.path.dirname(os.path.abspath(__file__))
SCHEMA = os.path.join(HERE, "schema.sql")
QUERIES = os.path.join(HERE, "queries.sql")
SAMPLE = os.path.join(HERE, "sample_members.csv")
OUTPUT = os.path.join(HERE, "renewal_worklist.csv")

HST_RATE = Decimal("0.13")
CENT = Decimal("0.01")


def money(value):
    """Round a dollar amount to the cent, half up."""
    return Decimal(str(value)).quantize(CENT, rounding=ROUND_HALF_UP)


def hst_on(dues):
    """HST charged on a dues amount."""
    return (Decimal(str(dues)) * HST_RATE).quantize(CENT, rounding=ROUND_HALF_UP)


def load_database():
    """Create the tables, seed the tiers, and load the members from the CSV."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    with open(SCHEMA, encoding="utf-8") as fh:
        conn.executescript(fh.read())

    with open(SAMPLE, newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))

    for row in rows:
        conn.execute(
            "INSERT INTO members "
            "(member_id, name, tier, join_month, status, dues, late_fee, expiry_date) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                int(row["member_id"]),
                row["name"],
                row["tier"] or None,
                int(row["join_month"]) if row["join_month"] else None,
                row["status"],
                float(row["dues"]) if row["dues"] else None,
                float(row["late_fee"]) if row["late_fee"] else 0.0,
                row["expiry_date"],
            ),
        )
    conn.commit()
    return conn


def load_queries():
    """Read queries.sql and split it into named statements on the -- name: marks."""
    queries = {}
    name = None
    buffer = []
    with open(QUERIES, encoding="utf-8") as fh:
        for line in fh:
            stripped = line.strip()
            if stripped.startswith("-- name:"):
                if name:
                    queries[name] = "".join(buffer).strip()
                name = stripped.split(":", 1)[1].strip()
                buffer = []
            elif name:
                buffer.append(line)
    if name:
        queries[name] = "".join(buffer).strip()
    return queries


def fmt(value):
    """Format a cell for the printed tables."""
    if value is None:
        return "-"
    if isinstance(value, float):
        return f"{value:,.2f}"
    return str(value)


def print_table(title, rows):
    """Print query rows as a simple aligned table."""
    print(f"\n{title}")
    print("-" * len(title))
    if not rows:
        print("(no rows)")
        return
    headers = rows[0].keys()
    cells = [[fmt(r[h]) for h in headers] for r in rows]
    widths = [max(len(h), *(len(row[i]) for row in cells)) for i, h in enumerate(headers)]
    line = "  ".join(h.ljust(widths[i]) for i, h in enumerate(headers))
    print(line)
    print("  ".join("-" * widths[i] for i in range(len(headers))))
    for row in cells:
        print("  ".join(row[i].ljust(widths[i]) for i in range(len(headers))))


def write_worklist_csv(rows):
    """Write the full worklist with per-member HST and total for the next tools."""
    with open(OUTPUT, "w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(
            ["member_id", "name", "tier", "status", "expiry_date",
             "dues", "late_fee", "hst", "total", "action"]
        )
        for r in rows:
            if r["dues"] is None:
                dues = late = hst = total = ""
            else:
                dues = money(r["dues"])
                late = money(r["late_fee"])
                hst = hst_on(r["dues"])
                total = dues + late + hst
            writer.writerow(
                [r["member_id"], r["name"], r["tier"] or "", r["status"],
                 r["expiry_date"], dues, late, hst, total, r["action"]]
            )


def main():
    conn = load_database()
    queries = load_queries()

    def run(name):
        return [dict(r) for r in conn.execute(queries[name]).fetchall()]

    # The two weekly worklists.
    print_table("Expiring in the next 30 days", run("expiring_worklist"))
    print_table("Lapsed in the past 30 days", run("lapsed_worklist"))

    # The monthly dues summary, with HST added per tier.
    by_tier = run("dues_summary_by_tier")
    print("\nDues summary by tier")
    print("--------------------")
    print("tier          members  dues       hst      total")
    print("------------  -------  ---------  -------  ---------")
    for r in by_tier:
        dues = money(r["dues"])
        hst = hst_on(r["dues"])
        total = dues + hst
        print(f"{r['tier']:<12}  {r['members']:>7}  {dues:>9}  {hst:>7}  {total:>9}")

    grand = run("dues_summary_total")[0]
    g_dues = money(grand["dues"])
    g_late = money(grand["late_fees"])
    g_hst = hst_on(grand["dues"])
    g_total = g_dues + g_hst + g_late
    print("------------  -------  ---------  -------  ---------")
    print(f"{'All tiers':<12}  {grand['members']:>7}  {g_dues:>9}  {g_hst:>7}  {g_dues + g_hst:>9}")
    print(f"\nLate fees: {g_late}    Grand total billed: {g_total}")

    # Reconciliation counts.
    print_table("Reconciliation counts", run("reconciliation"))

    # Write the worklist CSV for the Excel and dashboard tools.
    worklist = run("worklist_all")
    write_worklist_csv(worklist)
    print(f"\nWrote {os.path.basename(OUTPUT)} ({len(worklist)} rows).")

    # Check the totals against the hand-checked figures in spec.md.
    expected = {
        "billable_members": 10,
        "total_dues": Decimal("1733.75"),
        "hst": Decimal("225.39"),
        "late_fees": Decimal("25.00"),
        "grand_total": Decimal("1984.14"),
        "total_rows": 12,
        "distinct_members": 11,
    }
    recon = run("reconciliation")[0]
    checks = [
        ("billable members", grand["members"], expected["billable_members"]),
        ("total dues", g_dues, expected["total_dues"]),
        ("HST on dues", g_hst, expected["hst"]),
        ("late fees", g_late, expected["late_fees"]),
        ("grand total billed", g_total, expected["grand_total"]),
        ("total rows", recon["total_rows"], expected["total_rows"]),
        ("distinct members", recon["distinct_members"], expected["distinct_members"]),
    ]
    print("\nChecks against spec.md")
    print("----------------------")
    ok = True
    for label, got, want in checks:
        passed = got == want
        ok = ok and passed
        print(f"[{'PASS' if passed else 'FAIL'}] {label}: got {got}, expected {want}")

    print("\nAll checks passed." if ok else "\nSome checks FAILED.")
    conn.close()
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
