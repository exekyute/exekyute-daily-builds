# Grant engine

## Purpose
Tracks a grant by drawdown and compliance. It walks the award period by period and,
at each period, measures how much has been drawn on allowable costs, the run-rate
burn, the runway left, and where the spend is heading by the award end, so an
overspend shows up early. It also tracks which reports are overdue. The browser view
in `02` reads the timeline this tool writes.

## Inputs
`award.csv`, one row per budget category (category, budget). `transactions.csv`, one
row per spend (period, category, amount). `reporting_schedule.csv`, one row per report
(report, due_period, submitted). The award period length is set with `--months`
(default 12) and the current period with `--asof` (default the latest transaction).

## Validation rules
- Award: every field present, budget above zero, category not repeated.
- Transactions: every field present, period a positive number, amount above zero.
- Reports: every field present, due_period a positive number, submitted yes or no.

## Logic
The award total is the sum of the category budgets. A cost is allowable only if its
category is one the award budgets; anything else is disallowed and kept out of the
drawdown. For each period up to the as-of period:

1. Cumulative allowable = allowable spend up to that period. Cumulative disallowed is
   tracked alongside.
2. Burn rate = cumulative allowable over periods elapsed.
3. Projected total at the award end = cumulative allowable times award periods over
   periods elapsed.
4. Remaining = award total minus cumulative allowable. Runway = remaining over the
   burn rate.
5. Status = Over budget if the projection is above the award, On track otherwise.
6. Reports overdue = reports whose due period has passed and that are not submitted.

A category summary gives each category's budget, allowable spend, and remaining, and a
deadline list gives each report's status. Money uses `decimal.Decimal` rounded half up
to the cent.

## Outputs
`timeline.csv` (per period), `category_summary.csv` (per category), and `deadlines.csv`
(per report). The browser view reads the timeline; the category and deadline files give
the supporting detail.

## Edge cases
The sample starts on track and trends over budget as the burn rate climbs, has a
disallowed cost that stays out of the drawdown, and has a report that becomes overdue.
`transactions_invalid.csv` has a zero period, so a run against it is rejected.

### Hand-checked example
A 250,000 award over 12 periods. By period 4, 100,000 has been drawn on allowable costs
(5,000 of entertainment is disallowed and excluded), leaving 150,000. The burn rate is
25,000 a period, so the projection at the award end is 100,000 * 12 / 4 = 300,000.00,
which is 50,000.00 over the award, with about six periods of runway left and one report
overdue. The browser view reproduces every figure.
