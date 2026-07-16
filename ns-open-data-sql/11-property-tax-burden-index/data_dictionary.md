# Data dictionary

`out/tax_burden_index.csv` and `bi/exports/mart_tax_burden.csv` carry the same
columns; the mart is the copy Power BI and the dashboard read. One row per
municipality per fiscal year, where a municipality is the pair
`(area, area_type)`: six names (Antigonish, Digby, Lunenburg, Pictou,
Shelburne, Yarmouth) are both a Town and a Rural Municipality. Rows are
ordered by `year_start`, then `rank_in_year`, then `area`, then `area_type`.

| Column | Type | Meaning |
| --- | --- | --- |
| `area` | text | Municipality name as published, trimmed. Not unique on its own; pair with `area_type`. |
| `area_type` | text | Municipality class as published (Town, Rural Municipality, Halifax Regional, Cape Breton Regional, Region of Queens, West Hants Regional Municipality). |
| `year_label` | text | Fiscal year as published, for example `2025/2026`. |
| `year_start` | integer | First calendar year of the fiscal label (`2025/2026` gives 2025). Used for ordering and LAG. |
| `residential_rate` | double | General residential tax rate, dollars per $100 of assessed value. |
| `commercial_rate` | double | General commercial tax rate, dollars per $100 of assessed value. |
| `spread` | double | `commercial_rate - residential_rate`, rounded to 4 decimals. The burden index: how much heavier the commercial rate is. |
| `rank_in_year` | integer | RANK() of `spread` within `year_start`, widest spread ranked 1. Ties share a rank. |
| `yoy_spread_change` | double, nullable | `spread` minus the same municipality's previous observed year (LAG over `year_start`), rounded to 4 decimals. Empty in a municipality's first observed year. |
| `is_outlier` | boolean | True only in the latest year, for municipalities whose `spread` is at or above the 90th percentile (`quantile_cont(0.90)`) of latest-year spreads. False everywhere else. |
