# Claims Aging and Status Funnel

## Purpose
Take a claims valuation register, roll each claim up to its latest valuation, and show how the
still-open inventory ages, how the open, pending, and closed counts break down, and how long
closed claims took to settle. A claims analyst runs this to see where the open book is piling up
and to hand a clean claims file to the loss-ratio and reserve-development tools.

## Inputs
One CSV, the claims valuation register, with one row per claim per valuation point (development
month). Header, exact:

`claim_id,line_of_business,accident_period,report_date,valuation_date,development_month,status,close_date,paid_to_date,case_reserve,earned_premium`

| Column | Type | Notes |
| --- | --- | --- |
| claim_id | text | claim identifier, repeated across its valuation rows |
| line_of_business | text | Auto, Property, Liability, or Commercial |
| accident_period | text | four-digit accident year, e.g. 2024 |
| report_date | date | YYYY-MM-DD, when the claim was reported |
| valuation_date | date | YYYY-MM-DD, the date this row is valued at |
| development_month | integer | months of maturity: 12, 24, 36 ... |
| status | text | open, pending, or closed |
| close_date | date | YYYY-MM-DD when closed, blank otherwise |
| paid_to_date | money | cumulative paid in dollars, zero or more |
| case_reserve | money | case reserve in dollars, zero or more |
| earned_premium | money | earned premium for the line and accident year, greater than zero |

## Validation rules
- The header must match exactly, and every row must have 11 fields.
- claim_id must not be blank.
- line_of_business must be one of Auto, Property, Liability, Commercial.
- accident_period must be a four-digit year.
- report_date and valuation_date must be real YYYY-MM-DD dates, and valuation_date must not fall
  before report_date.
- development_month must be a whole number greater than zero.
- status must be open, pending, or closed. A closed claim must carry a valid close_date that is
  not before report_date. An open or pending claim must leave close_date blank.
- paid_to_date, case_reserve, and earned_premium must be amounts with up to two decimals and no
  minus sign. earned_premium must be greater than zero.
- No two rows may share the same claim_id and valuation_date.
- A claim's line, accident year, and report date must match across all of its rows.
- earned_premium must be the same for every row that shares a line and accident year.
- Cumulative paid_to_date must never fall as a claim moves to a later development month.

Each failed check stops the load with a clear, row-numbered message.

## Logic
1. Parse and validate every row.
2. The as-of date is the latest valuation_date in the file.
3. For each claim, take its row with the latest valuation_date as the current state.
4. age_days is the day count from report_date to the as-of date. Buckets are 0-30, 31-60, 61-90,
   91-180, and 180+; a boundary value lands in the lower bucket (30 is 0-30, 90 is 61-90).
5. Bucket only the still-open inventory, meaning open and pending claims. Closed claims are
   reported separately.
6. Count the open, pending, and closed claims.
7. days_to_close for a closed claim is the day count from report_date to close_date. The average
   is the mean of those, rounded to the nearest whole day.
8. incurred is paid_to_date plus case_reserve. Totals are summed over the latest row of each
   claim. Money is held in integer cents.

## Outputs
- On screen: an aging funnel of open inventory by bucket, the status mix, the average days to
  close, and the incurred and paid totals at the latest valuation.
- A downloadable `clean-claims.csv`, one row per claim per valuation point, with these added
  columns: `incurred`, `is_latest` (Y or N), `age_days`, `age_bucket`, and `days_to_close`
  (blank unless closed). The Loss Ratio Dashboard reads the latest rows; the Reserve Development
  Triangle reads every row.

## Edge cases
The sample register is built so one load exercises every branch:
- A claim aged exactly 30 days (A-2402) lands in 0-30, and one aged exactly 90 days (A-2403)
  lands in 61-90, both confirming boundaries fall into the lower bucket.
- A zero-paid claim still under review (A-2403) carries reserve but no payment.
- Claims span open, pending, and closed, and three accident years per line so the consumer tools
  have a full triangle and several line-and-period cells.
- Closed claims (A-2201, A-2202, P-2201) drive the average days to close.

The matching `bad-claims.csv` carries a negative case reserve so the rejection path is easy to
see. Other invalid rows (a closed claim with no close date, an unknown status, a duplicate
valuation, falling cumulative paid, inconsistent premium) are covered in the test suite.

**Hand-checked example.** As of 2024-12-31 the sample holds ten claims: five open, two pending,
three closed. The open inventory buckets as 1 (0-30), 0 (31-60), 1 (61-90), 2 (91-180), and 3
(180+). The three closed claims took 828, 568, and 938 days from report to close, an average of
778 days. Incurred across the latest valuations totals CAD 119,500.00 and paid totals CAD
73,500.00. The to-the-cent loss-ratio hand-check that ties these tools together lives in
`../02-loss-ratio-dashboard/spec.md`.
