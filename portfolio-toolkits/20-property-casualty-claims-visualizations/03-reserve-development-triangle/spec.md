# Reserve Development Triangle

## Purpose
Read the clean claims file from the Claims Aging and Status Funnel and lay cumulative paid losses
out as a development triangle, then read the development factors and project each accident year to
ultimate. A claims analyst runs this to see how losses mature and what reserve each accident year
still needs.

## Inputs
One CSV, the `clean-claims.csv` exported by the Claims Aging and Status Funnel. Header, exact:

`claim_id,line_of_business,accident_period,report_date,valuation_date,development_month,status,close_date,paid_to_date,case_reserve,incurred,earned_premium,is_latest,age_days,age_bucket,days_to_close`

This tool reads `line_of_business`, `accident_period`, `development_month`, and `paid_to_date`. It
uses every row, not just the latest, because the triangle needs the full development history.

## Validation rules
- The header must match the funnel's clean-claims export exactly. A different header is refused
  with a message pointing back to the funnel.
- Every row must have 16 fields.
- line_of_business must not be blank.
- accident_period must be a four-digit year.
- development_month must be a whole number greater than zero.
- paid_to_date must be an amount with up to two decimals and no minus sign.

Each failed check stops the load with a clear, row-numbered message.

## Logic
1. Parse and validate every row.
2. If a line of business is chosen, keep only its rows; "All" keeps the whole book.
3. Sum paid_to_date into a triangle cell for each accident year and development month. Accident
   years run down the side, development months across the top.
4. The age-to-age factor from one development month to the next is the sum of cumulative paid at
   the later month divided by the sum at the earlier month, taken only over the accident years
   that have a cell in both columns.
5. The factor to ultimate from a development age is the running product of every later age-to-age
   factor. The most mature age develops to ultimate by a factor of 1.0000.
6. Each accident year is projected from its latest filled cell: projected ultimate is that
   cumulative paid times the factor to ultimate for its age, rounded to the nearest cent, halves
   up. The indicated reserve is projected ultimate minus paid to date.
7. Money is held in integer cents. Factors are shown to four decimals.

## Outputs
On screen: the cumulative-paid triangle with the latest valuation on each row shaded, a row of
age-to-age factors, a row of factors to ultimate, and a table of projected ultimate and indicated
reserve by accident year. The summary band shows paid to date, projected ultimate, and the
indicated reserve for the current line filter.

## Edge cases
The sample file gives a full lower triangle: accident year 2022 is mature to 36 months, 2023 to
24 months, and 2024 to 12 months, so the diagonal steps back one column per year. Switching the
line filter to Auto or Property rebuilds the triangle and the factors from that line alone. The
matching `bad-clean-claims.csv` has a development month of "end" rather than a number, so loading
it shows that rejection. The test suite also covers the wrong-file header guard.

**Hand-checked example.** For the whole book the cumulative paid at 12 months totals CAD
30,000.00 for 2022 and CAD 9,000.00 for 2023, and at 24 months CAD 43,500.00 and CAD 20,500.00.
The 12-to-24 month factor uses both those years: (43,500.00 + 20,500.00) / (30,000.00 + 9,000.00)
= 64,000.00 / 39,000.00 = 1.6410. Only 2022 reaches 36 months, so the 24-to-36 factor is
47,000.00 / 43,500.00 = 1.0805. A claim valued at 12 months therefore develops to ultimate by
1.6410 x 1.0805 = 1.7731. Accident year 2024, paid CAD 6,000.00 at 12 months, projects to a CAD
10,638.37 ultimate and a CAD 4,638.37 reserve. These figures use the same paid amounts the Claims
Aging and Status Funnel produced, so the triangle and the funnel rest on one source.
