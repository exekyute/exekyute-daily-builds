# Spec: Multi-Departmental Budget Consolidation Tool

## Purpose

Take a directory of individual departmental budget sheets that arrive in inconsistent formatting,
standardize them, and merge them into one master corporate budget template. This models the routine
work of pulling disparate source files into a single, accurate corporate summary.

## Inputs

- `--departments`: directory of per-department CSV files (default `data/departments`). Each file is
  named for its department (for example `sales.csv` becomes department `Sales`) and has a
  `category,amount` header. Column names are matched case-insensitively and extra columns are ignored.
- `--output`: path for the consolidated master CSV (default `output/master_budget.csv`).

## Validation rules

- The `category` and `amount` columns must both be present. A missing column is a clear, immediate
  error and the run stops with a non-zero exit code.
- Amounts are read after stripping dollar signs, thousands commas, and whitespace. A blank or
  non-numeric amount is skipped and counted, not crashed on.
- A blank category is skipped and counted.
- A duplicate category within one department is summed into a single line and counted as a finding.
  The first value is kept and added to, never silently overwritten.
- Unknown extra columns (for example a `notes` column) are ignored.

## Logic

1. Discover every `.csv` file in the departments directory, sorted by name.
2. For each file, take the department name from the file name and read its category and amount cells.
3. Standardize each row: strip `$`, commas, and whitespace from the amount, parse it as
   `decimal.Decimal`, and round it half up to cents. Normalize the category to Title Case with single
   spaces.
4. Merge duplicate categories within a department by summing their amounts.
5. Sort the merged rows by department, then category.
6. Write the master CSV with a `department,category,amount` header and print a summary.

## Outputs

- A markdown table of the master budget printed to the screen.
- `output/master_budget.csv`, the master template, with amounts in plain fixed-point notation.
- A summary: departments processed, master line items, duplicate lines merged, rows skipped for a
  blank category, rows skipped for an unreadable amount, and the consolidated grand total.

## Edge cases

- Messy money formatting (`$1,200.50`, surrounding whitespace) standardized to a clean Decimal.
- A half-up rounding boundary (`2,999.995` becomes `3000.00`).
- A duplicate category within a department (summed, counted).
- A blank amount (skipped, counted) and a non-numeric amount (skipped, counted).
- A blank category (skipped, counted).
- An extra column the tool does not need (ignored).
- A file missing a required column (clear error, non-zero exit).
- An empty or missing directory (reported, non-zero exit).

## Sample data design

Five synthetic department files under `data/departments` are seeded so a single run exercises every
path:

- `sales.csv` is clean and tidy (a large department budget).
- `marketing.csv` carries messy formatting: `$1,200.50` with a dollar sign and comma, ` 4300 ` with
  whitespace, and mixed-case categories like `EVENTS` and `office supplies` to be normalized.
- `operations.csv` lists `Travel` twice (`3200.00` and `1800.00`), merged into one line of `5000.00`.
- `facilities.csv` has a blank `Security` amount (skipped), an extra `notes` column (ignored), and a
  `Cleaning` value of `2,999.995` that rounds half up to `3000.00`.
- `research.csv` is clean (used later as a favorable, under-budget department in the variance tool).

`data/invalid_sample/broken_budget.csv` has a `total` column instead of `amount`, so it can be used
to demonstrate the missing-column error.

## Hand-checked value (cross-tool proof)

`operations.csv` lists `Travel` twice, as `3200.00` and `1800.00`. By hand, `3200.00 + 1800.00 =
5000.00`. The consolidated master file records `Operations,Travel,5000.00`. The Variance Analysis
tool reads this exact line as the budget for Operations / Travel, so the two tools agree on a value
that was produced by a merge. See the Variance Analysis spec for the matching note.

The full master run totals `229500.00` across 14 line items and 5 departments.
