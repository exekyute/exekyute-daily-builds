"""SLA and aging runner for the 311 service-request analytics repo.

Reads the clean requests and the category SLA targets, builds an in-memory SQLite
database, and reports two things: time to close for the requests already resolved
(average days and SLA breaches by category), and the aging of the requests still
open as of the report date, bucketed by days open with the overdue ones counted. It
checks the headline numbers against spec.md and writes two CSVs for the dashboard.

The report date is the last day of the latest month a request was opened, so the
aging is measured at a fixed, repeatable point.

Standard library only: csv, sqlite3, decimal, datetime, os, sys. Run it with:

    python runner.py
    python runner.py path/to/clean_requests.csv
"""

import csv
import os
import sqlite3
import sys
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP

HERE = os.path.dirname(os.path.abspath(__file__))
SCHEMA_FILE = os.path.join(HERE, "schema.sql")
QUERIES_FILE = os.path.join(HERE, "queries.sql")
DEFAULT_REQUESTS = os.path.join(HERE, "clean_requests.csv")
TARGETS_FILE = os.path.join(HERE, "sla-targets.csv")
CATEGORY_OUTPUT = os.path.join(HERE, "category-sla.csv")
AGING_OUTPUT = os.path.join(HERE, "sla-aging.csv")

REQUEST_COLUMNS = [
    "request_id",
    "opened_date",
    "closed_date",
    "category",
    "department",
    "ward",
    "status",
]

BUCKET_ORDER = ["0-7", "8-14", "15-30", "31+"]

# Headline numbers from spec.md.
EXPECTED = {
    "overall_avg_days": Decimal("11.22"),
    "pothole_avg_days": Decimal("9.33"),
    "total_breaches": 5,
    "total_open": 5,
    "total_overdue": 4,
}


def round2(value):
    return Decimal(value).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


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


def load_targets(path):
    targets = []
    with open(path, newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for raw in reader:
            targets.append((raw["category"].strip(), int(raw["target_days"].strip())))
    return targets


def report_as_of(requests):
    """Last day of the latest month any request was opened."""
    latest_month = max(r["opened_date"][:7] for r in requests)
    year = int(latest_month[:4])
    month = int(latest_month[5:7])
    if month == 12:
        first_of_next = date(year + 1, 1, 1)
    else:
        first_of_next = date(year, month + 1, 1)
    return (first_of_next - timedelta(days=1)).isoformat()


def build_db(requests, targets):
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
    conn.executemany("INSERT INTO sla_targets (category, target_days) VALUES (?, ?)", targets)
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


def print_category_table(rows):
    columns = ["category", "closed", "avg_days", "target", "breaches"]
    display = []
    for r in rows:
        avg = round2(Decimal(r["total_days"]) / Decimal(r["closed_count"]))
        display.append([
            r["category"], str(r["closed_count"]), str(avg),
            str(r["target_days"]), str(r["breaches"]),
        ])
    widths = [len(c) for c in columns]
    for cells in display:
        for i, cell in enumerate(cells):
            widths[i] = max(widths[i], len(cell))
    print("\nTime to close by category (closed requests)")
    print("  " + " | ".join(columns[i].ljust(widths[i]) for i in range(len(columns))))
    print("  " + "-+-".join("-" * w for w in widths))
    for cells in display:
        print("  " + " | ".join(cells[i].ljust(widths[i]) for i in range(len(columns))))


def print_aging_table(rows):
    columns = ["bucket", "open", "overdue"]
    widths = [len(c) for c in columns]
    display = [[r["bucket"], str(r["open_count"]), str(r["overdue"])] for r in rows]
    for cells in display:
        for i, cell in enumerate(cells):
            widths[i] = max(widths[i], len(cell))
    print("\nOpen request aging (days open as of the report date)")
    print("  " + " | ".join(columns[i].ljust(widths[i]) for i in range(len(columns))))
    print("  " + "-+-".join("-" * w for w in widths))
    for cells in display:
        print("  " + " | ".join(cells[i].ljust(widths[i]) for i in range(len(columns))))


def export_category(rows):
    with open(CATEGORY_OUTPUT, "w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["category", "closed_count", "total_days", "target_days", "breaches"])
        for r in rows:
            writer.writerow([
                r["category"], r["closed_count"], r["total_days"], r["target_days"], r["breaches"],
            ])


def export_aging(rows):
    with open(AGING_OUTPUT, "w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["bucket", "open_count", "overdue"])
        for r in rows:
            writer.writerow([r["bucket"], r["open_count"], r["overdue"]])


def main():
    requests_path = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_REQUESTS
    if not os.path.isabs(requests_path):
        requests_path = os.path.join(HERE, requests_path)

    print("311 SLA and aging")
    print("Reading: " + os.path.basename(requests_path))

    try:
        requests = load_requests(requests_path)
        targets = load_targets(TARGETS_FILE)
    except (OSError, ValueError) as err:
        print("\nInput rejected: " + str(err))
        sys.exit(1)

    as_of = report_as_of(requests)
    print("Report date: " + as_of)

    conn = build_db(requests, targets)
    queries = parse_queries(QUERIES_FILE)

    cur = conn.execute(queries["time_to_close"])
    names = [d[0] for d in cur.description]
    category_rows = [dict(zip(names, record)) for record in cur.fetchall()]

    cur = conn.execute(queries["open_aging"], {"as_of": as_of})
    names = [d[0] for d in cur.description]
    found = {r["bucket"]: r for r in (dict(zip(names, record)) for record in cur.fetchall())}
    aging_rows = [
        found.get(b, {"bucket": b, "open_count": 0, "overdue": 0}) for b in BUCKET_ORDER
    ]

    print_category_table(category_rows)
    print_aging_table(aging_rows)

    export_category(category_rows)
    export_aging(aging_rows)

    # Headline numbers.
    total_days = sum(r["total_days"] for r in category_rows)
    total_closed = sum(r["closed_count"] for r in category_rows)
    overall_avg = round2(Decimal(total_days) / Decimal(total_closed))
    pothole = next((r for r in category_rows if r["category"] == "Pothole"), None)
    pothole_avg = round2(Decimal(pothole["total_days"]) / Decimal(pothole["closed_count"]))
    total_breaches = sum(r["breaches"] for r in category_rows)
    total_open = sum(r["open_count"] for r in aging_rows)
    total_overdue = sum(r["overdue"] for r in aging_rows)
    breach_rate = round2(Decimal(total_breaches) * 100 / Decimal(total_closed))

    checks = [
        ("overall average days to close", overall_avg, EXPECTED["overall_avg_days"]),
        ("pothole average days to close", pothole_avg, EXPECTED["pothole_avg_days"]),
        ("total SLA breaches among closed", total_breaches, EXPECTED["total_breaches"]),
        ("total open requests", total_open, EXPECTED["total_open"]),
        ("total overdue open requests", total_overdue, EXPECTED["total_overdue"]),
    ]

    print("\nChecks")
    ok = True
    for label, got, want in checks:
        mark = "ok" if got == want else "MISMATCH"
        if got != want:
            ok = False
        print("  [%s] %s: got %s, expected %s" % (mark, label, got, want))
    print("  (for reference) breach rate among closed requests: %s%%" % breach_rate)

    print("\n" + ("PASS" if ok else "FAIL"))
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
