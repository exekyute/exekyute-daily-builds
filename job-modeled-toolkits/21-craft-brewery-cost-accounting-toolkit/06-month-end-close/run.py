"""Runner and test harness for the month-end close queries.

Builds an in-memory SQLite database from schema.sql, loads the four input CSVs
(the perpetual valuation, the physical count, the per-SKU margins, and the excise
summary), runs each named query in queries.sql, prints the results as plain
tables, and asserts the totals against the hand-checked figures in spec.md. No
database server and no installs; the standard library does it all.

The close agreeing with these figures is the proof that the SQL tool and the
Python engines line up to the cent: the valuation total matches the perpetual
valuation tool, and the excise total matches the excise duty engine.

Usage:
    python run.py
    python run.py --counts physical_counts_bad.csv   (see the checks fail on bad data)
"""

import argparse
import csv
import os
import sqlite3
import sys
from decimal import Decimal

# Hand-checked expectations from spec.md.
EXPECTED = {
    "total_inventory_value": Decimal("17240.79"),
    "raw_material_value": Decimal("8167.77"),
    "packaging_material_value": Decimal("7997.18"),
    "finished_goods_value": Decimal("1075.84"),
    "total_excise_duty": Decimal("149.17"),
    "exception_count": 2,
    "hops_value_variance": Decimal("-157.44"),
}

TABLES = {
    "perpetual": "perpetual_valuation.csv",
    "physical_count": None,           # filled from the --counts argument
    "sku_margins": "sku_margins.csv",
    "excise_summary": "excise_summary.csv",
}


def load_table(conn, table, path):
    with open(path, newline="", encoding="utf-8") as handle:
        reader = csv.reader(handle)
        header = next(reader)
        rows = [r for r in reader if any(cell.strip() for cell in r)]
    placeholders = ",".join("?" for _ in header)
    conn.executemany(
        "INSERT INTO %s (%s) VALUES (%s)" % (table, ",".join(header), placeholders),
        rows,
    )


def parse_named_queries(path):
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
    header = "  ".join(col.ljust(widths[i]) for i, col in enumerate(columns))
    print("  " + header)
    print("  " + "  ".join("-" * widths[i] for i in range(len(columns))))
    for row in rows:
        cells = ["" if c is None else str(c) for c in row]
        print("  " + "  ".join(cells[i].ljust(widths[i]) for i in range(len(columns))))


def run(data_dir, counts_file):
    here = os.path.dirname(os.path.abspath(__file__))
    conn = sqlite3.connect(":memory:")
    with open(os.path.join(here, "schema.sql"), encoding="utf-8") as handle:
        conn.executescript(handle.read())

    files = dict(TABLES)
    files["physical_count"] = counts_file
    for table, filename in files.items():
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


def cents(number):
    return Decimal(str(number)).quantize(Decimal("0.01"))


def check(results):
    failures = []

    def value_of(name, column):
        columns, rows = results[name]
        return rows[0][columns.index(column)]

    total = cents(value_of("valuation_total", "total_inventory_value"))
    if total != EXPECTED["total_inventory_value"]:
        failures.append("inventory value %s, expected %s" % (total, EXPECTED["total_inventory_value"]))

    by_cat = dict((r[0], cents(r[1])) for r in results["valuation_by_category"][1])
    for category, key in (("raw_material", "raw_material_value"),
                          ("packaging_material", "packaging_material_value"),
                          ("finished_goods", "finished_goods_value")):
        if by_cat.get(category) != EXPECTED[key]:
            failures.append("%s value %s, expected %s" % (category, by_cat.get(category), EXPECTED[key]))

    duty = cents(value_of("excise_total", "total_excise_duty"))
    if duty != EXPECTED["total_excise_duty"]:
        failures.append("excise duty %s, expected %s" % (duty, EXPECTED["total_excise_duty"]))

    exception_count = len(results["exceptions"][1])
    if exception_count != EXPECTED["exception_count"]:
        failures.append("exception count %d, expected %d" % (exception_count, EXPECTED["exception_count"]))

    columns, recon = results["reconciliation"]
    sku_i, var_i, status_i = columns.index("sku"), columns.index("value_variance"), columns.index("status")
    hops = [r for r in recon if r[sku_i] == "RM-HOPS"]
    if not hops:
        failures.append("RM-HOPS missing from reconciliation")
    else:
        if cents(hops[0][var_i]) != EXPECTED["hops_value_variance"]:
            failures.append("hops value variance %s, expected %s" % (hops[0][var_i], EXPECTED["hops_value_variance"]))
        if hops[0][status_i] != "over tolerance":
            failures.append("hops status %s, expected over tolerance" % hops[0][status_i])

    tb_cols, tb_rows = results["trial_balance"]
    debits = cents(tb_rows[0][tb_cols.index("total_debits")])
    credits = cents(tb_rows[0][tb_cols.index("total_credits")])
    if debits != credits:
        failures.append("trial balance does not balance: debits %s, credits %s" % (debits, credits))

    return failures


def main(argv=None):
    parser = argparse.ArgumentParser(description="Month-end close runner.")
    parser.add_argument("--data-dir", default=os.path.dirname(os.path.abspath(__file__)),
                        help="folder holding the input CSVs")
    parser.add_argument("--counts", default="physical_counts.csv",
                        help="physical count file to reconcile against")
    args = parser.parse_args(argv)

    results = run(args.data_dir, args.counts)
    failures = check(results)

    print("")
    if failures:
        print("FAIL")
        for message in failures:
            print("  - %s" % message)
        return 1
    print("PASS: the close balances and every total agrees with the hand-checked figures in spec.md")
    print("      inventory $%s, excise $%s, debits = credits $%s"
          % (EXPECTED["total_inventory_value"], EXPECTED["total_excise_duty"],
             cents(results["trial_balance"][1][0][0])))
    return 0


if __name__ == "__main__":
    sys.exit(main())
