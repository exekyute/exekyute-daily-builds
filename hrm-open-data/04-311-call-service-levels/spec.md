# Spec

## Purpose

Take a pinned snapshot of Halifax's 311 call volumes at the half-hour-interval grain and produce one deterministic monthly table that answers three things: how many calls were offered, handled, and abandoned each month, what the derived service rates were, and how each month sits against the totals and rates for the year it belongs to. A headline reads the latest full year.

## Inputs

Dataset: 311 Call Volumes (`HRM::311-call-volumes`), pulled to `data/raw/hrm_311-call-volumes_2026-07-09.csv`. See SOURCE.md.

Columns used: `CALL_DATE`, `OFFERED`, `HANDLED`, `ABANDONED`, `PROCESSED_IN_IVR`, `TOTAL_TALK_TIME`. The other source columns (`MILITARY_HOUR`, `INTERVAL`, `AVERAGE_TALK_TIME`, `ObjectId`) are landed for fidelity but not used in the rollup.

## Cleaning and validation rules (02_transform.sql)

1. Parse `CALL_DATE` to a `DATE`. The Hub CSV renders the field as a formatted local datetime string such as `1/3/2017 8:00:00 AM`. `try_strptime` with format `%-m/%-d/%Y %-I:%M:%S %p` parses it; casting to `DATE` keeps the calendar date and drops the time. The time portion is a constant display artifact (only ever 07:00 or 08:00, a daylight-saving offset), well clear of midnight, so the month, day, and year are the true call date.
2. Cast `OFFERED`, `HANDLED`, `ABANDONED`, `PROCESSED_IN_IVR` to integers and `TOTAL_TALK_TIME` to a big integer (seconds).
3. Drop any row whose `CALL_DATE` fails to parse or whose `OFFERED` value is null or blank. A count of zero is valid (overnight intervals) and is kept.

The result, `calls_clean`, is one clean, typed row per source interval carrying a real date.

## Analysis logic step by step (03_analysis.sql)

The build runs three tables plus a headline table. Every rate is stored as a fraction in [0, 1] rounded to four decimals (0.0275 is 2.75 percent); talk time is in seconds. Every ratio guards its denominator, so a zero-offered or zero-handled group yields null rather than a divide-by-zero. The current snapshot has no such group, so the guard never fires and the output is unaffected.

**calls_monthly** (one row per month). Groups `calls_clean` by `date_trunc('month', call_date)` and reads:

- `month_start`, `year`, `month` (calendar parts of the month).
- `offered`, `handled`, `abandoned`, `processed_in_ivr`, `total_talk_time` as `SUM` of the interval counts.
- `abandonment_rate` = `round(abandoned / offered, 4)`.
- `answer_rate` = `round(handled / offered, 4)`.
- `avg_talk_time` = `round(total_talk_time / handled, 1)`, seconds per handled call.

**calls_yearly** (one row per year). Rolls `calls_monthly` up to the year:

- `year_offered`, `year_handled`, `year_abandoned`, `year_processed_in_ivr`, `year_total_talk_time` as `SUM` of the monthly totals.
- `year_abandonment_rate` = `round(year_abandoned / year_offered, 4)`.
- `year_answer_rate` = `round(year_handled / year_offered, 4)`.

Because the year rate is a ratio of summed counts, it weights each month by that month's call volume, which is the correct annual service level and differs from a plain average of the twelve monthly rates.

**monthly_service_levels** (one row per month, the exported golden). Joins each month to its year summary from `calls_yearly` on `year`, so every monthly row also carries the year totals and year rates. The year columns repeat on every month of a given year.

**headline** (two rows). Finds the latest full year (the greatest `year` for which all twelve months are present in `calls_monthly`), reads that year's row from `calls_yearly`, and writes two ready-to-print lines: the offered, handled, and abandoned totals, and the abandonment and answer rates as percentages. `run.py` prints these; it does not compute them.

## Outputs

`out/monthly_service_levels.csv` (generated) and `expected/monthly_service_levels.csv` (golden, committed), 115 rows, one per month from 2017-01 through 2026-07. Every column is defined in data_dictionary.md.

`bi/exports/mart_311_monthly.csv` (frozen mart, committed), the same 115 months projected to the eleven per-month columns only (`month_start` through `avg_talk_time`). It keeps the calendar `year` but drops all seven of the golden's `year_`-prefixed rollup columns, so each dashboard derives the year figures itself and the two tools land on the same numbers. Its columns are documented in bi/exports/data_dictionary.md.

Row order in both files is fixed by `ORDER BY month_start` in 99_export.sql, oldest month to newest.

## Headline figures (2025, the latest full year)

- Calls offered: **365,053**.
- Calls handled: **237,671**.
- Calls abandoned: **10,037**.
- Abandonment rate: **2.75 percent** (`year_abandonment_rate` 0.0275).
- Answer rate: **65.11 percent** (`year_answer_rate` 0.6511).

The abandonment rate is the figure the faces must agree on. It reads 2.75 percent in this golden, on the Tableau heatmap's 2025 column grand total, and on the Power BI Abandonment Rate card, because all three compute it as 10,037 over 365,053. Averaging the twelve monthly rates instead returns 2.61 percent and does not tie, which is why every rate here is a ratio of summed counts.

Across the nine full years 2017 to 2025 the annual abandonment rate runs from 2.75 percent in 2025 up to 7.01 percent in 2023.

## Edge cases

- **Partial 2026:** the snapshot ends on 2026-07-04, so 2026 holds seven months, not twelve. It appears in the monthly series and per-year summary but is not the latest full year; that is 2025. The "full year" test counts distinct months per year and requires twelve.
- **Divide by zero:** guarded in every rate with a `CASE` on the denominator. No month in the snapshot has zero offered or zero handled calls.
- **Date parse failure:** a row whose `CALL_DATE` will not parse is dropped in cleaning before any arithmetic. All 145,363 rows parse in the current snapshot.
- **Duplicate intervals:** the monthly `SUM` collapses any repeated interval into the month total, so a stray duplicate could not make the rollup non-deterministic.

## Determinism

The snapshot is pinned and committed. Every result query ends in an `ORDER BY`, dates come from the parsed `CALL_DATE` rather than `CURRENT_DATE`, and rates are rounded to four decimals, so the same input always produces byte-identical output. `expected/monthly_service_levels.csv` was built from a first verified run; `run.py` re-runs the pipeline and diffs the fresh output against it, printing PASS only on an exact row-for-row match.
