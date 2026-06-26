# Maturity Ladder

## Purpose
Sorts a list of debts and obligations into weekly rungs from an as-of date, so a treasury analyst
can see how much cash has to go out in each of the next 13 weeks, where the heavy weeks are, and
what is already past due. The weekly totals feed the Liquidity Forecast.

## Inputs
An obligations CSV, chosen with the file picker. Header row, then one row per obligation. All
amounts are Canadian dollars.

| Column | Type | Meaning |
| --- | --- | --- |
| `obligation_id` | text, not blank, unique | id of the obligation, e.g. `OB-1001` |
| `counterparty` | text, not blank | who is owed, e.g. `BMO Term Loan` |
| `type` | text, not blank | kind of obligation, e.g. `loan_principal`, `lease`, `tax_remittance` |
| `due_date` | text, `YYYY-MM-DD` | date the amount is due |
| `amount` | number, 0 or more, up to 2 decimals | amount due |

Two settings on the page:

- As-of date, the start of week 1 (default `2026-06-15`).
- Concentration threshold in dollars, the line above which a week is flagged heavy (default 50000).

## Validation rules
- The header must be exactly `obligation_id,counterparty,type,due_date,amount`, or the file is rejected.
- Every data row must have exactly 5 fields, or it names the row and the count.
- `obligation_id` must not be blank and must be unique. A repeat is rejected as a duplicate, named by row.
- `counterparty` and `type` must not be blank.
- `due_date` must be a real calendar date in `YYYY-MM-DD` form.
- `amount` must be a dollar figure of 0 or more with at most two decimals.
- The concentration threshold must be a dollar figure of 0 or more.

## Logic
1. For each obligation, measure whole days from the as-of date to the due date:
   `days = floor((due_date - as_of) / one day)`.
2. A due date before the as-of date is `Overdue`. Otherwise the rung is `week = floor(days / 7) + 1`.
   A week past 13 is `Beyond`. The as-of date itself lands in week 1.
3. Each week rung starts on `as_of + 7 * (week - 1)` days.
4. Sum the amounts in each rung. A week rung whose total reaches the concentration threshold is
   flagged heavy. The overdue rung is always flagged.
5. The "due within 13 weeks" figure is the overdue total plus weeks 1 through 13. The heaviest rung
   is the one with the largest total.
6. All money is held in integer cents through every step, so totals are exact to the cent.

## Outputs
On the page: summary stats, a bar chart of the ladder with heavy weeks and the overdue rung
flagged, and a table of each rung that has obligations. The export button writes
`maturities-by-week.csv`:

`week,debt_due`

one row per week 1 through 13. Overdue amounts are folded into week 1, because they still have to
be paid right away. Obligations beyond 13 weeks are left out of the export. The Liquidity Forecast
adds the `debt_due` column to each week's outflows.

## Edge cases
The sample file exercises a clean near-term obligation (`OB-1001`, week 1), an obligation on the
as-of date itself (`OB-1002`, the week-1 start boundary), an obligation on a week-end boundary
(`OB-1004`, the last day of week 2), an overdue obligation (`OB-1005`), one on the last day of the
horizon (`OB-1006`, week 13), and one past the horizon (`OB-1007`, beyond). The
`bad-obligations.csv` file holds a duplicate `obligation_id` and an unreal due date so the
rejections can be seen.

Hand-checked example, as-of `2026-06-15`: `OB-1001` is due `2026-06-19`, 4 days out, week 1.
`OB-1002` is due on the as-of date, 0 days out, week 1. Their week-1 chart total is
`50000.00 + 22000.00 = 72000.00`. `OB-1005` is due `2026-06-10`, before the as-of date, so it is
overdue at `4750.00`. On export the overdue amount folds into week 1, giving
`50000.00 + 22000.00 + 4750.00 = 76750.00`. `OB-1006` is due `2026-09-13`, 90 days out, week 13
(`floor(90 / 7) + 1 = 13`), at `75000.00`, above the 50000.00 threshold, so week 13 is heavy. The
exported week-1 figure (76750.00) and week-13 figure (75000.00) are the debt outflows the Liquidity
Forecast picks up.
