# Spec: Milestone-Driven Burn Rate Tracker

## Purpose

Track how fast a project is spending its grant fund. The tool loads the fixed grant fund and the
consultant spend the ledger already recorded, then applies each project phase cost on top and reports
the running burn rate after every phase. This models monitoring expenditure across project phases and
giving a coordinator an instant read on how much of the fund is left.

## Inputs

- `--budget`: path to the ledger's central budget file (default `data/central_budget.json`, a
  committed snapshot so the tool runs on its own). Point it at the live ledger output with
  `--budget ../multi-currency-ledger/central_budget.json`.
- `--phases`: path to the phase updates CSV with a `phase,cost` header
  (default `data/phase_updates.csv`).
- `--interactive`: enter phases one at a time at the prompt instead of reading the CSV.

The grant fund and the starting spend are never recomputed here. They are read from the central
budget file so this tool and the ledger always agree.

## Validation rules

- The phase file must contain the `phase` and `cost` columns. A missing column is a clear error.
- A phase name must be non-blank. A blank name row is skipped and counted.
- A cost must be numeric and greater than zero. A blank or non-numeric cost is skipped and counted.
- A duplicate phase name is recorded as a finding. The first occurrence is kept; the repeat does not
  change the running total.
- The central budget file must exist and contain `grant_total` and `consultant_spend`. A missing file
  gives a clear message to run the ledger first.

## Logic

1. Load the grant fund and consultant spend from the central budget file.
2. Start the running spend at the consultant spend carried from the ledger.
3. For each phase, validate the name and cost. A failed row is recorded in `skipped`.
4. Add the accepted cost to the running spend with `Decimal` math.
5. After each phase, compute remaining = fund minus spend, and burn rate = spend / fund as a
   percentage, both quantized to two places with half-up rounding.
6. A phase is over fund when the running spend is strictly greater than the grant fund.

## Outputs

- A starting line: grant fund, consultant spend carried from the ledger, and the starting burn rate.
- A markdown table, one row per accepted phase: Phase, Cost, Spent to date, Remaining, Burn rate,
  Status.
- A list of skipped and duplicate findings with the reason for each.
- A final summary: phases applied, final spend, remaining, and final burn rate.

## Edge cases

- A blank or non-numeric cost (row skipped and counted).
- A blank phase name (row skipped and counted).
- A duplicate phase name (recorded, first kept, not double-counted).
- Spend crossing the fund partway through (the status flips to OVER FUND, remaining goes negative).
- A missing central budget file (clear message instead of a crash).

## Sample data design

The included `data/phase_updates.csv` is seeded so a single run exercises every path, starting from
the ledger's 248,600.00 consultant spend against the 250,000.00 grant fund:

- `Inception Report` (500.00) brings spend to 249,100.00, still within fund.
- `Field Survey` (600.00) brings spend to 249,700.00, still within fund.
- `Midterm Review` (800.00) brings spend to 250,500.00, which crosses the fund (the boundary).
- `Field Survey` (300.00) repeats an earlier phase name (duplicate; first kept).
- `Final Audit` has a blank cost (skipped and counted).
- `Closeout` has a non-numeric cost (skipped and counted).

## Cross-tool agreement (hand-checked)

The ledger writes `consultant_spend` of **248,600.00** in `central_budget.json`. This tool loads that
exact figure as its starting spend. Worked by hand:

    burn rate = 248,600.00 / 250,000.00 = 0.99440 = 99.44%

The tool prints `99.44%` as the starting burn rate, which matches the hand calculation and confirms
the two tools agree on the same number. Running this tool with
`--budget ../multi-currency-ledger/central_budget.json` against a freshly generated ledger file
produces the identical starting line.
