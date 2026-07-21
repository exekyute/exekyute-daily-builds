# Data dictionary: out/ golden marts

Two output files, both written by the SQL export step and diffed against
`expected/`. The same two files are frozen to `bi/exports/` for Power BI, byte for
byte. All usage figures are integer hit counts.

## mart_usage_monthly.csv

One row per month, 136 rows from 2014-07 to 2025-10. Ordered by `month_start`.

| # | Column | Type | Meaning | Units |
| --- | --- | --- | --- | --- |
| 1 | `month_start` | date | First day of the month, `YYYY-MM-DD`. | date |
| 2 | `year` | integer | Calendar year of `month_start`. | year |
| 3 | `total_usage` | integer | Sum of every dataset's recorded usage in the month. | count |
| 4 | `distinct_datasets` | integer | Number of datasets that drew at least one hit in the month. | count |

## mart_usage_by_dataset.csv

One row per dataset, 237 rows. Ordered by `total_usage` descending, then
`dataset`.

| # | Column | Type | Meaning | Units |
| --- | --- | --- | --- | --- |
| 1 | `dataset` | text | Open-data item name, as carried inline by the source. | text |
| 2 | `total_usage` | integer | Total recorded usage for the dataset over the window. | count |
| 3 | `first_month` | date | First month the dataset drew usage, `YYYY-MM-DD`. | date |
| 4 | `last_month` | date | Last month the dataset drew usage, `YYYY-MM-DD`. | date |
| 5 | `usage_rank` | integer | Rank by `total_usage`, highest first. Competition ranking: tied totals share a rank and the next rank skips. 1 is the most-used dataset. | rank (1 = top) |

## Totals to check

- `mart_usage_monthly`: `SUM(total_usage)` = **555,050,254** across 136 months.
- `mart_usage_by_dataset`: `SUM(total_usage)` = **555,050,254** across 237
  datasets. Both marts tie to the same figure, and it matches the live
  `SUM(Usage)` confirmed against the FeatureServer.
- The `usage_rank = 1` dataset is **Zoning Boundaries** at **91,508,850** hits.
