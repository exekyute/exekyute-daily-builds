# Data dictionary: out/toxicology_trend.csv

One row per year (2015 to 2024) and one row per calendar month (pooled across all years). Twenty-two rows plus a header.

| Column            | Type          | Meaning | Units |
|-------------------|---------------|---------|-------|
| `dimension`       | text          | Which slice the row belongs to: `year` or `month`. | category |
| `period`          | text          | The period label: a four-digit year (for example `2018`) on year rows, or a three-letter month (for example `Aug`) on month rows. | year or month |
| `period_num`      | integer       | Sort key: the year (for example `2018`) on year rows, or the month number 1 to 12 on month rows. | ordinal |
| `total_deaths`    | integer       | All driver deaths in the period. Equals positive + not_detected + tox_unavailable. | deaths (count) |
| `positive`        | integer       | Driver deaths where one or more specified drugs were detected. | deaths (count) |
| `not_detected`    | integer       | Driver deaths where specified drugs were not detected. | deaths (count) |
| `tox_unavailable` | integer       | Driver deaths with no toxicology result available (unknown or pending). | deaths (count) |
| `pct_positive`    | decimal (5,1) | Positive share among drivers who had a result: 100 x positive / (positive + not_detected), to one decimal. `tox_unavailable` is excluded from the denominator. | percent |

Notes:

- On month rows, `period_num` is the calendar month (Jan = 1 through Dec = 12) and the counts are pooled across 2015 to 2024.
- `pct_positive` is always written with one decimal place (for example `50.0`).
