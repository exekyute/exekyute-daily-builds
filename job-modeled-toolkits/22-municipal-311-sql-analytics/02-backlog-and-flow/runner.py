"""Backlog and flow runner for the 311 service-request analytics repo.

Reads the clean requests from the intake tool and the category cost rates, builds an
in-memory SQLite database, and reports per department and month: opening backlog,
requests opened, requests closed, closing backlog, and the cost to serve the requests
closed that month. It confirms the flow identity (opening + new - closed = closing)
holds for every row, checks the worked example and the grand total against spec.md,
and writes period-summary.csv for the dashboard.

Standard library only: csv, sqlite3, decimal, os, sys. Run it with:

    python runner.py
    python runner.py path/to/clean_requests.csv
"""

import csv
import os
import sqlite3
import sys
from decimal import Decimal, ROUND_HALF_UP

HERE = os.path.dirname(os.path.abspath(__file__))
SCHEMA_FILE = os.path.join(HERE, "schema.sql")
QUERIES_FILE = os.path.join(HERE, "queries.sql")
DEFAULT_REQUESTS = os.path.join(HERE, "clean_requests.csv")
RATES_FILE = os.path.join(HERE, "category-cost-rates.csv")
SUMMARY_OUTPUT = os.path.join(HERE, "period-summary.csv")

REQUEST_COLUMNS = [
    "request_id",
    "opened_date",
    "closed_date",
    "category",
    "department",
    "ward",
    "status",
]

# The worked example from spec.md: Roads in 2025-01, plus the grand total cost.
EXPECTED_ROW = {
    "period": "2025-01",
    "department": "Roads",
    "opening": 2,
    "new_requests": 4,
    "closed": 3,
    "closing": 3,
    "cost_to_serve_cents": 25650,  # 3 potholes at 85.50
}
EXPECTED_TOTAL_COST_CENTS = 70850  # 708.50 across every department and month


def dollars_to_cents(text):
    """Convert a dollar string such as '85.50' to integer cents using half-up
    rounding, so money is exact and matches the browser tool to the cent."""
    amount = Decimal(text).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return int(amount * 100)


def month_of(date_text):
    return date_text[:7]


def next_month_start(period):
    """Given 'YYYY-MM', return the first day of the following month as YYYY-MM-DD."""
    year = int(period[:4])
    month = int(period[5:7])
    if month == 12:
        year += 1
        month = 1
    else:
        month += 1
    return "%04d-%02d-01" % (year, month)


def load_requests(path):
    with open(path, newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        missing = [c for c in REQUEST_COLUMNS if c not in (reader.fieldnames or [])]
        if missing:
            raise ValueError("Input is missing required columns: " + ", ".join(missing))
        rows = []
        for raw in reader:
            row = {c: (raw.get(c) or "").strip() for c in REQUEST_COLUMNS}
            if not row["opened_date"]:
                raise ValueError("A request row has no opened_date; run the intake tool first.")
            rows.append(row)
        return rows


def load_rates(path):
    rates = []
    with open(path, newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for raw in reader:
            rates.append((raw["category"].strip(), dollars_to_cents(raw["cost_cad"].strip())))
    return rates


def build_db(requests, rates):
    conn = sqlite3.connect(":memory:")
    with open(SCHEMA_FILE, encoding="utf-8") as handle:
        conn.executescript(handle.read())
    for row in requests:
        conn.execute(
            "INSERT INTO clean_requests "
            "(request_id, opened_date, closed_date, category, department, ward, status) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                row["request_id"],
                row["opened_date"],
                row["closed_date"] or None,
                row["category"],
                row["department"],
                row["ward"],
                row["status"],
            ),
        )
    conn.executemany(
        "INSERT INTO category_cost_rates (category, cost_cents) VALUES (?, ?)", rates
    )
    months = sorted({month_of(r["opened_date"]) for r in requests})
    for period in months:
        conn.execute(
            "INSERT INTO periods (period, start_date, next_date) VALUES (?, ?, ?)",
            (period, period + "-01", next_month_start(period)),
        )
    conn.commit()
    return conn


def parse_queries(path):
    blocks = {}
    name = None
    buffer = []
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            marker = line.strip()
            if marker.startswith("-- name:"):
                if name:
                    blocks[name] = "".join(buffer).strip()
                name = marker.split(":", 1)[1].strip()
                buffer = []
            elif name:
                buffer.append(line)
    if name:
        blocks[name] = "".join(buffer).strip()
    return blocks


def cents_to_dollars(cents):
    return "%d.%02d" % (cents // 100, cents % 100)


def print_summary(rows):
    columns = ["period", "department", "opening", "new", "closed", "closing", "cost_to_serve"]
    widths = [len(c) for c in columns]
    display = []
    for r in rows:
        cells = [
            r["period"], r["department"], str(r["opening"]), str(r["new_requests"]),
            str(r["closed"]), str(r["closing"]), cents_to_dollars(r["cost_to_serve_cents"]),
        ]
        display.append(cells)
        for i, cell in enumerate(cells):
            widths[i] = max(widths[i], len(cell))
    print("\nBacklog and flow by department and month")
    print("  " + " | ".join(columns[i].ljust(widths[i]) for i in range(len(columns))))
    print("  " + "-+-".join("-" * w for w in widths))
    for cells in display:
        print("  " + " | ".join(cells[i].ljust(widths[i]) for i in range(len(columns))))


def export_summary(rows):
    with open(SUMMARY_OUTPUT, "w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            ["period", "department", "opening", "new_requests", "closed", "closing", "cost_to_serve_cents"]
        )
        for r in rows:
            writer.writerow([
                r["period"], r["department"], r["opening"], r["new_requests"],
                r["closed"], r["closing"], r["cost_to_serve_cents"],
            ])


def main():
    requests_path = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_REQUESTS
    if not os.path.isabs(requests_path):
        requests_path = os.path.join(HERE, requests_path)

    print("311 backlog and flow")
    print("Reading: " + os.path.basename(requests_path))

    try:
        requests = load_requests(requests_path)
        rates = load_rates(RATES_FILE)
    except (OSError, ValueError) as err:
        print("\nInput rejected: " + str(err))
        sys.exit(1)

    conn = build_db(requests, rates)
    queries = parse_queries(QUERIES_FILE)

    cur = conn.execute(queries["period_summary"])
    names = [d[0] for d in cur.description]
    rows = [dict(zip(names, record)) for record in cur.fetchall()]

    print_summary(rows)
    export_summary(rows)

    ok = True

    # The flow identity must hold for every department and month.
    identity_failures = [
        r for r in rows
        if r["opening"] + r["new_requests"] - r["closed"] != r["closing"]
    ]
    if identity_failures:
        ok = False

    # The worked example.
    match = next(
        (r for r in rows
         if r["period"] == EXPECTED_ROW["period"] and r["department"] == EXPECTED_ROW["department"]),
        None,
    )
    example_ok = match is not None and all(match[k] == EXPECTED_ROW[k] for k in EXPECTED_ROW)
    if not example_ok:
        ok = False

    total_cost = sum(r["cost_to_serve_cents"] for r in rows)
    total_ok = total_cost == EXPECTED_TOTAL_COST_CENTS
    if not total_ok:
        ok = False

    print("\nChecks")
    print("  [%s] flow identity opening + new - closed = closing holds for all %d rows"
          % ("ok" if not identity_failures else "MISMATCH", len(rows)))
    print("  [%s] worked example Roads 2025-01: opening 2, new 4, closed 3, closing 3, cost 256.50"
          % ("ok" if example_ok else "MISMATCH"))
    print("  [%s] grand total cost to serve: got %s, expected %s"
          % ("ok" if total_ok else "MISMATCH",
             cents_to_dollars(total_cost), cents_to_dollars(EXPECTED_TOTAL_COST_CENTS)))

    print("\n" + ("PASS" if ok else "FAIL"))
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
