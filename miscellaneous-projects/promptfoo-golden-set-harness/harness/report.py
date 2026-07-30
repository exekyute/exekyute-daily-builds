"""Turn a promptfoo results file into an accuracy, consistency, and regression report.

    python harness/report.py runs/offline-baseline.json

Reads the recorded response for every row, rescores it with harness/scoring.py, and
checks the recomputed score against the score promptfoo recorded at eval time. Those two
numbers come from the same rubric down two different paths, so a disagreement means
something is wrong with the harness and the report says so instead of publishing a
number nobody checked.

Gates, for use in CI or a pre-commit check on a prompt change:

    --fail-under 0.90        every model and prompt version must reach that field accuracy
    --fail-on-regression     any case that stopped passing fails the run
"""

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import scoring  # noqa: E402  (path has to be set before the import)

SCORE_TOLERANCE = 1e-9
VERDICT_LABEL = {"pass": "ok", "fail": "FAIL", "unstable": "drift", "missing": "-"}

# promptfoo's failureReason on a result row: 0 none, 1 an assertion failed, 2 the
# provider call itself failed. It matters which: on an assertion failure promptfoo puts
# the grader's reason in the row's top-level `error` field, so reading that field alone
# counts every wrong answer as a broken call.
PROVIDER_ERROR = 2


def load_rows(path):
    """Flatten a promptfoo results file into one dict per model response."""
    with open(path, encoding="utf-8") as handle:
        payload = json.load(handle)
    block = payload.get("results") or {}
    raw_rows = block.get("results")
    if raw_rows is None:
        raise ValueError("%s has no results.results array" % path)

    rows = []
    for raw in raw_rows:
        test_case = raw.get("testCase") or {}
        variables = test_case.get("vars") or raw.get("vars") or {}
        response = raw.get("response") or {}
        provider_error = response.get("error")
        if not provider_error and raw.get("failureReason") == PROVIDER_ERROR:
            provider_error = raw.get("error")
        rows.append(
            {
                "model": (raw.get("provider") or {}).get("label")
                or (raw.get("provider") or {}).get("id")
                or "unknown",
                "version": scoring.version_key((raw.get("prompt") or {}).get("label")),
                "case_id": variables.get("case_id", "unknown"),
                "branch": variables.get("branch", ""),
                "expected": variables.get("expected") or {},
                "output": response.get("output"),
                "error": provider_error,
                "recorded_score": raw.get("score"),
                "recorded_pass": bool(raw.get("success")),
            }
        )
    return payload, rows


def score_rows(rows):
    """Rescore every row and group the results by model, version, and case.

    A row whose provider call failed is counted separately and left out of the metrics.
    A refused or rate-limited call is a run problem, and folding it into accuracy would
    read as a model that got the answer wrong.
    """
    grouped = {}
    integrity = {"checked": 0, "agreed": 0, "disagreements": []}
    errors = []

    for row in rows:
        if row["error"]:
            errors.append(
                {
                    "model": row["model"],
                    "version": row["version"],
                    "case_id": row["case_id"],
                    "message": str(row["error"]),
                }
            )
            continue
        result = scoring.score_case(row["expected"], row["output"])
        result["case_id"] = row["case_id"]
        result["branch"] = row["branch"]
        result["error"] = row["error"]

        recorded = row["recorded_score"]
        if isinstance(recorded, (int, float)):
            integrity["checked"] += 1
            if abs(recorded - result["field_score"]) <= SCORE_TOLERANCE:
                integrity["agreed"] += 1
            else:
                integrity["disagreements"].append(
                    {
                        "model": row["model"],
                        "version": row["version"],
                        "case_id": row["case_id"],
                        "recorded": recorded,
                        "recomputed": result["field_score"],
                    }
                )

        variant = grouped.setdefault((row["model"], row["version"]), {})
        variant.setdefault(row["case_id"], []).append(result)

    return grouped, integrity, errors


def golden_problems(rows):
    """Golden-set defects, checked once per case rather than once per row."""
    seen, problems = set(), []
    for row in rows:
        if row["case_id"] in seen:
            continue
        seen.add(row["case_id"])
        for field, note in scoring.validate_golden(row["expected"]):
            problems.append((row["case_id"], field, note))
    return problems


def table(headers, body, indent="  "):
    """Fixed-width ASCII table. Plain text keeps it readable in any console."""
    columns = [list(headers)] + [[str(cell) for cell in line] for line in body]
    widths = [max(len(line[i]) for line in columns) for i in range(len(headers))]
    lines = [
        indent + "  ".join(str(headers[i]).ljust(widths[i]) for i in range(len(headers))),
        indent + "  ".join("-" * widths[i] for i in range(len(headers))),
    ]
    for line in body:
        lines.append(
            indent + "  ".join(str(line[i]).ljust(widths[i]) for i in range(len(headers)))
        )
    return "\n".join(lines)


def pct(value):
    return "%.1f%%" % (value * 100)


def build_summaries(grouped):
    return {variant: scoring.summarize_variant(cases) for variant, cases in grouped.items()}


def print_header(payload, models, versions, cases, scored, errored):
    meta = payload.get("metadata") or {}
    options = payload.get("runtimeOptions") or {}
    lines = [
        ("eval id", payload.get("evalId", "unknown")),
        ("run at", meta.get("evaluationCreatedAt", "unknown")),
        ("promptfoo", meta.get("promptfooVersion", "unknown")),
        ("golden cases", str(len(cases))),
        ("prompt versions", ", ".join(versions)),
        ("models", ", ".join(models)),
        ("repeats per case", str(options.get("repeat", 1))),
        ("responses scored", str(scored)),
    ]
    if errored:
        lines.append(("provider errors", str(errored)))
    width = max(len(label) for label, _ in lines)
    print("Golden-set evaluation report")
    print("=" * 78)
    for label, value in lines:
        print("  %s : %s" % (label.ljust(width), value))


def print_metrics(summaries, models, versions):
    print("\nAccuracy, abstention, and consistency")
    body = []
    for model in models:
        for version in versions:
            summary = summaries.get((model, version))
            if summary is None:
                continue
            body.append(
                [
                    model,
                    version,
                    pct(summary["field_accuracy"]),
                    "%d/%d" % (summary["fields_matched"], summary["fields_total"]),
                    pct(summary["case_pass_rate"]),
                    pct(summary["hallucination_rate"]),
                    "%d/%d" % (summary["fabricated_fields"], summary["null_fields"]),
                    pct(summary["consistency"]),
                    str(summary["parse_errors"]),
                ]
            )
    print(
        table(
            [
                "model",
                "prompt",
                "field acc",
                "fields",
                "case pass",
                "fabricated",
                "count",
                "consistency",
                "unparsed",
            ],
            body,
        )
    )
    print("    field acc   fraction of golden fields matched after normalization")
    print("    case pass   fraction of responses right on all nine fields")
    print("    fabricated  share of absent fields the model filled in anyway")
    print("    consistency mean agreement across repeats of the same case")


def print_grid(grouped, summaries, models, versions, cases, branches):
    print("\nPer-case verdicts (ok = right on every repeat, drift = right on some)")
    headers = ["case", "branch"] + ["%s %s" % (m, v) for m in models for v in versions]
    body = []
    for case_id in cases:
        line = [case_id, branches.get(case_id, "")]
        for model in models:
            for version in versions:
                summary = summaries.get((model, version)) or {}
                verdict = (summary.get("verdicts") or {}).get(case_id, "missing")
                line.append(VERDICT_LABEL.get(verdict, verdict))
        body.append(line)
    print(table(headers, body))


def print_misses(grouped, models, versions):
    """Every field that missed, grouped so a repeated failure reads as one line."""
    tally = {}
    for (model, version), cases in grouped.items():
        for case_id, results in cases.items():
            for result in results:
                if result["parse_error"]:
                    key = (case_id, "(whole response)", "did not parse as JSON")
                    tally.setdefault(key, set()).add("%s %s" % (model, version))
                    continue
                for field, detail in result["fields"].items():
                    if detail["match"]:
                        continue
                    if not detail["present"]:
                        note = "field omitted"
                    elif detail["hallucinated"]:
                        note = "fabricated %s over an absent value" % (detail["actual"],)
                    else:
                        note = "got %s, expected %s" % (detail["actual"], detail["expected"])
                    tally.setdefault((case_id, field, note), set()).add(
                        "%s %s" % (model, version)
                    )

    if not tally:
        print("\nNo field misses.")
        return
    print("\nField misses")
    body = [
        [case_id, field, note, ", ".join(sorted(who))]
        for (case_id, field, note), who in sorted(tally.items())
    ]
    print(table(["case", "field", "what happened", "where"], body))


def print_movement(summaries, models, versions, branches):
    """Case-level movement between the first and last prompt version, per model."""
    if len(versions) < 2:
        print("\nOnly one prompt version in this run, so there is nothing to compare.")
        return {}
    base, latest = versions[0], versions[-1]
    print("\nPrompt change %s to %s" % (base, latest))
    movement, body = {}, []
    for model in models:
        before = (summaries.get((model, base)) or {}).get("verdicts") or {}
        after = (summaries.get((model, latest)) or {}).get("verdicts") or {}
        if not before or not after:
            continue
        delta = scoring.compare_versions(before, after)
        movement[model] = delta
        body.append(
            [
                model,
                str(len(delta["fixes"])),
                ", ".join(item["case_id"] for item in delta["fixes"]) or "none",
                str(len(delta["regressions"])),
                ", ".join(item["case_id"] for item in delta["regressions"]) or "none",
            ]
        )
    print(table(["model", "fixed", "cases fixed", "broke", "cases broken"], body))

    regressed = sorted(
        {item["case_id"] for delta in movement.values() for item in delta["regressions"]}
    )
    if regressed:
        print("\n  Cases that stopped passing:")
        for case_id in regressed:
            models_hit = sorted(
                model
                for model, delta in movement.items()
                if any(item["case_id"] == case_id for item in delta["regressions"])
            )
            print(
                "    %s (%s) now failing on %s"
                % (case_id, branches.get(case_id, ""), ", ".join(models_hit))
            )
    return movement


def print_integrity(integrity, errors):
    print("\nHarness integrity")
    if integrity["checked"] == 0:
        print("  no promptfoo scores recorded, nothing to cross-check")
    elif not integrity["disagreements"]:
        print(
            "  %d of %d rescored responses match the score promptfoo recorded"
            % (integrity["agreed"], integrity["checked"])
        )
    else:
        print(
            "  %d of %d match, %d disagree:"
            % (integrity["agreed"], integrity["checked"], len(integrity["disagreements"]))
        )
        for item in integrity["disagreements"][:10]:
            print(
                "    %s %s %s: promptfoo %.4f, recomputed %.4f"
                % (
                    item["model"],
                    item["version"],
                    item["case_id"],
                    item["recorded"],
                    item["recomputed"],
                )
            )
    if errors:
        print(
            "  %d response(s) left out of the metrics because the provider call failed:"
            % len(errors)
        )
        for item in errors[:5]:
            print(
                "    %s %s %s: %s"
                % (item["model"], item["version"], item["case_id"], item["message"])
            )
        if len(errors) > 5:
            print("    and %d more" % (len(errors) - 5))


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Score a promptfoo run for accuracy, consistency, and regressions."
    )
    parser.add_argument("results", help="path to a promptfoo JSON results file")
    parser.add_argument(
        "--fail-under",
        type=float,
        default=None,
        metavar="RATE",
        help="exit 1 if any model and prompt version scores below this field accuracy",
    )
    parser.add_argument(
        "--fail-on-regression",
        action="store_true",
        help="exit 1 if any case stopped passing between the first and last version",
    )
    parser.add_argument(
        "--json", dest="json_path", default=None, help="also write the metrics as JSON"
    )
    args = parser.parse_args(argv)

    try:
        payload, rows = load_rows(args.results)
    except (OSError, ValueError) as problem:
        print("Could not read %s: %s" % (args.results, problem))
        return 2
    if not rows:
        print("No rows in %s" % args.results)
        return 2

    problems = golden_problems(rows)
    grouped, integrity, errors = score_rows(rows)
    summaries = build_summaries(grouped)

    models = sorted({model for model, _ in grouped})
    versions = sorted({version for _, version in grouped})
    cases = sorted({row["case_id"] for row in rows})
    branches = {row["case_id"]: row["branch"] for row in rows}

    scored = sum(len(results) for cases_ in grouped.values() for results in cases_.values())
    print_header(payload, models, versions, cases, scored, len(errors))

    print("\nGolden set")
    if problems:
        print("  %d defect(s) in the golden set itself:" % len(problems))
        for case_id, field, note in problems:
            print("    %s %s: %s" % (case_id, field, note))
        print("  Fix the golden set before reading any score below.")
    else:
        print("  %d cases checked, every golden value normalizes cleanly" % len(cases))

    print_metrics(summaries, models, versions)
    print_grid(grouped, summaries, models, versions, cases, branches)
    print_misses(grouped, models, versions)
    movement = print_movement(summaries, models, versions, branches)
    print_integrity(integrity, errors)

    if args.json_path:
        export = {
            "evalId": payload.get("evalId"),
            "variants": [
                {
                    "model": model,
                    "prompt": version,
                    "field_accuracy": summary["field_accuracy"],
                    "case_pass_rate": summary["case_pass_rate"],
                    "hallucination_rate": summary["hallucination_rate"],
                    "consistency": summary["consistency"],
                    "unstable_cases": summary["unstable_cases"],
                    "parse_errors": summary["parse_errors"],
                }
                for (model, version), summary in sorted(summaries.items())
            ],
            "regressions": {
                model: delta["regressions"] for model, delta in movement.items()
            },
            "golden_problems": [
                {"case_id": case_id, "field": field, "note": note}
                for case_id, field, note in problems
            ],
            "integrity": {
                "checked": integrity["checked"],
                "agreed": integrity["agreed"],
                "disagreements": integrity["disagreements"],
            },
        }
        with open(args.json_path, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(export, handle, indent=2)
            handle.write("\n")
        print("\nMetrics written to %s" % args.json_path)

    failures = []
    if problems:
        failures.append("%d golden-set defect(s)" % len(problems))
    if integrity["disagreements"]:
        failures.append("%d score disagreement(s)" % len(integrity["disagreements"]))
    if args.fail_under is not None:
        below = [
            "%s %s at %s" % (model, version, pct(summary["field_accuracy"]))
            for (model, version), summary in sorted(summaries.items())
            if summary["field_accuracy"] < args.fail_under
        ]
        if below:
            failures.append(
                "below the %s gate: %s" % (pct(args.fail_under), "; ".join(below))
            )
    if args.fail_on_regression:
        regressed = sum(len(delta["regressions"]) for delta in movement.values())
        if regressed:
            failures.append("%d case regression(s)" % regressed)

    print()
    if failures:
        print("FAIL: %s" % "; ".join(failures))
        return 1
    print("PASS: golden set clean, scores reconciled, no gate breached")
    return 0


if __name__ == "__main__":
    sys.exit(main())
