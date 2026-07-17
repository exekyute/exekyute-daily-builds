# Data dictionary: out/monthly_service_levels.csv

One row per month. 115 rows from 2017-01 through 2026-07. The first eleven columns describe the month; the last seven repeat that month's year totals and year rates on every one of its rows.

| # | Column | Type | Meaning | Units |
| --- | --- | --- | --- | --- |
| 1 | `month_start` | date | First day of the month (for example 2025-03-01). | date |
| 2 | `year` | integer | Calendar year of the month. | year |
| 3 | `month` | integer | Calendar month, 1 to 12. | month |
| 4 | `offered` | integer | Calls offered to the queue in the month. | count |
| 5 | `handled` | integer | Calls answered by an agent in the month. | count |
| 6 | `abandoned` | integer | Calls abandoned before an agent answered. | count |
| 7 | `processed_in_ivr` | integer | Calls resolved in the automated menu without reaching an agent. | count |
| 8 | `total_talk_time` | integer | Total agent talk time in the month. | seconds |
| 9 | `abandonment_rate` | number | `abandoned` over `offered`, a fraction in [0, 1] to four decimals. 0.0275 is 2.75 percent. | fraction |
| 10 | `answer_rate` | number | `handled` over `offered`, a fraction in [0, 1] to four decimals. | fraction |
| 11 | `avg_talk_time` | number | `total_talk_time` over `handled`, one decimal. | seconds per handled call |
| 12 | `year_offered` | integer | Calls offered across the whole year. | count |
| 13 | `year_handled` | integer | Calls handled across the whole year. | count |
| 14 | `year_abandoned` | integer | Calls abandoned across the whole year. | count |
| 15 | `year_processed_in_ivr` | integer | Calls processed in IVR across the whole year. | count |
| 16 | `year_total_talk_time` | integer | Total agent talk time across the whole year. | seconds |
| 17 | `year_abandonment_rate` | number | `year_abandoned` over `year_offered`, a fraction to four decimals. A ratio of summed counts, so it weights each month by call volume. | fraction |
| 18 | `year_answer_rate` | number | `year_handled` over `year_offered`, a fraction to four decimals. | fraction |

Notes:

- Columns 12 through 18 hold the same value on every row of a given year, since they describe the year, not the single month.
- A fraction rate reads as a percentage when multiplied by 100: `year_abandonment_rate` 0.0275 is 2.75 percent.
- Rates are guarded against a zero denominator and would render as empty cells if a month or year had zero offered or zero handled calls. No row in the current snapshot triggers that.
