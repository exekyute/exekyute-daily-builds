# Data dictionary

## expected/key_figures.csv

One row per key figure. Two columns.

| Column | Type | Meaning |
|---|---|---|
| `figure` | text | Key-figure name. Year-level figures carry the fiscal year as a suffix, for example `paid_per_beneficiary_2023-2024`. |
| `value` | text | The figure's value, written exactly as the verification compares it. Money carries two decimals, coverage rates carry two decimals, slope and intercept carry six, counts have none. |

### Figure names

| Figure | Type | Meaning | Units |
|---|---|---|---|
| `paid_per_beneficiary_<fiscal year>` | money | Amount paid divided by beneficiaries for that fiscal year, rounded to the cent | CAD |
| `coverage_rate_pct_<fiscal year>` | percent | Beneficiaries as a share of insured persons for that fiscal year, times 100, rounded to two decimals | percent |
| `total_amount_paid` | money | Sum of `amount_paid` across all observed fiscal years | CAD, whole dollars in this dataset |
| `total_beneficiaries` | count | Sum of `beneficiaries` across all observed fiscal years | persons |
| `overall_paid_per_beneficiary` | money | Total amount paid divided by total beneficiaries, rounded to the cent | CAD |
| `slope_per_year` | number | Least squares slope of paid-per-beneficiary against fiscal year start, rounded to six decimals | CAD per year |
| `intercept` | number | Least squares intercept from the same fit, rounded to six decimals | CAD |
| `projected_paid_per_beneficiary_<fiscal year>` | money | Intercept plus slope times the projected year start, rounded to the cent | CAD |
| `latest_paid_per_beneficiary` | money | Paid per beneficiary in the most recent observed fiscal year | CAD |
| `change_pct_first_to_latest` | percent | Percent change in paid-per-beneficiary from the first observed year to the latest | percent |

## Data sheet (workbook)

Prepared rows from the snapshot, one per fiscal year, sorted ascending. Values only, no formulas.

| Column | Type | Meaning | Units |
|---|---|---|---|
| `fiscal_year` | text | Nova Scotia fiscal year label, `YYYY-YYYY` | none |
| `services_rendered` | integer | Dental services rendered under the children's oral health program | services |
| `amount_paid` | number | Total paid for those services | CAD |
| `persons_insured` | integer | Children insured under the program | persons |
| `beneficiaries` | integer | Children who received at least one service | persons |

## Model sheet (workbook)

Every figure below is a live formula; nothing is pasted.

| Block | Contents |
|---|---|
| Per-year table (rows 4 to 19) | Fiscal year and year start (parsed from the label), amount paid, beneficiaries, paid per beneficiary as a live division rounded to the cent, persons insured, coverage rate as a live division times 100 |
| Totals (rows 22 to 24) | `SUM` of amount paid, `SUM` of beneficiaries, and overall paid per beneficiary as the ratio of the two sums |
| Trend and projection (rows 27 to 31) | `SLOPE` and `INTERCEPT` over the per-year table, then two projected periods computed as `ROUND(INTERCEPT(...) + SLOPE(...) * year, 2)` |
| Headline (rows 34 to 37) | Latest fiscal year, latest paid per beneficiary, percent change since the first year, and the next projected value, all as cell references or live formulas |
