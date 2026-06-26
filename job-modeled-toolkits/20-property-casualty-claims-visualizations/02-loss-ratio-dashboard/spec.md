# Loss Ratio Dashboard

## Purpose
Read the clean claims file from the Claims Aging and Status Funnel and show the loss ratio,
incurred losses divided by earned premium, for every line of business and accident year. A claims
analyst runs this to see which line-and-year cells are running hot and how the whole book
compares.

## Inputs
One CSV, the `clean-claims.csv` exported by the Claims Aging and Status Funnel. Header, exact:

`claim_id,line_of_business,accident_period,report_date,valuation_date,development_month,status,close_date,paid_to_date,case_reserve,incurred,earned_premium,is_latest,age_days,age_bucket,days_to_close`

This tool reads four of those columns: `line_of_business`, `accident_period`, `incurred`,
`earned_premium`, and uses `is_latest` to pick each claim's most recent valuation.

## Validation rules
- The header must match the funnel's clean-claims export exactly. A different header is refused
  with a message pointing back to the funnel, so loading the wrong file is caught at once.
- Every row must have 16 fields.
- claim_id and accident_period must not be blank.
- is_latest must be Y or N.
- incurred and earned_premium must be amounts with up to two decimals and no minus sign, and
  earned_premium must be greater than zero.
- earned_premium must be the same for every row that shares a line and accident year.

Each failed check stops the load with a clear, row-numbered message.

## Logic
1. Parse and validate every row.
2. Keep only the rows where is_latest is Y, so each claim counts once at its most recent
   valuation.
3. Group those rows by line of business and accident year.
4. For each group, sum incurred (paid plus case reserve, already combined in the clean file), and
   take earned premium once, since every claim in a line and year carries the same premium.
5. Loss ratio is incurred divided by earned premium. It is computed for each cell, for each line
   across its years, for each year across the lines, and for the whole book.
6. Money is held in integer cents. Ratios are shown as percentages to one decimal.

## Outputs
On screen: a grid with lines of business as rows and accident years as columns. Each cell shows
the loss ratio and the incurred dollars, shaded deeper as the ratio climbs. A right-hand column
totals each line across years, a bottom row totals each year across lines, and the corner cell is
the loss ratio for the whole book. The summary band shows the overall ratio, total incurred,
total premium, and the highest and lowest cells.

## Edge cases
The sample file is the funnel's output for ten claims across two lines and three accident years,
so the grid is fully populated. The shading scale exercises a spread of ratios from 56.7 percent
to 75.0 percent. The matching `bad-clean-claims.csv` is the raw register rather than the clean
export, so loading it shows the header guard pointing back to the funnel. The test suite also
covers a bad is_latest flag and an inconsistent premium.

**Hand-checked example.** Auto, accident year 2022, has two claims. At their latest valuation
they carry incurred of CAD 12,000.00 and CAD 5,000.00, a total of CAD 17,000.00. The earned
premium for Auto 2022 is CAD 25,000.00, counted once. The loss ratio is 17,000.00 / 25,000.00 =
0.68, shown as 68.0 percent. Across the whole book incurred is CAD 119,500.00 against earned
premium of CAD 176,000.00, a loss ratio of 67.9 percent. The incurred total of CAD 119,500.00 is
the same figure the Claims Aging and Status Funnel reports at the latest valuation, which is how
the two tools tie out to the cent.
