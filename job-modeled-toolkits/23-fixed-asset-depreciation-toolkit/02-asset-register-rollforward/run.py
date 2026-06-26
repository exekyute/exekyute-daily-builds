"""Asset register rollforward runner.

Builds an in-memory SQLite database from the asset register and opening UCC,
runs the rollforward queries in queries.sql to derive opening, additions,
disposals, and asset counts per CCA class, then applies the half-year rule and
the class rate with decimal rounding to get CCA and closing UCC. It reconciles
every figure against per_class_cca.csv produced by the depreciation engine in
../01-cca-depreciation-engine and prints PASS or FAIL.

Standard library only: csv, sqlite3, decimal, os, sys. Run it with:

    python run.py
    python run.py --assets sample_assets.csv --opening opening_ucc.csv

Money is stored in the database as integer cents to keep the aggregation exact.
The runner converts to decimal dollars and rounds CCA half up to the cent, the
same rule the engine uses, which is why the two tie out.
"""

import argparse
import csv
import os
import sqlite3
import sys
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation

HERE = os.path.dirname(os.path.abspath(__file__))
SCHEMA_FILE = os.path.join(HERE, "schema.sql")
QUERIES_FILE = os.path.join(HERE, "queries.sql")
DEFAULT_ASSETS = os.path.join(HERE, "sample_assets.csv")
DEFAULT_OPENING = os.path.join(HERE, "opening_ucc.csv")
DEFAULT_ENGINE = os.path.join(HERE, "per_class_cca.csv")
DEFAULT_YEAR = 2026

CENT = Decimal("0.01")

ASSET_COLUMNS = [
    "asset_id", "description", "cca_class", "capital_cost", "in_service_date",
    "useful_life_years", "salvage_value", "disposed", "disposal_proceeds",
    "prior_accum_book_dep",
]

# Figures the rollforward must reproduce, from spec.md, in cents.
EXPECTED = {
    "8": {"cca": 250000, "closing": 1250000},
    "10": {"recapture": 300000},
    "50": {"terminal_loss": 90000},
}

RECONCILED_FIELDS = [
    "opening_ucc", "additions", "disposals", "half_year_adjustment",
    "cca", "recapture", "terminal_loss", "closing_ucc",
]


def q(value):
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


def dollars_to_cents(text):
    amount = Decimal(str(text).strip()).quantize(CENT, rounding=ROUND_HALF_UP)
    return int(amount * 100)


def cents_to_dollars(cents):
    sign = "-" if cents < 0 else ""
    cents = abs(cents)
    return "%s%d.%02d" % (sign, cents // 100, cents % 100)


def load_opening(path):
    rows = []
    with open(path, newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for raw in reader:
            cca_class = (raw.get("cca_class") or "").strip()
            if not cca_class:
                raise ValueError("an opening UCC row has no cca_class")
            try:
                cents = dollars_to_cents(raw.get("opening_ucc"))
            except (InvalidOperation, ValueError):
                raise ValueError("opening UCC for class %s is not a number" % cca_class)
            if cents < 0:
                raise ValueError("opening UCC for class %s cannot be negative" % cca_class)
            rows.append((cca_class, cents))
    return rows


def load_assets(path):
    rows = []
    with open(path, newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        missing = [c for c in ASSET_COLUMNS if c not in (reader.fieldnames or [])]
        if missing:
            raise ValueError("register is missing required columns: " + ", ".join(missing))
        for raw in reader:
            asset_id = (raw.get("asset_id") or "").strip() or "(missing id)"
            cca_class = (raw.get("cca_class") or "").strip()
            disposed_raw = (raw.get("disposed") or "").strip().upper()
            if disposed_raw not in ("Y", "N"):
                raise ValueError("asset %s: disposed must be Y or N" % asset_id)
            disposed = 1 if disposed_raw == "Y" else 0
            try:
                cost = dollars_to_cents(raw.get("capital_cost"))
                proceeds = dollars_to_cents(raw.get("disposal_proceeds") or "0")
            except (InvalidOperation, ValueError):
                raise ValueError("asset %s: capital_cost or disposal_proceeds is not a number" % asset_id)
            if cost < 0:
                raise ValueError("asset %s: capital_cost cannot be negative" % asset_id)
            rows.append((
                asset_id,
                (raw.get("description") or "").strip(),
                cca_class,
                cost,
                (raw.get("in_service_date") or "").strip(),
                disposed,
                proceeds,
            ))
    return rows


def build_db(assets, opening):
    conn = sqlite3.connect(":memory:")
    with open(SCHEMA_FILE, encoding="utf-8") as handle:
        conn.executescript(handle.read())
    known = {row[0] for row in conn.execute("SELECT cca_class FROM cca_classes")}

    for cca_class, cents in opening:
        if cca_class not in known:
            raise ValueError("opening UCC names unknown CCA class %r" % cca_class)
        conn.execute(
            "INSERT INTO opening_ucc (cca_class, opening_ucc_cents) VALUES (?, ?)",
            (cca_class, cents),
        )
    for row in assets:
        if row[2] not in known:
            raise ValueError("asset %s names unknown CCA class %r" % (row[0], row[2]))
        conn.execute(
            "INSERT INTO assets (asset_id, description, cca_class, capital_cost_cents, "
            "in_service_date, disposed, disposal_proceeds_cents) VALUES (?, ?, ?, ?, ?, ?, ?)",
            row,
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


def roll_class(rate, opening, additions, disposals, assets_remaining):
    """Apply the CCA rules to one class. Decimal dollars in, decimal dollars out.

    This reimplements the pool rules independently of the engine so the
    reconciliation is a genuine cross-check, not the same code run twice.
    """
    ucc_before = opening + additions - disposals
    recapture = Decimal("0.00")
    terminal_loss = Decimal("0.00")
    half = Decimal("0.00")
    base = Decimal("0.00")
    cca = Decimal("0.00")

    if ucc_before < Decimal("0"):
        recapture = q(-ucc_before)
        closing = Decimal("0.00")
    elif assets_remaining == 0 and ucc_before > Decimal("0"):
        terminal_loss = q(ucc_before)
        closing = Decimal("0.00")
    else:
        net_additions = additions - disposals
        if net_additions > Decimal("0"):
            half = q(net_additions / Decimal("2"))
        base = q(ucc_before - half)
        cca = q(rate * base)
        closing = q(ucc_before - cca)

    return {
        "opening_ucc": q(opening),
        "additions": q(additions),
        "disposals": q(disposals),
        "half_year_adjustment": half,
        "cca": cca,
        "recapture": recapture,
        "terminal_loss": terminal_loss,
        "closing_ucc": closing,
    }


def fetch(conn, query, params=None):
    cur = conn.execute(query, params or {})
    names = [d[0] for d in cur.description]
    return [dict(zip(names, record)) for record in cur.fetchall()]


def print_rollforward(rows):
    columns = ["class", "opening", "additions", "disposals", "CCA", "recapture", "terminal", "closing"]
    print("\nCCA rollforward by class")
    print("  " + " | ".join("%-10s" % c for c in columns))
    print("  " + "-+-".join("-" * 10 for _ in columns))
    for r in rows:
        cells = [
            r["cca_class"],
            cents_to_dollars(r["opening_ucc_cents"]),
            cents_to_dollars(r["additions_cents"]),
            cents_to_dollars(r["disposals_cents"]),
            str(r["roll"]["cca"]),
            str(r["roll"]["recapture"]),
            str(r["roll"]["terminal_loss"]),
            str(r["roll"]["closing_ucc"]),
        ]
        print("  " + " | ".join("%-10s" % c for c in cells))


def print_disposals(rows):
    print("\nDisposal detail (amount taken against the pool is the lesser of proceeds and cost)")
    print("  %-8s %-6s %12s %12s %12s" % ("asset", "class", "proceeds", "cost", "taken"))
    for r in rows:
        print("  %-8s %-6s %12s %12s %12s" % (
            r["asset_id"], r["cca_class"],
            cents_to_dollars(r["proceeds_cents"]),
            cents_to_dollars(r["cost_cents"]),
            cents_to_dollars(r["taken_cents"]),
        ))


def load_engine_csv(path):
    by_class = {}
    with open(path, newline="", encoding="utf-8") as handle:
        for raw in csv.DictReader(handle):
            by_class[raw["cca_class"].strip()] = raw
    return by_class


def main(argv=None):
    parser = argparse.ArgumentParser(description="CCA asset register rollforward.")
    parser.add_argument("--assets", default=DEFAULT_ASSETS)
    parser.add_argument("--opening", default=DEFAULT_OPENING)
    parser.add_argument("--engine", default=DEFAULT_ENGINE, help="engine per_class_cca.csv to reconcile against")
    parser.add_argument("--year", type=int, default=DEFAULT_YEAR)
    args = parser.parse_args(argv)

    for name, path in (("assets", args.assets), ("opening", args.opening)):
        if not os.path.isabs(path):
            setattr(args, name, os.path.join(HERE, path))

    print("Asset register rollforward, tax year %d" % args.year)
    print("Reading: %s" % os.path.basename(args.assets))

    try:
        assets = load_assets(args.assets)
        opening = load_opening(args.opening)
        conn = build_db(assets, opening)
    except (OSError, ValueError) as err:
        print("\nInput rejected: %s" % err)
        return 1

    queries = parse_queries(QUERIES_FILE)
    rollforward = fetch(conn, queries["class_rollforward"], {"year": str(args.year)})
    disposals = fetch(conn, queries["disposal_detail"])

    for r in rollforward:
        rate = Decimal(r["rate"])
        r["roll"] = roll_class(
            rate,
            Decimal(r["opening_ucc_cents"]) / 100,
            Decimal(r["additions_cents"]) / 100,
            Decimal(r["disposals_cents"]) / 100,
            r["assets_remaining"],
        )

    print_rollforward(rollforward)
    print_disposals(disposals)

    ok = True
    checks = []

    # The pool identity must hold for every class.
    for r in rollforward:
        roll = r["roll"]
        ucc_before = roll["opening_ucc"] + roll["additions"] - roll["disposals"]
        if roll["recapture"] > Decimal("0.00") or roll["terminal_loss"] > Decimal("0.00"):
            identity = roll["closing_ucc"] == Decimal("0.00")
        else:
            identity = roll["closing_ucc"] == q(ucc_before - roll["cca"])
        if not identity:
            ok = False
    checks.append(("pool identity opening + additions - disposals - CCA = closing holds for all classes",
                   all(True for _ in rollforward) and ok))

    # Reconcile every field against the engine output, to the cent.
    try:
        engine = load_engine_csv(args.engine)
    except OSError:
        print("\nInput rejected: engine file %s not found; run the engine first." % os.path.basename(args.engine))
        return 1

    recon_ok = True
    mismatches = []
    for r in rollforward:
        cca_class = r["cca_class"]
        if cca_class not in engine:
            recon_ok = False
            mismatches.append("class %s missing from engine output" % cca_class)
            continue
        for field in RECONCILED_FIELDS:
            got = r["roll"][field]
            want = Decimal(engine[cca_class][field])
            if got != want:
                recon_ok = False
                mismatches.append("class %s %s: rollforward %s vs engine %s" % (cca_class, field, got, want))
    if not recon_ok:
        ok = False
    checks.append(("rollforward reconciles to the engine per_class_cca.csv to the cent", recon_ok))

    # The headline figures from spec.md.
    by_class = {r["cca_class"]: r["roll"] for r in rollforward}
    headline_ok = (
        int(by_class["8"]["cca"] * 100) == EXPECTED["8"]["cca"]
        and int(by_class["8"]["closing_ucc"] * 100) == EXPECTED["8"]["closing"]
        and int(by_class["10"]["recapture"] * 100) == EXPECTED["10"]["recapture"]
        and int(by_class["50"]["terminal_loss"] * 100) == EXPECTED["50"]["terminal_loss"]
    )
    if not headline_ok:
        ok = False
    checks.append(("worked example: class 8 CCA 2500.00 / closing 12500.00, "
                   "class 10 recapture 3000.00, class 50 terminal loss 900.00", headline_ok))

    print("\nChecks")
    for label, passed in checks:
        print("  [%s] %s" % ("ok" if passed else "MISMATCH", label))
    for note in mismatches:
        print("    - " + note)

    print("\n" + ("PASS" if ok else "FAIL"))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
