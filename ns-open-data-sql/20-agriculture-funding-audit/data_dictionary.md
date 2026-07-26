# Data dictionary

All dollar figures are Canadian dollars (CAD), carried as `DECIMAL(18,2)` in SQL and written to CSV with two decimal places. Percentages are rounded to two decimals for display; the underlying division happens on exact decimals.

## out/funding_audit.csv (also expected/funding_audit.csv)

One sectioned result file. Columns not meaningful for a section are blank.

| Column | Type | Meaning |
| --- | --- | --- |
| section | text | Which block the row belongs to: `summary`, `totals_tie`, `top_recipients`, `program_shares`, `yoy_division`, or `duplicate_candidates`. |
| rank | integer | Position within the section. Ranking sections order by dollars descending; `yoy_division` orders by fiscal year then division. |
| measure | text | Label for `summary` and `totals_tie` rows (for example `grand_total_dollars`, `sum_by_program`). Blank elsewhere. |
| fiscal_year | text | Fiscal year label like `2014-2015`. Filled for `yoy_division` and `duplicate_candidates` rows. |
| division | text | Canonical division name. Filled for `yoy_division` rows. |
| program_name | text | Program label, including `(program not stated)` for the 21 blank-program rows. Filled for `program_shares` and `duplicate_candidates` rows. |
| recipient | text | Recipient display name (most frequent raw spelling of the normalized key). Filled for `top_recipients` and `duplicate_candidates` rows. |
| payments | integer | Payment count for the row. In `duplicate_candidates` it is the occurrence count of the repeated payment; in the duplicate summary row it is the count of occurrences beyond the first. |
| amount | CAD, 2 dp | Dollar figure for the row. In `duplicate_candidates` it is the single repeated payment amount, not the group total. |
| share_pct | percent, 2 dp | The row's share of the grand total in dollars. 100.00 on the grand-total row. |
| cumulative_share_pct | percent, 2 dp | Running share of the grand total, filled only in `top_recipients`. |
| yoy_change | CAD, 2 dp | In `yoy_division`, the dollar change against the division's previous observed fiscal year (blank in a division's first year). In `duplicate_candidates`, reused as the extra dollars beyond the first occurrence (amount times occurrences minus one). |
| yoy_pct | percent, 2 dp | Year-over-year change percent, filled only in `yoy_division`. |

## bi/exports/mart_funding_audit.csv (copy of out/mart_funding_audit.csv)

One row per source payment, cleaned. 6,324 rows; `payment_amount` sums to exactly $75,357,902.03, the same grand total the audit file proves.

| Column | Type | Meaning |
| --- | --- | --- |
| fiscal_year | text | Fiscal year label like `2014-2015`. |
| fiscal_year_start | integer | First calendar year of the fiscal label (2014 for `2014-2015`). Use this for year arithmetic in DAX; the mart has no date column. |
| division | text | Canonical division name (ampersand spelling folded into `Programs and Business Risk Management`). |
| program_name | text | Cleaned program label, including `(program not stated)`. |
| recipient | text | Recipient display name after case and spacing normalization. |
| payment_amount | CAD, 2 dp | The individual payment amount. |
| is_duplicate_candidate | integer 0/1 | 1 when the row belongs to a duplicate-candidate group (same recipient key, program, amount, fiscal year appearing more than once). |
| dup_occurrences | integer | How many payments share this row's recipient key, program, amount, and fiscal year. 1 for unique payments. |
