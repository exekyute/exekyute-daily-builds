# Data dictionary: out/commodity_mix.csv

One row per commodity per fiscal year, after cleaning. Ordered by `commodity`, then `fiscal_year`.

| Column | Type | Units | Meaning |
| --- | --- | --- | --- |
| `commodity` | text | none | Canonical commodity label, after trimming and folding singular and plural spellings (for example Beef, Apple, Maple, Honey, Bees, Pollination). |
| `fiscal_year` | text | fiscal year | The fiscal year, for example `2015-2016`. Ten values span 2015-2016 to 2024-2025. |
| `farms` | integer | farms | Registered farms for this commodity in this fiscal year, after cleaning. |
| `year_total_farms` | integer | farms | Total registered farms across all commodities in this fiscal year. The denominator for `share_pct`. |
| `share_pct` | number | percent | `farms` as a percent of `year_total_farms`, rounded to two decimals. This commodity's share of the year's mix. |
| `prev_year_farms` | integer | farms | `farms` for the same commodity in the immediately preceding fiscal year. Empty when the commodity was absent that year (no adjacent prior year). |
| `yoy_change_farms` | integer | farms | `farms` minus `prev_year_farms`. Positive means more farms than the prior year. Empty when there is no adjacent prior year. |
| `yoy_pct` | number | percent | Percent change in farms from the prior year, `100 * (farms - prev_year_farms) / prev_year_farms`, rounded to two decimals. Empty when there is no adjacent prior year or the prior count is zero. |

Notes:

- `share_pct` and `yoy_pct` are fixed to two decimals for a stable, diffable file. A trailing zero can drop in the CSV (22.90 prints as 22.9); the value is unchanged.
- Empty cells in `prev_year_farms`, `yoy_change_farms`, and `yoy_pct` are genuine nulls (no comparable prior year), not zeros.
