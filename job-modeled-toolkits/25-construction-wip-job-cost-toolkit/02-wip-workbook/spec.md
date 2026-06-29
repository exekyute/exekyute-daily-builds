# WIP workbook builder and verifier

## Purpose
Turns the engine's schedule CSV into a formatted Excel workbook a project
accountant can open, read, and change. The derived columns are live formulas, so
editing a job's cost or contract value recomputes its row. A verifier then proves
the workbook's formulas reproduce the engine's numbers to the cent.

## Inputs
`wip_schedule.csv`, the file written by the job-cost engine in `01`, with one row
per job and the columns it produces (job_id, job_name, the four input numbers, and
the derived percent_complete, earned_revenue, cost_to_complete,
estimated_gross_profit, gross_profit_to_date, over_under_billing, and status).

## Validation rules
The builder expects the schedule CSV the engine writes and stops with a message if
the file is empty. The engine has already validated every job, so the builder's
job is layout, not revalidation. The verifier is the check on this tool: it loads
the workbook and the schedule and reports any cell that does not match.

## Logic
Build:

1. Write a WIP Schedule sheet. Columns A and B hold the job id and name, columns C
   to F hold the four input numbers as values, and columns G to M hold live Excel
   formulas:
   - Percent complete `=ROUND(cost/estimate,4)`
   - Earned revenue `=ROUND(contract*cost/estimate,2)`
   - Cost to complete `=estimate-cost`
   - Estimated gross profit `=contract-estimate`
   - Gross profit to date `=earned-cost`
   - Over/under billing `=earned-billed`
   - Status `=IF(over_under>0,"Underbilled",IF(over_under<0,"Overbilled","Even"))`
2. Add a totals row that sums each money column and takes the cost-weighted
   aggregate percent complete.
3. Shade the over/under column: soft red where a job is overbilled, soft green
   where it is underbilled.
4. Write a Dashboard sheet that totals the schedule and counts jobs by billing
   position, with cross-sheet formulas that reference the WIP Schedule.

Verify:

1. Read the schedule CSV as the expected numbers.
2. Open the workbook and confirm every input cell matches the schedule.
3. For each derived cell, confirm it holds the exact formula it should, then
   compute that formula straight from the workbook's own input cells and confirm
   the result equals the engine's figure to the cent. The computation runs through
   a small formula evaluator (`formula_eval.py`), not Excel and not the engine, so
   it is an independent check.
4. Confirm the totals row and the Dashboard cells add up to the schedule.

Money is rounded half up to the cent. Percent complete is rounded to four places.

## Outputs
`wip_workbook.xlsx` with two sheets, WIP Schedule and Dashboard. The verifier
prints a PASS or FAIL line per section and exits non-zero if anything disagrees.

## Edge cases
The schedule covers underbilled, overbilled, even, completed, and not-started
jobs, so the workbook exercises the green shading, the red shading, and the zero
case, and the status formula returns all three labels. The verifier follows the
chain where one formula references another (over/under reads the earned-revenue
cell, which reads the input cells), so a wrong formula anywhere in the chain is
caught.

### Hand-checked example
For job J-1001 the workbook's earned-revenue cell holds
`=ROUND(C2*E2/D2,2)`. Computed from its input cells, 1,200,000 * 480,000 / 800,000
rounded to the cent is 720,000.00, and the over/under cell `=H2-F2` is
720,000.00 - 700,000.00 = 20,000.00, underbilled. These match the engine's
schedule to the cent, and the verifier confirms it along with all 141 checks
across the workbook.

## Dependency
This tool uses `openpyxl` to write and read the `.xlsx` (see `requirements.txt`).
The engine in `01` and the macro in `03` use no third-party packages.
