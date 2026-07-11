# Data dictionary: out/surplus_league.csv

One row per municipality per fiscal year, 554 rows. Currency is Canadian dollars throughout, kept to two decimals.

| Column | Type | Meaning |
| --- | --- | --- |
| `year` | text | Fiscal year label, for example `2023-24` (the year running April 1 to March 31). |
| `region` | text | Municipality name as published in the dataset. |
| `region_type` | text | Municipality class: `Town`, `Rural Municipality`, or `Regional Municipality`. Paired with `region` it identifies the municipality, since a few names belong to both a Town and a Rural Municipality. |
| `total_revenues` | decimal(18,2), CAD | Total operating revenue for the year. |
| `total_expenditures` | decimal(18,2), CAD | Total operating expenditure for the year. |
| `operating_surplus` | decimal(18,2), CAD | `total_revenues` minus `total_expenditures`. Positive is a surplus, negative a deficit. |
| `surplus_rank_in_year` | integer | Rank within the fiscal year by `operating_surplus`, largest first (1 = largest surplus). Ties share a rank. |
| `deficit_rank_in_year` | integer | Rank within the fiscal year by `operating_surplus`, smallest first (1 = largest deficit). Ties share a rank. |
| `municipalities_in_year` | integer | How many municipalities are ranked that fiscal year (the field size behind the ranks). |
| `prior_year_surplus` | decimal(18,2), CAD | The same municipality's `operating_surplus` in the previous fiscal year. Empty in its first observed year. |
| `yoy_surplus_change` | decimal(18,2), CAD | `operating_surplus` minus `prior_year_surplus`. Positive means the surplus grew (or the deficit shrank) from the prior year. Empty in a first observed year. |
| `years_observed` | integer | How many fiscal years this municipality appears in with a computable surplus. |
| `mean_surplus` | decimal(18,2), CAD | This municipality's average `operating_surplus` across its observed years, rounded to the cent. A trend baseline, repeated on each of its rows. |
