# Spec: children's dental utilization model

## Purpose

Model what Nova Scotia's children's oral health program pays per child who actually uses it, year over year, inside a formula-driven Excel workbook. The workbook holds no pasted results: every key figure is a live formula over the Data sheet, and `build.py` proves each one by recomputing it in plain Python and diffing against a golden file.

## Inputs

One pinned snapshot in `data/raw/`, pulled from the Socrata resource endpoint for dataset `saqh-58pj` (Children's Oral Health Utilization). Columns used: `fiscal_year`, `_of_services_rendered`, `amount_paid`, `persons_insured`, `beneficiaries`. The dataset's own derived rate columns are ignored; the model recomputes its rates from the base counts.

## Cleaning rules

Applied by `load_rows()` before anything else sees the data:

1. Keep only rows whose `fiscal_year` matches `YYYY-YYYY`.
2. Parse the four count and money columns; drop any row where parsing fails.
3. Drop any row with zero or negative `beneficiaries` or `persons_insured`, so no formula ever divides by zero.
4. Sort ascending by fiscal year.

The cleaned rows become the workbook's Data sheet, values only. The 2026-07-06 snapshot has 16 fiscal years, 2008-2009 through 2023-2024, and loses no rows to cleaning.

## Model logic, step by step

All formulas live on the Model sheet and reference the Data sheet.

1. **Year start.** Parsed live from the label: `=VALUE(LEFT(Data!A<r>,4))`. This is the regression x variable.
2. **Paid per beneficiary.** For each year, `=ROUND(Data!C<r>/Data!E<r>,2)`: amount paid divided by beneficiaries, rounded to the cent.
3. **Coverage rate.** For each year, `=ROUND(Data!E<r>/Data!D<r>*100,2)`: beneficiaries as a percent of insured persons.
4. **Totals.** `SUM` over the Data sheet's amount-paid and beneficiaries columns, then overall paid per beneficiary as `=ROUND(SUM(paid)/SUM(beneficiaries),2)`. Because the sums are over raw integers, the totals tie exactly to the snapshot.
5. **Projection.** Plain least squares of the rounded paid-per-beneficiary values against year start, over all observed years. The two projected periods (2024-2025 and 2025-2026) are each computed in one cell as `=ROUND(INTERCEPT(y,x)+SLOPE(y,x)*year,2)`, where `year` is a live cell equal to the last observed year start plus one or two. Slope and intercept are also shown on their own, rounded to six decimals.
6. **Headline.** Latest fiscal year, latest paid per beneficiary, percent change from the first observed year (`=ROUND((last-first)/first*100,2)`), and the next projected value, all as references into the blocks above.

The Python verification recomputes the same figures with the closed-form slope and intercept (covariance over variance), never a fitting library, and rounds money with `decimal.Decimal` and `ROUND_HALF_UP`, which rounds halves away from zero exactly as Excel's `ROUND` does. The recomputation never touches Python's built-in `round()` on money because it rounds halves to even.

## Cell map of key figures

With 16 observed years, the Model sheet lays out as follows.

| Key figure | Cell(s) |
|---|---|
| `paid_per_beneficiary_<fy>` | E4:E19, one row per fiscal year in ascending order |
| `coverage_rate_pct_<fy>` | G4:G19 |
| `total_amount_paid` | B22 |
| `total_beneficiaries` | B23 |
| `overall_paid_per_beneficiary` | B24 |
| `slope_per_year` | B27 |
| `intercept` | B28 |
| `projected_paid_per_beneficiary_2024-2025` | C30 |
| `projected_paid_per_beneficiary_2025-2026` | C31 |
| `latest_paid_per_beneficiary` | B35 (references E19) |
| `change_pct_first_to_latest` | B36 |

The headline block also holds the latest fiscal year label (B34) and the next projected value (B37, references C30).

## Edge cases

- **Missing years.** The regression runs over the years that exist; nothing is interpolated. A gap in the series changes the x values, not the method.
- **Zero beneficiaries or insured persons.** Such a row is dropped during cleaning, so it never reaches the Data sheet and no Excel division can hit a zero.
- **New snapshot with more years.** `build.py` computes the layout from the row count, so every range and cell reference shifts with the data. The cell map above is for the pinned 16-year snapshot.

## Determinism and money tie

The build is deterministic end to end: a pinned snapshot, a fixed sort, closed-form arithmetic, and half-away-from-zero rounding at defined points. Money is only ever rounded at the cent, and the totals block sums raw integer dollars, so `total_amount_paid` ties to the snapshot to the cent. Running `python build.py` twice produces the same workbook and the same PASS.
