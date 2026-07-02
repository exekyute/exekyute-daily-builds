"""Command-line wrapper for the cost-allocation engine.

Reads a cost pool and a driver table, validates both, splits every pool item across
the departments by driver, and writes two files:

  allocation_matrix.csv  - one row per department with its driver, its share of each
                           cost item, and its total. The workbook builder in 02 reads
                           this file.
  department_summary.csv - one row per department with its total and its share of the
                           pool.

Usage:
  python cli.py
  python cli.py --pool cost_pool.csv --drivers drivers.csv
"""

import argparse
import csv
import sys
from decimal import Decimal

from allocation import build_allocation
from validation import ValidationError, validate_driver_row, validate_pool_row


def load_pool(path):
    items = []
    seen = set()
    with open(path, newline="", encoding="utf-8") as handle:
        for raw in csv.DictReader(handle):
            item, amount = validate_pool_row(raw)
            if item in seen:
                raise ValidationError("Pool: item %r appears more than once" % item)
            seen.add(item)
            items.append((item, amount))
    if not items:
        raise ValidationError("Cost pool file is empty")
    return items


def load_drivers(path):
    drivers = {}
    with open(path, newline="", encoding="utf-8") as handle:
        for raw in csv.DictReader(handle):
            dept, value = validate_driver_row(raw)
            if dept in drivers:
                raise ValidationError("Drivers: department %r appears more than once" % dept)
            drivers[dept] = value
    if not drivers:
        raise ValidationError("Drivers file is empty")
    if sum(drivers.values()) <= 0:
        raise ValidationError("Drivers: the total driver value must be greater than zero")
    return drivers


def write_matrix(path, result):
    columns = ["department", "driver_value"] + result["items"] + ["total"]
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        for row in result["rows"]:
            record = {"department": row["department"], "driver_value": str(row["driver_value"]), "total": str(row["total"])}
            for item in result["items"]:
                record[item] = str(row["allocations"][item])
            writer.writerow(record)


def write_summary(path, result):
    columns = ["department", "driver_value", "allocated_total", "pct_of_pool"]
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        for row in result["rows"]:
            writer.writerow({
                "department": row["department"], "driver_value": str(row["driver_value"]),
                "allocated_total": str(row["total"]), "pct_of_pool": str(row["pct_of_pool"]),
            })


def main(argv=None):
    parser = argparse.ArgumentParser(description="IT shared-cost allocation and showback engine.")
    parser.add_argument("--pool", default="cost_pool.csv")
    parser.add_argument("--drivers", default="drivers.csv")
    parser.add_argument("--matrix-out", default="allocation_matrix.csv")
    parser.add_argument("--summary-out", default="department_summary.csv")
    args = parser.parse_args(argv)

    try:
        pool = load_pool(args.pool)
        drivers = load_drivers(args.drivers)
    except ValidationError as error:
        print("Input rejected. %s" % error, file=sys.stderr)
        return 1
    except FileNotFoundError as error:
        print("File not found: %s" % error.filename, file=sys.stderr)
        return 1

    result = build_allocation(pool, drivers)
    write_matrix(args.matrix_out, result)
    write_summary(args.summary_out, result)

    print("IT cost allocation and showback")
    print("Pool: %s across %d items   Total driver: %s   Departments: %d" % (
        result["pool_total"], len(result["items"]), result["total_driver"], len(result["departments"])))
    print()
    header = "  %-14s %8s %14s %10s" % ("Department", "Driver", "Allocated", "% pool")
    print(header)
    for row in result["rows"]:
        pct = (row["pct_of_pool"] * 100).quantize(Decimal("0.1"))
        print("  %-14s %8s %14s %9s%%" % (row["department"], row["driver_value"], row["total"], pct))
    print("  " + "-" * (len(header) - 2))
    print("  %-14s %8s %14s" % ("Total", result["total_driver"], result["allocated_total"]))
    print()
    print("Allocated total ties to pool: %s" % (result["allocated_total"] == result["pool_total"]))
    print("Wrote %s and %s" % (args.matrix_out, args.summary_out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
