# Data dictionary: frozen BI marts

Two marts, written by the SQL export step and imported by the Power BI report.
Power BI recomputes nothing structural: it binds to these frozen figures, so the
report reads the same totals the SQL golden holds. Both files are byte-for-byte
identical to the golden in `expected/`. All usage figures are integer hit counts.

## mart_usage_monthly.csv

One row per month, 136 rows from 2014-07 to 2025-10. Ordered by `month_start`.
This is the fact table the Total Usage measure and the usage line chart bind to.

| # | Column | Type | Meaning |
| --- | --- | --- | --- |
| 1 | `month_start` | date | First day of the month, `YYYY-MM-DD`. |
| 2 | `year` | integer | Calendar year of `month_start`. |
| 3 | `total_usage` | integer | Sum of every dataset's recorded usage in the month. |
| 4 | `distinct_datasets` | integer | Number of datasets that drew at least one hit in the month. |

## mart_usage_by_dataset.csv

One row per dataset, 237 rows. Ordered by `total_usage` descending, then
`dataset`. This is the table the ranked bar and the Dataset Rank measure bind to.

| # | Column | Type | Meaning |
| --- | --- | --- | --- |
| 1 | `dataset` | text | Open-data item name, as carried inline by the source. |
| 2 | `total_usage` | integer | Total recorded usage for the dataset over the window. |
| 3 | `first_month` | date | First month the dataset drew usage, `YYYY-MM-DD`. |
| 4 | `last_month` | date | Last month the dataset drew usage, `YYYY-MM-DD`. |
| 5 | `usage_rank` | integer | Rank by `total_usage`, highest first (competition ranking, ties share and skip). |

## Totals to check after import

- Power BI, `mart_usage_monthly`: `SUM(total_usage)` = **555,050,254**; row count
  **136**.
- Power BI, `mart_usage_by_dataset`: `SUM(total_usage)` = **555,050,254**; row
  count **237**; the rank-1 dataset is **Zoning Boundaries** at **91,508,850**.
