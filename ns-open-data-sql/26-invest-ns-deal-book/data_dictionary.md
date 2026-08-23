# Data dictionary

All dollar figures are Canadian dollars (CAD), carried as `DECIMAL(18,2)` in SQL and written to CSV with two decimal places. Percentages are rounded to two decimals for display; the underlying division happens on exact decimals. Blank contributions are NULL, never zero.

## out/deal_book.csv (also expected/deal_book.csv)

One sectioned result file, 176 rows plus a header. Columns that are not meaningful for a section are blank.

| Column | Type | Meaning |
| --- | --- | --- |
| section | text | Which block the row belongs to: `summary`, `totals_tie`, `by_sector`, `by_county`, `by_deal_type`, `by_fiscal_year`, `top_recipients`, or `deal_type_mix`. |
| rank | integer | Position within the section. Ranking sections order by dollars descending with the label as tie-breaker; `by_fiscal_year` orders by year; `deal_type_mix` orders by year then dollars. |
| measure | text | Label for `summary` and `totals_tie` rows, for example `total_deals_and_contribution` or `sum_by_county`. In `by_county` it reads `not_a_county` on the two rows whose county label does not name a county. Blank elsewhere. |
| fiscal_year | text | Fiscal year label such as `2018-2019`. Filled for `by_fiscal_year` and `deal_type_mix`. |
| nsbi_sector | text | Sector label as filed, after case and spacing folding. Filled for `by_sector` and the `top_sector` summary row. |
| nsbi_county | text | County label after the Halifax fold. Filled for `by_county` and the `top_county` summary row. |
| deal_type | text | Deal-type label as filed, after case and spacing folding. Filled for `by_deal_type`, `deal_type_mix`, and the `top_deal_type` summary row. |
| account_name | text | Recipient display name, the most frequent raw spelling of the normalized key. Filled for `top_recipients` and the `top_recipient` summary row. |
| deals | integer | Number of source deals behind the row. On `blank_contribution_deals`, `zero_contribution_deals`, `non_county_label_deals`, `deals_without_coordinates`, and `deals_outside_nova_scotia` it is the size of that counted class. |
| amount | CAD, 2 dp | Total contribution for the row. Blank on the `blank_contribution_deals` row, because a blank contribution has no dollar value to report. |
| share_pct | percent, 2 dp | The row's share of the grand total in dollars, except in `deal_type_mix`, where it is the deal type's share of its own fiscal year. 100.00 on the grand-total row. |
| yoy_change | CAD, 2 dp | Dollar change against the previous fiscal year, filled only in `by_fiscal_year`. Blank in the first year. |
| yoy_pct | percent, 2 dp | The same change as a percentage, filled only in `by_fiscal_year`. Blank in the first year. |

## bi/exports/mart_deal_book.csv (copy of out/mart_deal_book.csv)

One row per source deal, cleaned. 4,553 rows; `nsbi_financial_contribution` sums to exactly $289,279,591.01, the same grand total the deal book proves. This is the file the Tableau guide connects to.

| Column | Type | Meaning |
| --- | --- | --- |
| object_id | integer | The source row identifier, unique across the file. It is the export's sort key. |
| fiscal_year | text | Fiscal year label such as `2018-2019`. |
| fiscal_year_start | integer | First calendar year of the fiscal label, 2018 for `2018-2019`. Use it for year arithmetic and range filters; the mart has no date column. |
| nsbi_sector | text | Sector label as filed, after case and spacing folding. |
| nsbi_county | text | County label after the Halifax fold: one of Nova Scotia's 18 counties, or one of the two labels that do not name a county. |
| county_is_geographic | integer 0/1 | 0 for `province-wide` and `Not Applicable / Unknown`, 1 for a real county. Filter on 1 before giving the field a geographic role. |
| deal_type | text | Deal-type label as filed, after case and spacing folding. |
| account_name | text | Recipient display name after case and spacing normalization. |
| place_name | text | Community name as filed. |
| postalcode | text | Postal code as filed, no spaces normalized beyond the trim. |
| nsbi_financial_contribution | CAD, 2 dp | The deal's contribution. Empty when the source value was blank; never zero-filled. Zero means a genuine zero. |
| has_contribution | integer 0/1 | 0 when the source contribution was blank, 1 otherwise. |
| latitude | decimal degrees | Latitude as filed. Empty on the one deal with no coordinates. |
| longitude | decimal degrees | Longitude as filed. Negative west of the prime meridian. |
| is_mappable | integer 0/1 | 1 when both coordinates are present. |
| in_ns_bounds | integer 0/1 | 1 when the coordinate pair falls inside the `NS_BOUNDS` rectangle, latitude 43.0 to 47.5 and longitude -67.0 to -59.0. Filter the point map on this. |

## out/dash_deal_book.csv, emitted as dashboard/data.js

The dashboard cube: the same money aggregated to fiscal year by sector by county by deal type. 1,007 rows; `contribution` sums to exactly $289,279,591.01. `run.py` re-emits it as a `const DATA = [...]` literal with these field names unchanged.

| Column | Type | Meaning |
| --- | --- | --- |
| fiscal_year | text | Fiscal year label such as `2018-2019`. |
| fiscal_year_start | integer | First calendar year of the fiscal label. Sorts the year axis. |
| nsbi_sector | text | Sector label as filed. |
| nsbi_county | text | County label after the Halifax fold. |
| county_is_geographic | integer 0/1 | 0 for the two labels that do not name a county. |
| deal_type | text | Deal-type label as filed. |
| deals | integer | Deals in this combination. |
| funded_deals | integer | Of those, how many carry a contribution value. |
| blank_deals | integer | Of those, how many had a blank contribution. |
| zero_deals | integer | Of those, how many carry a contribution of exactly zero. |
| mappable_deals | integer | How many have both coordinates. |
| in_bounds_deals | integer | How many have coordinates inside Nova Scotia. |
| contribution | CAD, 2 dp | Total contribution for the combination. Blank contributions add nothing. |
