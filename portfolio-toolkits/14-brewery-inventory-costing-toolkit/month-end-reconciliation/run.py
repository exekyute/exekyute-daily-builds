"""Runner and test harness for the month-end reconciliation queries.

Builds an in-memory SQLite database from schema.sql, loads the three input
CSVs (the costing engine's perpetual valuation and excise summary, plus the
warehouse physical count), runs each named query in queries.sql, prints the
results as plain tables, and asserts the totals against the hand-checked figures
in spec.md. No database server and no installs; the standard library does it all.

Usage:
    python run.py
    python run.py --data-dir .
"""

import argparse
import csv
import os
import sqlite3
import sys
from decimal import Decimal

# Hand-checked expectations from spec.md. The reconciliation tool agreeing with
# these to the cent is the proof the two tools line up.
EXPECTED = {
    "total_inventory_value": Decimal("25448.34"),
    "finished_goods_value": Decimal("21540.00"),
    "raw_material_value": Decimal("1398.34"),
    "packaging_material_value": Decimal("2510.00"),
    "hops_value_variance": Decimal("-75.17"),
    "exception_count": 5,
    "total_excise_duty": Decimal("423.34"),
}

TABLES = {
    "perpetual": "perpetual_valuation.csv",
    "physical_count": "physical_counts.csv",
    "excise_summary": "excise_summary.csv",
}


def load_table(conn, table, path):
    with open(path, newline="", encoding="utf-8") as handle:
        reader = csv.reader(handle)
        header = next(reader)
        rows = list(reader)
    placeholders = ",".join("?" for _ in header)
    conn.executemany(
        "INSERT INTO %s (%s) VALUES (%s)" % (table, ",".join(header), placeholders),
        rows,
    )


def parse_named_queries(path):
    """Split queries.sql on '-- @name' markers into an ordered list."""
    queries = []
    name = None
    buffer = []
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            stripped = line.strip()
            if stripped.startswith("-- @"):
                if name is not None:
                    queries.append((name, "".join(buffer)))
                name = stripped[4:].strip()
                buffer = []
            elif name is not None:
                buffer.append(line)
    if name is not None:
        queries.append((name, "".join(buffer)))
    return queries


def print_table(title, columns, rows):
    print("\n%s" % title)
    widths = [len(c) for c in columns]
    for row in rows:
        for i, cell in enumerate(row):
            widths[i] = max(widths[i], len("" if cell is None else str(cell)))
    line = "  ".join(col.ljust(widths[i]) for i, col in enumerate(columns))
    print("  " + line)
    print("  " + "  ".join("-" * widths[i] for i in range(len(columns))))
    for row in rows:
        cells = ["" if c is None else str(c) for c in row]
        print("  " + "  ".join(cells[i].ljust(widths[i]) for i in range(len(columns))))


def run(data_dir):
    here = os.path.dirname(os.path.abspath(__file__))
    conn = sqlite3.connect(":memory:")
    with open(os.path.join(here, "schema.sql"), encoding="utf-8") as handle:
        conn.executescript(handle.read())
    for table, filename in TABLES.items():
        load_table(conn, table, os.path.join(data_dir, filename))
    conn.commit()

    results = {}
    for name, sql in parse_named_queries(os.path.join(here, "queries.sql")):
        cursor = conn.execute(sql)
        columns = [d[0] for d in cursor.description]
        rows = cursor.fetchall()
        results[name] = (columns, rows)
        print_table(name, columns, rows)
    return results


def check(results):
    """Assert the query output against the spec. Returns a list of failures."""
    failures = []

    def value_of(name, column):
        columns, rows = results[name]
        idx = columns.index(column)
        return rows[0][idx]

    def cents(number):
        return Decimal(str(number)).quantize(Decimal("0.01"))

    total = cents(value_of("valuation_total", "total_inventory_value"))
    if total != EXPECTED["total_inventory_value"]:
        failures.append("total inventory value %s, expected %s"
                        % (total, EXPECTED["total_inventory_value"]))

    by_cat = dict((r[0], cents(r[1])) for r in results["valuation_by_category"][1])
    for category, key in (
        ("finished_goods", "finished_goods_value"),
        ("raw_material", "raw_material_value"),
        ("packaging_material", "packaging_material_value"),
    ):
        if by_cat.get(category) != EXPECTED[key]:
            failures.append("%s value %s, expected %s"
                            % (category, by_cat.get(category), EXPECTED[key]))

    columns, recon_rows = results["reconciliation"]
    sku_i = columns.index("sku")
    var_i = columns.index("value_variance")
    status_i = columns.index("status")
    hops = [r for r in recon_rows if r[sku_i] == "RM-HOPS-CASCADE"]
    if not hops:
        failures.append("RM-HOPS-CASCADE missing from reconciliation")
    else:
        if cents(hops[0][var_i]) != EXPECTED["hops_value_variance"]:
            failures.append("hops value variance %s, expected %s"
                            % (hops[0][var_i], EXPECTED["hops_value_variance"]))
        if hops[0][status_i] != "over tolerance":
            failures.append("hops status %s, expected over tolerance" % hops[0][status_i])

    exception_count = len(results["exceptions"][1])
    if exception_count != EXPECTED["exception_count"]:
        failures.append("exception count %d, expected %d"
                        % (exception_count, EXPECTED["exception_count"]))

    duty = cents(value_of("excise_total", "total_excise_duty"))
    if duty != EXPECTED["total_excise_duty"]:
        failures.append("total excise duty %s, expected %s"
                        % (duty, EXPECTED["total_excise_duty"]))

    return failures


def main(argv=None):
    parser = argparse.ArgumentParser(description="Month-end reconciliation runner.")
    parser.add_argument(
        "--data-dir",
        default=os.path.dirname(os.path.abspath(__file__)),
        help="folder holding the three input CSVs",
    )
    args = parser.parse_args(argv)

    results = run(args.data_dir)
    failures = check(results)

    print("")
    if failures:
        print("FAIL")
        for message in failures:
            print("  - %s" % message)
        return 1
    print("PASS: every total agrees with the hand-checked figures in spec.md")
    return 0


if __name__ == "__main__":
    sys.exit(main())
