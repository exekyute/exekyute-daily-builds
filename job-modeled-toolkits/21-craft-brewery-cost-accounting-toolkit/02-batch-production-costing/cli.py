"""Command-line wrapper for the batch production costing tool.

Reads the landed-cost file from the procurement tool plus this period's batch
register, ingredient lines, and packaging runs. Validates them, costs each
batch, prints a summary, and writes two output CSVs: batch_costs.csv (one row
per batch) and finished_unit_costs.csv (one row per packaging run). The excise,
valuation, and margin tools read these.

Usage:
    python cli.py --landed landed_costs.csv --batches batches.csv \
        --ingredients batch_ingredients.csv --runs packaging_runs.csv --out-dir .
"""

import argparse
import csv
import os
import sys
from decimal import Decimal

from batch import cost_all, money, weighted_average_costs
from validation import ValidationError, validate

BATCH_OUT = (
    "batch_id", "beer", "product_line", "abv_class", "brewed_litres",
    "finished_litres", "yield_pct", "ingredient_cost", "labour_cost",
    "overhead_cost", "brew_cost", "packaging_material_cost", "total_batch_cost",
    "cost_per_finished_litre", "volume_flag",
)
FINISHED_OUT = (
    "fg_sku", "description", "product_line", "abv_class", "batch_id",
    "container_sku", "units", "packaged_litres", "beer_cost",
    "packaging_material_cost", "line_cost", "unit_cost",
)


def read_rows(path):
    with open(path, newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        header = reader.fieldnames or []
        rows = [dict(r) for r in reader]
    return header, rows


def group(rows, key):
    out = {}
    for row in rows:
        out.setdefault((row.get(key) or "").strip(), []).append(row)
    return out


def batches_to_typed(rows):
    out = []
    for r in rows:
        out.append({
            "batch_id": r["batch_id"].strip(),
            "beer": r["beer"].strip(),
            "product_line": r["product_line"].strip(),
            "abv_class": r["abv_class"].strip(),
            "brewed_litres": Decimal(r["brewed_litres"].strip()),
            "finished_litres": Decimal(r["finished_litres"].strip()),
            "labour_cost": Decimal(r["labour_cost"].strip()),
            "overhead_cost": Decimal(r["overhead_cost"].strip()),
        })
    return out


def ingredients_typed(rows):
    out = {}
    for r in rows:
        out.setdefault(r["batch_id"].strip(), []).append({
            "sku": r["material_sku"].strip(),
            "quantity": Decimal(r["quantity"].strip()),
        })
    return out


def runs_typed(rows):
    out = {}
    for r in rows:
        out.setdefault(r["batch_id"].strip(), []).append({
            "fg_sku": r["fg_sku"].strip(),
            "description": r["description"].strip(),
            "container_sku": r["container_sku"].strip(),
            "label_sku": (r.get("label_sku") or "").strip(),
            "units": Decimal(r["units"].strip()),
            "litres_per_unit": Decimal(r["litres_per_unit"].strip()),
        })
    return out


def _format(value):
    return str(value) if isinstance(value, Decimal) else value


def write_csv(path, columns, rows):
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(columns)
        for row in rows:
            writer.writerow([_format(row[c]) for c in columns])


def print_summary(summaries, finished):
    grand = money(sum(s["total_batch_cost"] for s in summaries))
    print("Batch production costing")
    print("  batches costed : %d" % len(summaries))
    print("  finished runs  : %d" % len(finished))
    print("  total cost     : $%s" % grand)
    print("")
    print("  %-10s %-8s %10s %12s %14s" % ("batch", "yield%", "litres", "batch cost", "cost/litre"))
    print("  " + "-" * 58)
    for s in summaries:
        print("  %-10s %-8s %10s %12s %14s"
              % (s["batch_id"], s["yield_pct"], s["finished_litres"],
                 s["total_batch_cost"], s["cost_per_finished_litre"]))
        if s["volume_flag"]:
            print("    ! %s" % s["volume_flag"])
    print("")
    print("  %-16s %8s %12s" % ("finished good", "units", "unit cost"))
    print("  " + "-" * 40)
    for f in finished:
        print("  %-16s %8s %12s" % (f["fg_sku"], f["units"], f["unit_cost"]))


def main(argv=None):
    parser = argparse.ArgumentParser(description="Batch production costing.")
    parser.add_argument("--landed", required=True)
    parser.add_argument("--batches", required=True)
    parser.add_argument("--ingredients", required=True)
    parser.add_argument("--runs", required=True)
    parser.add_argument("--out-dir", dest="out_dir")
    args = parser.parse_args(argv)

    for path in (args.landed, args.batches, args.ingredients, args.runs):
        if not os.path.exists(path):
            print("input file not found: %s" % path, file=sys.stderr)
            return 2

    _, landed_rows = read_rows(args.landed)
    batch_header, batch_rows = read_rows(args.batches)
    ing_header, ing_rows = read_rows(args.ingredients)
    run_header, run_rows = read_rows(args.runs)

    wac_costs = weighted_average_costs(landed_rows)
    known = set(wac_costs)

    try:
        validate(batch_rows, batch_header, ing_rows, ing_header, run_rows, run_header, known)
    except ValidationError as error:
        print("Input rejected. Nothing was written.\n", file=sys.stderr)
        for problem in error.problems:
            print("  - %s" % problem, file=sys.stderr)
        return 1

    summaries, finished = cost_all(
        batches_to_typed(batch_rows),
        ingredients_typed(ing_rows),
        runs_typed(run_rows),
        wac_costs,
    )
    print_summary(summaries, finished)

    if args.out_dir:
        write_csv(os.path.join(args.out_dir, "batch_costs.csv"), BATCH_OUT, summaries)
        write_csv(os.path.join(args.out_dir, "finished_unit_costs.csv"), FINISHED_OUT, finished)
        print("\nWrote batch_costs.csv and finished_unit_costs.csv to %s" % args.out_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main())
