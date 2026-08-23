# Data dictionary

All hour figures are closure hours as reported by Nova Scotia Open Data, carried
as `DECIMAL(18,1)` in SQL and written to CSV with one decimal place. Percentages
are rounded to two decimals for display; the division itself runs on exact
decimals. A blank percentage means the denominator was zero, not that the value
is zero.

## out/ed_closures.csv (also expected/ed_closures.csv)

One sectioned result file, 127 data rows. Columns that do not apply to a section
are blank.

| Column | Type | Meaning |
| --- | --- | --- |
| section | text | Which block the row belongs to: `summary`, `row_accounting`, `reconciliation`, `zone_totals`, `type_totals`, `zone_year`, or `site_totals`. |
| rank | integer | Position within the section. Ranking sections order by total hours descending with the label as tie-breaker; `zone_year` orders by zone then fiscal year; the three measure sections keep a fixed reading order. |
| measure | text | Label for `summary`, `row_accounting`, and `reconciliation` rows, for example `total_closure_hours` or `rows_mismatched`. Blank in the breakdown sections. |
| fiscal_year | text | Fiscal year label as reported, for example `2023-24`. Filled for `zone_year` rows. |
| fiscal_year_start | integer | First calendar year of the fiscal label, so `2023-24` gives 2023. This is the sortable year, used for ordering, for the `LAG`, and for the year-index pattern in DAX. Filled for `zone_year` rows. |
| zone | text | Management zone code as reported: `1`, `2`, `3`, `4`, or `IWK`. Filled for `zone_totals`, `zone_year`, and `site_totals` rows. |
| facility_type | text | Facility type: `CEC`, `Community`, `Regional`, `Tertiary`, or `UTC`. In `type_totals` it is the type reported in that site-year. In `site_totals` it is the type the site reported in its most recent observed year. |
| site | text | Facility name after canonicalization. Filled for `site_totals` rows. |
| site_years | integer | Number of site-year rows behind the figure. In the three measure sections this column carries the count the measure names, for example 456 for `rows_in_snapshot` and 38 for `sites_observed`. |
| zero_site_years | integer | How many of those site-years reported 0.0 total hours. |
| total_hours | hours, 1 dp | Total closure hours for the row. In the `reconciliation` section it carries the hours-valued measures (`mismatch_total_abs_hours`, `mismatch_max_abs_hours`). |
| temporary_hours | hours, 1 dp | Temporary (unplanned) closure hours. |
| scheduled_hours | hours, 1 dp | Scheduled closure hours. |
| temporary_share_pct | percent, 2 dp | `temporary_hours` divided by `total_hours`, in percent. Blank where `total_hours` is 0.0. |
| yoy_change_hours | hours, 1 dp | In `zone_year`, total hours minus the same zone's previous fiscal year. Blank in a zone's first year. |
| yoy_change_pct | percent, 2 dp | The same change as a percent of the previous year. Blank in a zone's first year and blank where the previous year was 0.0. |

### Section contents

| Section | Rows | What it holds |
| --- | --- | --- |
| `summary` | 8 | Provincial totals and the counts that describe the snapshot: sites, fiscal years, zero-closure site-years, sites at zero throughout, sites whose facility type changed, facility types with any hours, and site-years where the share denominator guard fired. |
| `row_accounting` | 6 | The row ledger: snapshot rows, one line per exclusion class, and the clean row count. |
| `reconciliation` | 5 | The `temporary + scheduled = total` check: rows checked, rows reconciled, rows mismatched, and the total and largest absolute break in hours. |
| `zone_totals` | 5 | Closure hours by zone across all twelve years. |
| `type_totals` | 5 | Closure hours by the facility type reported in each site-year. |
| `zone_year` | 60 | Each zone in each fiscal year, with year-over-year change. |
| `site_totals` | 38 | Every site ranked by total closure hours, including the 13 that reported none. |

## bi/exports/mart_ed_closures.csv (copy of out/mart_ed_closures.csv)

One row per source site-year, cleaned. 456 rows; `total_hours` sums to exactly
520,811.3, the same provincial total the golden file proves. This is the file
Power BI imports and the file `dashboard/data.js` is generated from.

| Column | Type | Meaning |
| --- | --- | --- |
| fiscal_year | text | Fiscal year label as reported, for example `2023-24`. Use it for axis labels, not for sorting. |
| fiscal_year_start | integer | First calendar year of the fiscal label (2023 for `2023-24`). Sort the fiscal year column by this one, and use it for the year-index YoY pattern in DAX. The mart has no date column, so this integer is the only year arithmetic available. |
| zone | text | Management zone code as reported: `1`, `2`, `3`, `4`, or `IWK`. Text, not a number, because `IWK` is one of the values. |
| facility_type | text | Facility type reported for this site in this fiscal year: `CEC`, `Community`, `Regional`, `Tertiary`, or `UTC`. Eight sites report two different types over the window, so this is a site-year attribute rather than a site attribute. |
| site | text | Facility name after canonicalization: apostrophes folded to ASCII, and `Roseway` written as `Roseway Hospital`. |
| temporary_hours | hours, 1 dp | Temporary (unplanned) closure hours in that site-year. |
| scheduled_hours | hours, 1 dp | Scheduled closure hours in that site-year. |
| total_hours | hours, 1 dp | Total closure hours as reported. Equals `temporary_hours + scheduled_hours` on all 456 rows. |
| is_zero_closure | integer 0/1 | 1 when the site reported 0.0 total hours that year. 238 rows carry a 1. |

## dashboard/data.js

Generated by `run.py` from the mart, one JavaScript object per mart row with the
same nine fields and the same values. It holds no figures of its own; the
dashboard derives every number it displays from these rows.
