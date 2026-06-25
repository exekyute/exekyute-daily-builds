"""Command-line wrapper for the brewery inventory costing engine.

Reads a transaction CSV, validates it, replays each SKU's ledger to a
weighted-average ending position, computes federal excise duty on the beer
packaged in the period, and writes two output CSVs the reconciliation tool
reads next. All file and console work lives here; the math lives in costing.py.

Usage:
    python cli.py sample_transactions.csv --ytd-hl 1960 --out-dir .
"""

import argparse
import csv
import sys
from collections import OrderedDict
from decimal import Decimal

import costing
import validation


def read_transactions(path):
    with open(path, newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        fieldnames = reader.fieldnames
        rows = list(reader)
    return fieldnames, rows


def _decimal(raw):
    text = (raw or "").strip()
    return Decimal(text) if text else Decimal("0")


def build_ledgers(rows):
    """Group rows by SKU in first-seen order and run each ledger."""
    by_sku = OrderedDict()
    meta = {}
    for row in rows:
        sku = row["sku"].strip()
        by_sku.setdefault(sku, [])
        by_sku[sku].append(
            {
                "txn_type": row["txn_type"].strip(),
                "quantity": _decimal(row["quantity"]),
                "unit_price": _decimal(row["unit_price"]),
                "freight": _decimal(row["freight"]),
                "customs_duty": _decimal(row["customs_duty"]),
            }
        )
        meta[sku] = {
            "description": row["description"].strip(),
            "category": row["category"].strip(),
            "stock_unit": row["unit"].strip(),
        }

    results = []
    for sku, txns in by_sku.items():
        ledger = costing.run_ledger(txns)
        ledger.update({"sku": sku})
        ledger.update(meta[sku])
        results.append(ledger)
    return results


def compute_excise(rows, ytd_hectolitres):
    """Total excise duty by ABV class across the period's packaging events.

    Packaging events are processed in file (chronological) order, threading a
    single cumulative production figure through them so the reduced-rate
    brackets are applied to the right slices of volume.
    """
    cumulative = Decimal(ytd_hectolitres)
    totals = OrderedDict()
    for row in rows:
        if row["txn_type"].strip() != "package":
            continue
        litres = costing.to_litres(
            _decimal(row["quantity"]),
            row["unit"].strip(),
            _decimal(row["litres_per_unit"]),
        )
        hectolitres = costing.litres_to_hectolitres(litres)
        abv_class = row["abv_class"].strip()
        duty, cumulative = costing.excise_for_volume(hectolitres, abv_class, cumulative)
        bucket = totals.setdefault(
            abv_class, {"hectolitres": Decimal("0"), "duty": Decimal("0")}
        )
        bucket["hectolitres"] += hectolitres
        bucket["duty"] += duty
    return totals


def write_perpetual(path, ledgers):
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "sku",
                "description",
                "category",
                "on_hand_qty",
                "stock_unit",
                "wac_unit_cost",
                "inventory_value",
                "integrity_flag",
            ]
        )
        for row in ledgers:
            writer.writerow(
                [
                    row["sku"],
                    row["description"],
                    row["category"],
                    format(row["on_hand_qty"], "f"),
                    row["stock_unit"],
                    format(row["wac_unit_cost"], "f"),
                    format(row["on_hand_value"], "f"),
                    row["integrity_flag"],
                ]
            )


def write_excise(path, totals):
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["abv_class", "hectolitres", "excise_duty"])
        for abv_class, bucket in totals.items():
            writer.writerow(
                [
                    abv_class,
                    format(bucket["hectolitres"].quantize(Decimal("0.01")), "f"),
                    format(costing.money(bucket["duty"]), "f"),
                ]
            )


def main(argv=None):
    parser = argparse.ArgumentParser(description="Brewery inventory costing engine.")
    parser.add_argument("transactions", help="path to the transaction CSV")
    parser.add_argument(
        "--ytd-hl",
        default="0",
        help="total beer (hL, all classes) already brewed this year before this file",
    )
    parser.add_argument(
        "--out-dir", default=".", help="folder to write the two output CSVs into"
    )
    args = parser.parse_args(argv)

    fieldnames, rows = read_transactions(args.transactions)

    errors = validation.validate_header(fieldnames)
    if not errors:
        errors = validation.validate_rows(rows)
    if errors:
        sys.stderr.write("Input rejected. %d problem(s) found:\n" % len(errors))
        for message in errors:
            sys.stderr.write("  - %s\n" % message)
        return 1

    ledgers = build_ledgers(rows)
    excise = compute_excise(rows, args.ytd_hl)

    perpetual_path = "%s/perpetual_valuation.csv" % args.out_dir.rstrip("/")
    excise_path = "%s/excise_summary.csv" % args.out_dir.rstrip("/")
    write_perpetual(perpetual_path, ledgers)
    write_excise(excise_path, excise)

    total_value = sum((row["on_hand_value"] for row in ledgers), Decimal("0"))
    total_duty = sum((costing.money(b["duty"]) for b in excise.values()), Decimal("0"))
    flagged = [row["sku"] for row in ledgers if row["integrity_flag"]]

    print("Processed %d SKUs from %s" % (len(ledgers), args.transactions))
    print("  Total inventory value: $%s" % format(total_value, "f"))
    print("  Total excise duty:     $%s" % format(total_duty, "f"))
    if flagged:
        print("  Integrity flags on:    %s" % ", ".join(flagged))
    print("Wrote %s" % perpetual_path)
    print("Wrote %s" % excise_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
