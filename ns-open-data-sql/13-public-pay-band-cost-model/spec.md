# Spec

## Purpose

The workbook turns the published Nova Scotia government pay scales into a
cost model: the pay-band grid by classification and step, the cost of step
progression inside each classification, and a live what-if for an
across-the-board raise. Every key figure in the workbook is a live Excel
formula; a plain-Python recomputation in build.py verifies each one against
expected/key_figures.csv.

## Inputs

- data/raw/ns_government-pay-scales_2026-07-06.csv: the pinned snapshot of the
  full NS Government Pay Scales dataset (all scale periods), pulled from the
  Socrata endpoint documented in SOURCE.md.
- The workbook's one user input: the raise percentage in Model!B5,
  default 2.0%. Verification always pins this input at 2%.

## Cleaning rules

Applied in load_scale() in build.py, in this order:

1. Keep only rows from the latest scale period: rows whose start_date equals
   the maximum start_date in the snapshot (2025-04-01, the period running to
   2026-03-31). Every row in that period carries the Excluded plan type; the
   bargaining-unit scales in the snapshot end in earlier periods, so the
   model covers the current non-union scale.
2. Drop rows with a blank biweekly_pay_rate. The dataset carries a few
   hourly-only records; the model is built on biweekly rates. (The current
   period has none; the build prints the dropped count either way.)
3. Map columns: classification = pay_plan (trimmed), step label =
   int(pay_plan_level), rate = Decimal(biweekly_pay_rate).
4. Integrity checks, each fatal if violated: pay_plan_level must be numeric;
   rates must already be cent-precise; a (classification, step label) pair
   may not appear twice with different rates.
5. Order each classification's steps by pay progression, not by raw label:
   labels 80 and up first (ascending), then the rest (ascending). Thirty-two
   plans in the current period (all seventeen EC and ten LM plans plus the
   five SO plans) number their below-range steps 80 to 99 and continue the
   main range from label 0, so sorting by raw label would put the cheapest
   steps last. Along the progression, rates must not fall; a falling rate is
   fatal.
6. Sort by classification, then progression order inside each
   classification. This fixed order makes every downstream figure, including
   tie-breaks, reproducible.

## Model logic, step by step

1. **Grid pivot.** The cleaned long-format rows (Data sheet) are pivoted onto
   the Model sheet: one row per classification, one column per progression
   step (Step 1 through Step 31, the deepest plan), the published biweekly
   rate at each intersection. Step 1 is each plan's lowest rate; the
   portal's own step labels stay on the Data sheet. A classification with
   fewer steps leaves its trailing cells empty.
2. **Step-progression cost.** For each classification row, live formulas
   derive: Steps (COUNT of the row's rates), First step (MIN), Top step
   (MAX), Span (Top minus First), and One-step cost (Span divided by
   Steps minus 1, rounded to the cent; 0 for single-step classifications).
   MIN and MAX stand in for the first and top step because rule 5 guarantees
   rates never fall along the progression.
3. **Raise what-if.** The Inputs cell Model!B5 holds the raise percentage.
   Each classification's Raise cost is SUMPRODUCT(ROUND(rates * B5, 2)): the
   published rate at every step is raised by the input percentage, each
   raised amount is rounded to the cent, and the rounded amounts are summed.
   The grand total is the plain SUM of the per-classification raise costs, so
   the total ties exactly to the parts. Change B5 and the whole model
   recomputes live.

### The headcount-free assumption

The dataset is the published pay scale, not payroll headcount. Nobody knows
from this data how many employees sit at each step. Raise costs here are
modelled per published rate: the cost of lifting each published step rate by
the input percentage, once. They are not actual payroll cost.

## Cell map of the key figures

All on the Model sheet. expected/key_figures.csv lists the same figures in
the same order.

| Figure (key_figures.csv)     | Cell | Formula                                    |
|------------------------------|------|--------------------------------------------|
| raise_pct                    | B5   | input cell, default 0.02                   |
| classification_count         | B8   | =COUNTA(classification column)             |
| published_rate_count         | B9   | =SUM(Steps column)                         |
| total_biweekly_base          | B10  | =SUM(Base total column)                    |
| raise_total                  | B11  | =SUM(Raise cost column)                    |
| raise_top_classification     | B12  | =INDEX(names,MATCH(MAX(raise),raise,0))    |
| raise_top_cost               | B13  | =MAX(Raise cost column)                    |
| single_step_classifications  | B14  | =COUNTIF(Steps column,1)                   |
| widest_span                  | B15  | =MAX(Span column)                          |
| widest_span_classification   | B16  | =INDEX(names,MATCH(MAX(span),span,0))      |

The grid starts at row 18 (header) with one classification per row below it.
The derived columns (Steps, First step, Top step, Span, One-step cost, Base
total, Raise cost) sit to the right of the step columns.

## Edge cases

- **Single-step classifications.** Span is 0.00 and One-step cost is 0.00 by
  the IF guard; they still carry base and raise costs. Counted in B14. The
  current period has none, so B14 shows 0; the guard stays for future
  snapshots.
- **Wrapped step numbering.** The EC, LM, and SO plans label their
  below-range steps 80 to 99 and their main range from 0. Rule 5 orders
  them by progression, the pivot places them by position, and the
  monotonicity check runs on the progression, so label 80 lands in the
  Step 1 column and label 0 follows label 99 where the rates say it
  belongs.
- **Shorter classifications.** A classification with fewer steps than the
  deepest plan leaves its trailing grid cells empty. COUNT, MIN, MAX, SUM,
  and SUMPRODUCT all ignore empty cells (blanks multiply to 0 inside the
  SUMPRODUCT), so no formula breaks.
- **Hourly-only records.** Rows with a blank biweekly rate are dropped and
  counted; build.py prints the dropped count on every build.
- **Ties.** MATCH finds the first row with the maximum, and rows are sorted
  by classification, so a tie resolves to the alphabetically first
  classification in both Excel and the Python recomputation.

## Determinism and money ties

The snapshot is pinned and committed, row order is fixed by the sort in rule
6, and no step depends on the clock or on randomness. Money in the Python
recomputation rounds with decimal.Decimal and ROUND_HALF_UP, the same
half-away-from-zero rule as Excel's ROUND; Python's built-in round() is never
used. Totals tie exactly because every total is a sum of already-rounded
cent amounts. Verification recomputes all ten key figures with the input
pinned at 2% and diffs them against expected/key_figures.csv; any difference
prints the first mismatch and exits nonzero. The golden file itself was
frozen from a first verified run via the write_expected() helper in build.py.
