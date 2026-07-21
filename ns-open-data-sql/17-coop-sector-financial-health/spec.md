# Spec: co-op sector financial health model

## Purpose

Model the financial health of Nova Scotia's co-operative sector, year over year, inside a formula-driven Excel workbook. The workbook holds no pasted results: every key figure is a live formula over the Data sheet, and `build.py` proves each one by recomputing it in plain Python and diffing against a golden file.

## Inputs

One pinned snapshot in `data/raw/`, pulled from the Socrata resource endpoint for dataset `ff6i-nhbm` (Co-operatives Financial and Operating Summary). Columns used: `report_year`, `co_ops_reporting`, `total_income`, `total_expenses`, `net_income`, `total_assets`, `total_liability`, `total_equity`, `full_time_employees`, `part_time_employees`, `total_employees`, `total_members`. The dataset's governance columns (board positions filled, AGMs held, quorum, meeting counts) are not used. Every used value in the snapshot is a whole number; money is whole Canadian dollars.

## Cleaning rules

Applied by `load_rows()` before anything else sees the data:

1. Keep only rows whose `report_year` is a four-digit year.
2. Parse every used column as an integer; drop any row where parsing fails.
3. Drop any row with a zero or negative `total_income`, `total_assets`, `total_liability`, or `co_ops_reporting`, so no formula ever divides by zero.
4. Sort ascending by `report_year`. A duplicate report year stops the build.

The cleaned rows become the workbook's Data sheet, values only. The 2026-07-06 snapshot has 10 report years, 2015 through 2024, and loses no rows to cleaning.

## Model logic, step by step

All formulas live on the Model sheet and reference the Data sheet. On the Data sheet, column B is `co_ops_reporting`, C is `total_income`, D is `total_expenses`, E is `net_income`, F is `total_assets`, G is `total_liability`, H is `total_equity`, and K is `total_employees`.

1. **Operating margin.** For each year, `=ROUND(Data!E<r>/Data!C<r>*100,2)`: net income as a percent of total income, rounded to two decimals. The dataset's own `net_income` column is used as reported, not recomputed as income minus expenses (see Edge cases).
2. **Equity ratio.** For each year, `=ROUND(Data!H<r>/Data!F<r>*100,2)`: total equity as a percent of total assets.
3. **Solvency.** For each year, `=ROUND(Data!F<r>/Data!G<r>,2)`: total assets over total liabilities, as a multiple.
4. **Employees per reporting co-op.** For each year, `=ROUND(Data!K<r>/Data!B<r>,2)`: total employees over the number of co-ops that reported. The reporting count is the denominator because the employee figures come from the reports that were filed, not from every registered co-op.
5. **Direction flags.** Next to each of the margin, equity ratio, and employees columns, a text flag compares the rounded ratio to the prior year's rounded ratio: `=IF(E<r>>E<r-1>,"up",IF(E<r><E<r-1>,"down","flat"))`. The first observed year holds the literal text `n/a`. The flags compare the rounded cells so they always agree with what a reader sees on the sheet.
6. **Sector totals.** `SUM` over the Data sheet's income, expenses, and net income columns. The inputs are whole dollars, so these sums tie to the snapshot exactly. The overall margin is `=ROUND(SUM(net)/SUM(income)*100,2)` over the same ranges.
7. **Headline.** Latest report year, its margin, equity ratio, solvency, and employees per reporting co-op with their direction flags, all as references into the per-year table.

The Python verification recomputes the same figures with `decimal.Decimal` and rounds with `ROUND_HALF_UP`, which rounds halves away from zero exactly as Excel's `ROUND` does. Python's built-in `round()` is never used because it rounds halves to even.

## Cell map of key figures

With 10 observed years, the Model sheet lays out as follows.

| Key figure | Cell(s) |
|---|---|
| `margin_pct_<year>` | E5:E14, one row per report year in ascending order |
| `margin_dir_<year>` | F5:F14 |
| `equity_ratio_pct_<year>` | G5:G14 |
| `equity_dir_<year>` | H5:H14 |
| `solvency_ratio_<year>` | I5:I14 |
| `employees_per_coop_<year>` | J5:J14 |
| `employees_dir_<year>` | K5:K14 |
| `total_income_all_years` | B17 |
| `total_expenses_all_years` | B18 |
| `total_net_income_all_years` | B19 |
| `overall_margin_pct` | B20 |
| `latest_year` | B23 |
| `latest_margin_pct` | B24 |
| `latest_margin_dir` | B25 |
| `latest_equity_ratio_pct` | B26 |
| `latest_equity_dir` | B27 |
| `latest_solvency_ratio` | B28 |
| `latest_employees_per_coop` | B29 |
| `latest_employees_dir` | B30 |

## Edge cases

- **Zero denominators.** A row with a zero or negative income, assets, liabilities, or reporting count is dropped during cleaning, so it never reaches the Data sheet and no Excel division can hit a zero. The pinned snapshot loses nothing to this rule.
- **Missing years.** Ratios are computed within each observed year, and a direction flag compares adjacent observed rows. A gap in the series would make a flag compare across the gap; nothing is interpolated.
- **Duplicate years.** An aggregate summary should carry one row per year, so a repeated `report_year` stops the build rather than picking a winner.
- **Source-data quirks.** In 2020 and 2021 the reported `net_income` differs from income minus expenses by one dollar (in opposite directions, so the ten-year totals agree). In several years assets differ from liabilities plus equity by up to three dollars. The model uses the reported columns as-is and does not force the identities.
- **New snapshot with more years.** The layout is computed from the row count, so every range and cell reference shifts with the data. The cell map above is for the pinned 10-year snapshot.

## Determinism and money tie

The build is deterministic end to end: a pinned snapshot, a fixed sort, integer inputs, and half-away-from-zero rounding at defined points. The snapshot carries money as whole dollars, the totals block sums those integers directly, and `total_income_all_years`, `total_expenses_all_years`, and `total_net_income_all_years` tie to the snapshot exactly. Ratios are rounded once, at two decimals, in the cell that displays them. Running `python build.py` twice produces the same workbook and the same PASS.
