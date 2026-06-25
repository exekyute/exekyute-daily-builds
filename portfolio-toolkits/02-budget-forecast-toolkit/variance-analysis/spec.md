# Spec: Variance Analysis Report Writer

## Purpose

Compare a forecasted budget against actual expenses, compute the variance for every department, and
write a summary of the departments that exceed budget parameters. This models the monthly variance
review of checking actual results against budgeted targets and reporting the overruns.

## Inputs

- `--budget`: master budget CSV with a `department,category,amount` header. This is the file
  produced by the Multi-Departmental Budget Consolidation tool. Default `data/master_budget.csv`.
- `--actuals`: actual spend CSV with the same `department,category,amount` header.
  Default `data/actuals.csv`.
- `--pct-threshold`: percent over budget that trips a flag. Default `10`.
- `--dollar-threshold`: dollars over budget that trips a flag. Default `5000.00`.
- `--report`: path for the CSV report. Default `variance_report.csv`.

## Validation rules

- Both files must contain the `department`, `category`, and `amount` columns. A missing column is a
  clear, immediate error and the run stops with a non-zero exit code.
- A missing input file is a clear error, not a crash.
- Amounts are read after stripping dollar signs, commas, and whitespace. A row with a blank
  department, a blank category, or an unreadable amount is skipped and counted.
- A duplicate department/category row within a file is summed and counted.
- Thresholds must be numeric.

## Logic

1. Load the budget and the actuals into dictionaries keyed by (department, category).
2. Roll both up to a budget total and an actual total per department.
3. For each department, `variance = actual - budget` (signed) and
   `variance_pct = variance / budget * 100`, both with `Decimal` rounded half up. When budget is
   zero the percentage is reported as not applicable.
4. A department over budget is flagged when it breaches either limit:
   `variance_pct > pct-threshold` OR `variance > dollar-threshold`. The test is strictly greater
   than, so a department sitting exactly on a limit is within parameters.
5. Identify line items present in the budget but missing from the actuals, and unbudgeted line items
   present in the actuals only.

## Outputs

- A markdown table: Department, Budget, Actual, Variance, Variance %, Status.
- A written summary listing every department that exceeds budget parameters, with the reason.
- A findings block: thresholds in force, count flagged, budgeted-but-missing line items, unbudgeted
  line items, duplicates merged, rows skipped.
- A CSV report written to `--report` with the same per-department rows.

## Edge cases

- A department over budget by percentage only (flagged).
- A department over budget by dollars only (flagged).
- A department over budget by both (flagged, with two reasons).
- A department exactly on the threshold (within parameters, not flagged).
- A department under budget (favorable, not flagged).
- A line item in the budget but missing from actuals.
- An unbudgeted line item in actuals only.
- A duplicate actuals row (summed, counted).
- A blank or unreadable actuals row (skipped, counted).
- A file missing a required column (clear error, non-zero exit).

## Sample data design

`data/master_budget.csv` is a copy of the consolidation tool's output. `data/actuals.csv` is seeded
so one run exercises every path:

- Facilities: actual 25300.00 vs budget 23000.00, exactly 10.00% and exactly 2300.00 over. Within
  parameters (boundary case).
- Marketing: actual 7280.00 vs budget 6500.00, 12.00% over but only 780.00 over. Flagged on percent.
- Operations: actual 31000.00 vs budget 25000.00, 24.00% and 6000.00 over. Flagged on both.
- Research: actual 22500.00 vs budget 25000.00. Under budget, favorable.
- Sales: actual 156000.00 vs budget 150000.00, 4.00% but 6000.00 over. Flagged on dollars.
- Sales / Software is budgeted but absent from actuals (missing line item).
- Operations / Software appears in actuals only (unbudgeted spend).
- Research / Lab Supplies appears twice in actuals (duplicate, summed).
- Marketing / Misc has a non-numeric amount in actuals (skipped, counted).

`data/invalid_sample/bad_actuals.csv` has a `spend` column instead of `amount`, for the
missing-column error demo.

## Hand-checked value (cross-tool proof)

The consolidation tool merges two `Operations / Travel` lines (`3200.00` and `1800.00`) into a single
`5000.00` entry in `master_budget.csv`. This tool reads that same file, so the budget it uses for
`Operations / Travel` is `5000.00`, the exact figure the consolidation tool wrote. The two tools
agree on a value that was produced by a merge in the first tool and consumed by the second.

At the department level, the run reports Operations with a budget of `25000.00`. By hand, the
Operations budget lines are `Maintenance 8000.00 + Travel 5000.00 + Utilities 12000.00 = 25000.00`,
which matches the rolled-up budget shown in the table.
