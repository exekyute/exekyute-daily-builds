# WIP refresh macro

## Purpose
An Excel macro that sorts the WIP Schedule sheet in place by a column the user
chooses, then reports how many jobs are underbilled, overbilled, and even. It is
the kind of one-click tidy a project accountant runs after opening the workbook.

## Inputs
The `wip_workbook.xlsx` produced by the workbook tool in `02`, open in Excel with
the `WipRefresh` module imported. The macro reads one choice from the user through
an input box: BILLING, EARNED, or PROFIT.

## Validation rules
- If the workbook has no sheet named `WIP Schedule`, the macro shows a message and
  stops.
- If the schedule has no job rows, the macro shows a message and stops.
- If the user enters anything other than BILLING, EARNED, or PROFIT, the macro
  shows a message naming the valid keys and stops without sorting.
- An empty entry (the user cancels the input box) stops quietly.

## Logic
1. Find the WIP Schedule sheet and the last job row by walking down column A until
   the Total row or a blank cell.
2. Read the sort choice and map it to a column: BILLING to the over/under column,
   EARNED to earned revenue, PROFIT to gross profit to date.
3. Sort the job rows (not the header or the Total row) by that column, ascending,
   so the most overbilled jobs sort to the top when sorting by billing.
4. Count the jobs in each billing position by reading the status column and show
   the totals in a message box.

The calculation logic (which keys are valid, where the last row is) is kept in its
own functions, separate from the sub that reads and writes cells, the same way the
Python tools separate logic from plumbing.

## Outputs
The WIP Schedule sheet re-sorted in place, with the red and green shading following
the rows, and a message box summarizing the job counts. The macro does not write
new numbers; the schedule's formulas recompute as Excel moves the rows.

## Edge cases
Running the macro on a workbook without the WIP Schedule sheet, on an empty
schedule, or with an unrecognized sort key each produces a clear message and no
sort. Sorting by billing puts the most overbilled jobs first, which is the review
order a project accountant wants.

### Why the hand-check lives elsewhere
This machine cannot run Excel VBA, so this macro is written to be read and is not
executed here. The to-the-cent proof lives in the Python engine and the workbook
verifier in `01` and `02`, which run on this machine and agree to the cent. This
macro only reorders rows and counts them, so it carries no figure that needs a
hand-check.

## Manual test steps
1. Build the workbook: run `02/build_workbook.py`, then open `wip_workbook.xlsx`
   in Excel.
2. Open the VBA editor (Alt+F11), choose File then Import File, and import
   `WipRefresh.bas`.
3. Put the cursor on the WIP Schedule sheet, press Alt+F8, select
   `SortWipSchedule`, and run it. Enter BILLING. Expect the jobs to reorder with
   the most overbilled first and a message box reading Underbilled: 2,
   Overbilled: 3, Even: 1.
4. Run it again and enter SUPPLIES. Expect the message that it is not a sort key,
   and the schedule unchanged. This is the invalid-input screenshot.
