# Job-cost engine

## Purpose
Turns a list of construction contracts into a work-in-progress (WIP) schedule. For
each job it recognizes revenue by cost-to-cost percent complete and reports the
over or under billing position, the kind of month-end calculation a project
accountant or job-cost analyst runs before billing. A WIP-workbook builder reads
the schedule this tool writes.

## Inputs
`contracts.csv`, one row per job, with these columns:

| Column | Type | Meaning |
| --- | --- | --- |
| job_id | text | Unique job identifier |
| job_name | text | Job name for the schedule |
| contract_value | number | Total contract price |
| estimated_total_cost | number | Current estimate of total cost at completion |
| cost_to_date | number | Cost booked to the job so far |
| billed_to_date | number | Amount billed to the owner so far |

## Validation rules
Each rule rejects the row with a message naming the job and the field.

- Every field is present and non-empty.
- `contract_value` is greater than zero.
- `estimated_total_cost` is greater than zero.
- `cost_to_date` is zero or more.
- `billed_to_date` is zero or more.
- `estimated_total_cost` is not less than `cost_to_date`. A job cannot report a
  cost overrun past its own estimate without the estimate being revised first,
  which keeps percent complete between 0 and 100 percent.
- `job_id` does not repeat within the file.

## Logic
For each job, in order:

1. Percent complete = cost_to_date / estimated_total_cost, rounded to four
   decimal places, half up.
2. Earned revenue = contract_value * cost_to_date / estimated_total_cost, rounded
   to the cent, half up.
3. Cost to complete = estimated_total_cost - cost_to_date.
4. Estimated gross profit at completion = contract_value - estimated_total_cost.
5. Gross profit to date = earned_revenue - cost_to_date.
6. Over/under billing = earned_revenue - billed_to_date. Positive means
   underbilled, the job has earned more than it has billed (an asset). Negative
   means overbilled, the job has billed more than it has earned (a liability).
   Zero is even.

Money uses `decimal.Decimal` rounded half up to the cent, so the figures match
the workbook formulas the next tool writes, to the cent.

## Outputs
`wip_schedule.csv`, one row per job, with the input columns plus percent_complete,
earned_revenue, cost_to_complete, estimated_gross_profit, gross_profit_to_date,
over_under_billing, and status (Underbilled, Overbilled, or Even).

## Edge cases
The sample `contracts.csv` is seeded so one run touches every branch:

- A clean underbilled job (J-1001, the hand-check below) and a second underbilled
  job (J-1005).
- Overbilled jobs (J-1002 and J-1006).
- A completed job at exactly 100 percent that is even (J-1003).
- A not-started job at zero cost that is overbilled on a deposit (J-1004).

`contracts_invalid.csv` holds a job whose cost to date is above its estimated
total cost, so a run against it is rejected.

### Hand-checked example
Job J-1001, the Riverside Transit Hub: contract value 1,200,000, estimated total
cost 800,000, cost to date 480,000, billed to date 700,000.

- Percent complete = 480,000 / 800,000 = 0.6000.
- Earned revenue = 1,200,000 * 0.60 = 720,000.00.
- Over/under billing = 720,000.00 - 700,000.00 = 20,000.00, so the job is
  underbilled by 20,000.00.

Across all six jobs the schedule totals earned revenue 2,640,500.00, billings
2,682,000.00, and a net over/under of -41,500.00 (overbilled in total). The
workbook builder re-derives every one of these with its own cell formulas and the
verifier confirms they agree to the cent.
