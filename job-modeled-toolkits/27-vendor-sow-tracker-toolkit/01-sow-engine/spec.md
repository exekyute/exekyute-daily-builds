# SOW engine

## Purpose
Tracks a vendor statement of work by earned value. It walks the SOW week by week
and, at each week, measures the work earned against the money spent, so an overrun
shows up in the estimate at completion long before the final invoice. The browser
view in `02` reads the timeline this tool writes.

## Inputs
Two CSVs plus a holdback rate.

`milestones.csv`, one row per milestone:

| Column | Type | Meaning |
| --- | --- | --- |
| milestone_id | text | Unique milestone identifier |
| name | text | Milestone name |
| budget | number | Budget for the milestone |
| complete_week | integer | The week the milestone is earned |

`effort_log.csv`, one row per effort entry:

| Column | Type | Meaning |
| --- | --- | --- |
| week | integer | Week the effort was logged |
| milestone_id | text | Milestone the effort was on |
| hours | number | Hours worked |
| rate | number | Billing rate per hour |

The holdback rate is a share between 0 and 1, passed with `--holdback` (default 0.10).

## Validation rules
- Milestones: every field present, budget above zero, complete_week a positive
  number, milestone_id unique.
- Effort: every field present, week a positive number, milestone_id present in the
  milestones file, hours and rate zero or more.
- Holdback rate between 0 and 1.

## Logic
The total budget is the sum of the milestone budgets. For each week from 1 to the
last week with effort:

1. Cost to date = the effort cost (hours times rate) of every entry up to that week.
2. Earned value = the budget of every milestone complete by that week.
3. CPI = earned value over cost to date.
4. Estimate at completion (EAC) = total budget times cost to date over earned value,
   which is the budget divided by CPI.
5. Variance at completion (VAC) = total budget minus EAC. Negative is an overrun.
6. Holdback accrued = the holdback rate times earned value, released in full once
   every milestone is complete.
7. Status from EAC against budget: On track at or under budget, At risk above budget,
   Over budget more than five percent above.

Money uses `decimal.Decimal` rounded half up to the cent. CPI and the percentages
are rounded to four places.

## Outputs
`timeline.csv`, one row per week with cost to date, earned value, percent complete,
percent spent, CPI, EAC, VAC, holdback accrued, holdback released, and status.
`milestone_summary.csv`, one row per milestone with its budget, actual cost, and
variance.

## Edge cases
The sample has milestones that finish on budget and milestones that run over, so the
timeline moves between At risk and Over budget and the holdback releases only at the
final week. `effort_invalid.csv` logs effort against a milestone that is not in the
milestones file, so a run against it is rejected.

### Hand-checked example
The SOW totals 80,000 across five milestones, with a 10 percent holdback. By week 3,
two milestones (50,000 of budget) are complete and 52,000 has been spent, so the
estimate at completion is 80,000 * 52,000 / 50,000 = 83,200.00 and the holdback
accrued is 5,000.00. At completion the SOW has spent 85,000.00 against 80,000.00 of
budget, so the EAC is 85,000.00, the variance is -5,000.00, and the 8,000.00 holdback
is released. The browser view reproduces every figure, and the test suite checks them.
