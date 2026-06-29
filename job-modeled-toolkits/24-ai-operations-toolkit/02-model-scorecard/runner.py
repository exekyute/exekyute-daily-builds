"""Model scorecard runner for the AI operations toolkit.

Builds an in-memory SQLite database from an eval-results CSV and the cost engine's
per-call cost CSV, runs the analytical queries in queries.sql, turns the confusion
counts into accuracy, precision, recall, F1, cost per correct, and a weighted score,
ranks the models, reconciles the per-call costs against the engine, prints it all,
checks every figure against the hand-checked numbers in spec.md, and writes
model_scorecard.csv for the dashboard.

Standard library only: csv, sqlite3, os, sys, decimal. Run it with:

    python runner.py
    python runner.py eval_results_bad.csv
"""

import csv
import os
import sqlite3
import sys
from decimal import Decimal, ROUND_HALF_UP

HERE = os.path.dirname(os.path.abspath(__file__))
SCHEMA_FILE = os.path.join(HERE, "schema.sql")
QUERIES_FILE = os.path.join(HERE, "queries.sql")
DEFAULT_EVAL = os.path.join(HERE, "eval_results.csv")
CALL_COSTS = os.path.join(HERE, "cost_by_call.csv")
SCORECARD_OUT = os.path.join(HERE, "model_scorecard.csv")

LABELS = {"approve", "reject"}

# The weights behind the single score, and the rounding units. Quality counts for
# half, cost for a little under a third, speed for the rest. Quality is the F1 score;
# cost and speed are scaled across the models on the card so the best on each axis
# scores one and the worst scores zero.
WEIGHT_QUALITY = Decimal("0.5")
WEIGHT_COST = Decimal("0.3")
WEIGHT_SPEED = Decimal("0.2")

RATE4 = Decimal("0.0001")
CENT = Decimal("0.01")

# The numbers the sample data is built to produce. A passing run is proof the
# queries and the scoring still behave. See spec.md.
EXPECTED_MODELS = {
    "frontier-large": {
        "accuracy": "0.9000", "precision": "0.8333", "recall": "1.0000", "f1": "0.9091",
        "p50": 1100, "p95": 2000, "cost_cents": 100, "cost_per_correct": "0.1111",
        "score": "45.45", "rank": 3,
    },
    "balanced-mid": {
        "accuracy": "0.8000", "precision": "0.8000", "recall": "0.8000", "f1": "0.8000",
        "p50": 500, "p95": 900, "cost_cents": 40, "cost_per_correct": "0.0500",
        "score": "74.08", "rank": 2,
    },
    "frontier-mini": {
        "accuracy": "0.6000", "precision": "0.6000", "recall": "0.6000", "f1": "0.6000",
        "p50": 250, "p95": 500, "cost_cents": 10, "cost_per_correct": "0.0167",
        "score": "80.00", "rank": 1,
    },
}

EXPECTED_RECON_TOTAL = 77585  # cents, equal to the engine's $775.85 direct grand total
EXPECTED_RECON_BY_TEAM = {
    "DataScience": 12550,
    "Engineering": 54910,
    "Sales": 6619,
    "Support": 3506,
}


def to_cents(text, label):
    """Turn a dollar amount like '10.13' into 1013 whole cents."""
    try:
        value = Decimal(str(text).strip())
    except Exception:
        raise ValueError("%s: %r is not a number" % (label, text))
    return int((value * 100).to_integral_value(rounding=ROUND_HALF_UP))


def load_eval_rows(path):
    """Read and validate the eval CSV. A bad row stops the run with a clear message."""
    required = ["eval_id", "model", "task_type", "gold_label", "predicted_label",
                "latency_ms", "cost_usd"]
    rows = []
    seen = set()
    with open(path, newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        missing = [c for c in required if c not in (reader.fieldnames or [])]
        if missing:
            raise ValueError("Eval file is missing columns: " + ", ".join(missing))
        for line_no, raw in enumerate(reader, start=2):
            row = {c: (raw.get(c) or "").strip() for c in required}
            label = "Eval %s" % (row["eval_id"] or "(missing id) on line %d" % line_no)
            if not row["eval_id"]:
                raise ValueError("%s: eval_id is required" % label)
            if row["eval_id"] in seen:
                raise ValueError("%s: eval_id appears more than once" % label)
            seen.add(row["eval_id"])
            for field in ("gold_label", "predicted_label"):
                if row[field] not in LABELS:
                    raise ValueError(
                        "%s: %s must be approve or reject, got %r"
                        % (label, field, row[field])
                    )
            try:
                latency = int(row["latency_ms"])
            except ValueError:
                raise ValueError("%s: latency_ms must be a whole number" % label)
            if latency <= 0:
                raise ValueError("%s: latency_ms must be greater than zero" % label)
            rows.append((
                row["eval_id"], row["model"], row["task_type"],
                row["gold_label"], row["predicted_label"], latency,
                to_cents(row["cost_usd"], label),
            ))
    if not rows:
        raise ValueError("Eval file is empty")
    return rows


def load_call_costs(path):
    """Read the cost engine's per-call output and convert each cost to cents."""
    rows = []
    with open(path, newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for raw in reader:
            rows.append((
                raw["record_id"], raw["team"], raw["model"],
                to_cents(raw["cost"], "Call %s" % raw.get("record_id", "")),
            ))
    return rows


def build_db(eval_rows, call_rows):
    conn = sqlite3.connect(":memory:")
    with open(SCHEMA_FILE, encoding="utf-8") as handle:
        conn.executescript(handle.read())
    conn.executemany(
        "INSERT INTO eval_results VALUES (?, ?, ?, ?, ?, ?, ?)", eval_rows
    )
    conn.executemany("INSERT INTO call_costs VALUES (?, ?, ?, ?)", call_rows)
    conn.commit()
    return conn


def parse_queries(path):
    """Split queries.sql into named blocks on the '-- name:' markers."""
    blocks = {}
    name = None
    buffer = []
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            if line.strip().startswith("-- name:"):
                if name:
                    blocks[name] = "".join(buffer).strip()
                name = line.strip().split(":", 1)[1].strip()
                buffer = []
            elif name:
                buffer.append(line)
    if name:
        blocks[name] = "".join(buffer).strip()
    return blocks


def run_query(conn, sql):
    cur = conn.execute(sql)
    columns = [d[0] for d in cur.description]
    return columns, cur.fetchall()


def ratio(numerator, denominator, places=RATE4):
    """Exact decimal ratio rounded half up, or zero when the denominator is zero."""
    if denominator == 0:
        return Decimal("0").quantize(places)
    return (Decimal(numerator) / Decimal(denominator)).quantize(places, rounding=ROUND_HALF_UP)


def score_models(matrix_rows, latency_rows):
    """Turn the SQL counts into the per-model metrics and the weighted score.

    matrix_rows are (model, tp, fp, fn, tn, correct, total, cost_cents).
    latency_rows are (model, p50, p95). Returns a list of dicts ordered by rank.
    """
    latency = {r[0]: {"p50": r[1], "p95": r[2]} for r in latency_rows}
    cards = []
    for model, tp, fp, fn, tn, correct, total, cost_cents in matrix_rows:
        f1 = (Decimal(2 * tp) / Decimal(2 * tp + fp + fn)) if (2 * tp + fp + fn) else Decimal("0")
        cost_per_correct = (Decimal(cost_cents) / Decimal(100) / Decimal(correct)) if correct else None
        cards.append({
            "model": model,
            "tp": tp, "fp": fp, "fn": fn, "tn": tn,
            "correct": correct, "total": total,
            "accuracy": ratio(correct, total),
            "precision": ratio(tp, tp + fp),
            "recall": ratio(tp, tp + fn),
            "f1": f1.quantize(RATE4, rounding=ROUND_HALF_UP),
            "f1_exact": f1,
            "p50": latency[model]["p50"],
            "p95": latency[model]["p95"],
            "cost_cents": cost_cents,
            "cost_per_correct": (cost_per_correct.quantize(RATE4, rounding=ROUND_HALF_UP)
                                 if cost_per_correct is not None else None),
            "cpc_exact": cost_per_correct,
        })

    # Scale cost and speed across the models on the card. Lower is better for both,
    # so the cheapest and fastest score one and the priciest and slowest score zero.
    p95s = [c["p95"] for c in cards]
    cpcs = [c["cpc_exact"] for c in cards if c["cpc_exact"] is not None]
    p95_min, p95_max = min(p95s), max(p95s)
    cpc_min, cpc_max = (min(cpcs), max(cpcs)) if cpcs else (Decimal("0"), Decimal("0"))

    for card in cards:
        if p95_max == p95_min:
            speed_norm = Decimal("1")
        else:
            speed_norm = (Decimal(p95_max - card["p95"]) / Decimal(p95_max - p95_min))
        if card["cpc_exact"] is None or cpc_max == cpc_min:
            cost_norm = Decimal("0") if card["cpc_exact"] is None else Decimal("1")
        else:
            cost_norm = (cpc_max - card["cpc_exact"]) / (cpc_max - cpc_min)
        raw = (WEIGHT_QUALITY * card["f1_exact"]
               + WEIGHT_COST * cost_norm
               + WEIGHT_SPEED * speed_norm) * Decimal("100")
        card["score"] = raw.quantize(CENT, rounding=ROUND_HALF_UP)

    cards.sort(key=lambda c: (-c["score"], c["model"]))
    for rank, card in enumerate(cards, start=1):
        card["rank"] = rank
    return cards


def print_scorecard(cards):
    print("\nModel scorecard (ranked, best first)")
    header = "  %-4s %-15s %9s %9s %9s %9s %8s %8s %10s %8s" % (
        "Rank", "Model", "Accuracy", "Precision", "Recall", "F1",
        "p50 ms", "p95 ms", "Cost/corr", "Score",
    )
    print(header)
    print("  " + "-" * (len(header) - 2))
    for c in cards:
        cpc = "$%s" % c["cost_per_correct"] if c["cost_per_correct"] is not None else "n/a"
        print("  %-4d %-15s %9s %9s %9s %9s %8d %8d %10s %8s" % (
            c["rank"], c["model"], c["accuracy"], c["precision"], c["recall"],
            c["f1"], c["p50"], c["p95"], cpc, c["score"],
        ))


def write_scorecard(cards):
    columns = ["rank", "model", "accuracy", "precision", "recall", "f1",
               "p50_latency_ms", "p95_latency_ms", "cost_usd", "cost_per_correct", "score"]
    with open(SCORECARD_OUT, "w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(columns)
        for c in sorted(cards, key=lambda x: x["rank"]):
            cost_usd = (Decimal(c["cost_cents"]) / Decimal(100)).quantize(CENT)
            cpc = c["cost_per_correct"] if c["cost_per_correct"] is not None else ""
            writer.writerow([
                c["rank"], c["model"], c["accuracy"], c["precision"], c["recall"],
                c["f1"], c["p50"], c["p95"], cost_usd, cpc, c["score"],
            ])


def main():
    eval_path = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_EVAL
    if not os.path.isabs(eval_path):
        eval_path = os.path.join(HERE, eval_path)

    print("Model scorecard")
    print("Eval file: " + os.path.basename(eval_path))

    try:
        eval_rows = load_eval_rows(eval_path)
        call_rows = load_call_costs(CALL_COSTS)
    except (OSError, ValueError) as err:
        print("\nInput rejected: " + str(err))
        return 1

    conn = build_db(eval_rows, call_rows)
    queries = parse_queries(QUERIES_FILE)

    _, matrix_rows = run_query(conn, queries["confusion_matrix"])
    _, latency_rows = run_query(conn, queries["latency_percentiles"])
    _, team_rows = run_query(conn, queries["spend_by_team"])
    _, total_rows = run_query(conn, queries["spend_total"])

    cards = score_models(matrix_rows, latency_rows)
    print_scorecard(cards)
    write_scorecard(cards)

    recon_total = total_rows[0][0]
    print("\nSpend reconciliation against the cost engine")
    print("  Grand total: %d cents ($%s)" % (recon_total, Decimal(recon_total) / 100))
    for team, cents in team_rows:
        print("    %-12s %d cents ($%s)" % (team, cents, Decimal(cents) / 100))

    # Checks. Every figure is compared to the hand-checked number in spec.md.
    checks = []
    by_model = {c["model"]: c for c in cards}
    for model, want in EXPECTED_MODELS.items():
        got = by_model.get(model)
        if got is None:
            checks.append(("model %s present" % model, False))
            continue
        checks.append(("%s accuracy" % model, str(got["accuracy"]) == want["accuracy"]))
        checks.append(("%s precision" % model, str(got["precision"]) == want["precision"]))
        checks.append(("%s recall" % model, str(got["recall"]) == want["recall"]))
        checks.append(("%s f1" % model, str(got["f1"]) == want["f1"]))
        checks.append(("%s p50" % model, got["p50"] == want["p50"]))
        checks.append(("%s p95" % model, got["p95"] == want["p95"]))
        checks.append(("%s cost cents" % model, got["cost_cents"] == want["cost_cents"]))
        checks.append(("%s cost/correct" % model,
                       str(got["cost_per_correct"]) == want["cost_per_correct"]))
        checks.append(("%s score" % model, str(got["score"]) == want["score"]))
        checks.append(("%s rank" % model, got["rank"] == want["rank"]))

    checks.append(("reconciled grand total", recon_total == EXPECTED_RECON_TOTAL))
    team_cents = {team: cents for team, cents in team_rows}
    for team, want_cents in EXPECTED_RECON_BY_TEAM.items():
        checks.append(("reconciled %s" % team, team_cents.get(team) == want_cents))

    print("\nChecks")
    ok = True
    for label, passed in checks:
        if not passed:
            ok = False
        print("  [%s] %s" % ("ok" if passed else "MISMATCH", label))

    print("\n" + ("PASS" if ok else "FAIL"))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
