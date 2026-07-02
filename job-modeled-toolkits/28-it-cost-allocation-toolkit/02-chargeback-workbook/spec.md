# Chargeback workbook builder and verifier

## Purpose
Turns the engine's allocation matrix into a formatted Excel workbook a finance analyst
can open and change. The allocation cells are live formulas, so changing a department's
driver recomputes the whole split. A verifier then proves the workbook's formulas
reproduce the engine's allocation to the cent.

## Inputs
`allocation_matrix.csv`, written by the allocation engine in `01`: one row per
department with its driver, its share of each cost item, and its total.

## Validation rules
The builder expects the matrix the engine writes. The verifier is the check on this
tool: it loads the workbook and the matrix and reports any cell that does not match.

## Logic
Build:

1. Write an Allocation sheet. A pool-amount row holds the total driver and each item
   amount (the column totals). Each department row holds its driver value as a number
   and a live formula for its share of each item, `=ROUND(item*driver/total_driver, 2)`,
   plus a row total. A totals row sums each column.
2. Write a Dashboard sheet with the pool total, the allocated total, the department
   count, and each department's chargeback, with cross-sheet formulas.

Verify:

1. Read the allocation matrix as the expected numbers.
2. Open the workbook and confirm each pool amount matches the engine's column total.
3. For each allocation cell, confirm it holds the formula it should, then compute that
   formula straight from the workbook's own pool and driver cells and confirm the result
   equals the engine's allocation to the cent. The computation runs through a small
   formula evaluator (`formula_eval.py`), not Excel and not the engine.
4. Confirm the totals row and the Dashboard add up to the pool.

Money is rounded half up to the cent.

## Outputs
`chargeback_workbook.xlsx` with an Allocation sheet and a Dashboard sheet. The verifier
prints a line per department and a PASS or FAIL summary, and exits non-zero on a mismatch.

## Edge cases
The verifier checks every department-and-item cell, the row and column totals, and the
dashboard, so a wrong formula anywhere is caught. Because the sample drivers divide the
pool evenly, the workbook's simple rounded formula ties to the engine exactly; the
engine's largest-remainder handling of an uneven split is covered by its own tests.

### Hand-checked example
Engineering's cloud-hosting cell holds `=ROUND(C$2*$B3/$B$2,2)`. Computed from its
cells, 60,000 * 40 / 100 is 24,000.00, and Engineering's row total is 40,000.00. These
match the engine's matrix to the cent, and the verifier confirms it across all 50 checks.

## Dependency
This tool uses `openpyxl` (see `requirements.txt`). The engine in `01` uses no
third-party packages.
