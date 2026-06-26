# Spec: QA Test-Case Generator

## Purpose

Generate a structured set of edge-case scenarios for the Benefit Engine, run each one through
the actual engine, and emit both a human-readable markdown table and a machine-readable JSON
file. This is how calculation output gets QA'd after any change to the engine: regenerate the
cases and confirm the expected values still hold.

## Inputs

- Scenario definitions in `scenarios.py`. Each scenario has a name, the salary/service/age
  inputs, a short rationale, and an `expect_error` flag for cases the engine must reject.
- `--out-dir`: optional output folder (default `./output`).

## Logic

1. Add the sibling `benefit-formula-engine` folder to the import path (the folder name contains
   a hyphen, so it cannot be imported normally). This is the one deliberate cross-tool link in
   the toolkit.
2. For each scenario, validate and calculate using the engine's own functions.
   - A normal scenario records the expected monthly payout and a detail line.
   - An `expect_error` scenario succeeds when the engine raises a validation error, and records
     the rejection message.
3. Each result carries a `passed` flag: true when the engine behaved as the scenario expected.

## Outputs

- `output/test_cases.md`: a markdown table of every scenario, its key inputs, the expected
  monthly payout (or "rejected"), the outcome, and why it matters.
- `output/test_cases.json`: the same records as structured JSON, ready to drive an automated
  test suite.
- A console summary listing each scenario and whether it behaved as expected.

## Scenarios covered

- Normal retirement at 65 (baseline, no reduction).
- Early retirement at 55 (maximum reduction).
- Service above the cap (clamped to the maximum).
- Best 5 of many years (averaging window selection).
- Boundary age just below normal (one year of reduction).
- Invalid: negative salary (must be rejected).
- Invalid: age below earliest (must be rejected).

## Cross-check with the engine spec

The "Normal retirement at 65" scenario uses five $100,000 salary years, 30 years of service,
and retirement at 65. The engine spec's worked example gives a monthly payout of $5,000.00. The
generator must produce the same value, which proves the QA tool and the engine agree.
