# Data dictionary: mart_311_monthly.csv

The frozen mart both dashboards read. One row per month, 115 rows from 2017-01 through 2026-07, ordered by `month_start`. It is the per-month subset of the analytical golden: it keeps the calendar `year` for slicing but drops the golden's seven `year_`-prefixed rollup columns, so each dashboard derives the year figures itself and Tableau and Power BI land on the same numbers from the same file.

| # | Column | Type | Meaning | Units |
| --- | --- | --- | --- | --- |
| 1 | `month_start` | date | First day of the month (for example 2025-03-01). Bind as a Date and as the Power BI date-table key. | date |
| 2 | `year` | whole number | Calendar year of the month. | year |
| 3 | `month` | whole number | Calendar month, 1 to 12. | month |
| 4 | `offered` | whole number | Calls offered to the queue in the month. | count |
| 5 | `handled` | whole number | Calls answered by an agent in the month. | count |
| 6 | `abandoned` | whole number | Calls abandoned before an agent answered. | count |
| 7 | `processed_in_ivr` | whole number | Calls resolved in the automated menu without reaching an agent. | count |
| 8 | `total_talk_time` | whole number | Total agent talk time in the month. | seconds |
| 9 | `abandonment_rate` | decimal | `abandoned` over `offered`, a fraction in [0, 1] to four decimals. 0.0275 is 2.75 percent. | fraction |
| 10 | `answer_rate` | decimal | `handled` over `offered`, a fraction in [0, 1] to four decimals. | fraction |
| 11 | `avg_talk_time` | decimal | `total_talk_time` over `handled`, one decimal. | seconds per handled call |

For a year-level rate, aggregate the counts and divide, rather than averaging the per-month `abandonment_rate`: a Tableau calculated field `SUM([abandoned]) / SUM([offered])` or the Power BI measure `DIVIDE ( [Total Abandoned], [Total Offered] )`. That ratio of sums weights each month by its call volume and is the figure the SQL golden reports as `year_abandonment_rate`. Averaging the per-month rates does not reproduce it: for 2025 that returns 2.61 percent against the true 2.75 percent.
