# Data dictionary

Times are UTC, matching the source column `datetimeutc`. Durations are in seconds. Percentages are `DECIMAL(9,2)`, so the CSV text is byte-stable rather than depending on float formatting.

The portal publishes no unit metadata for the measure columns. Air temperature reads as degrees Celsius and relative humidity as percent; `avg_wind_speed` carries no published unit, and its distribution in this window (median 2.4, maximum 21.0) reads as metres per second. The audit does not depend on the wind unit being resolved, because `WIND_MAX` is set above the physical ceiling under either reading.

## out/station_quality.csv (also expected/station_quality.csv)

One sectioned result file, eleven sections, 359 rows. Columns that mean nothing to a section are left blank rather than reused for something else.

| Column | Type | Meaning |
| --- | --- | --- |
| section | text | Which block the row belongs to: `headline`, `constants`, `window`, `coverage_tie`, `station_cadence`, `station_scorecard`, `completeness_ranking`, `missing_by_measure`, `gap_detail`, `frozen_detail`, or `out_of_range_detail`. |
| rank | integer | Position within the section, unique inside it. In `completeness_ranking` rank 1 is the *worst* station, since the point of the audit is what is broken. |
| site_id | text | Road weather station code, for example `RNSKM`. Blank on rows that describe the whole window. |
| reading_date | date | UTC day. Filled on the three detail sections, where it is the day the event started. |
| measure | text | What the row is about: a constant name, a window statistic, a measure name (`air_temperature`, `relative_humidity`, `avg_wind_speed`), or an event kind (`reporting_gap`, `modal_interval`, `slot_coverage`, `window_total`). |
| detail | text | The human-readable specifics: a constant's value and unit, a station's flag and the reasons behind it, a gap's start and end timestamps, a frozen run's held value and span, an out-of-range value with the bounds it broke. |
| cadence_seconds | integer, seconds | The station's derived reporting interval, the modal interval between its consecutive readings. |
| seconds | integer, seconds | Duration for event rows: the length of a gap in `gap_detail`, the span of a run in `frozen_detail`. In `station_cadence` it repeats the cadence. |
| readings_actual | integer | Readings received. In `frozen_detail` it is the run length in readings. In `coverage_tie` it holds the count being tied. |
| slots_covered | integer | Distinct cadence slots that received at least one reading. This is the numerator of `uptime_pct`. |
| readings_expected | integer | Cadence slots the window called for, the duration divided by `cadence_seconds` and rounded up. In `station_cadence` it is instead the readings a full day implies at that cadence. |
| uptime_pct | percent, 2 dp | `100 * slots_covered / readings_expected`. Bounded at 100.00 by construction. |
| share_pct | percent, 2 dp | Context percentage. In `station_cadence`, the modal interval's share of that station's measured intervals. In `missing_by_measure`, missing values as a share of readings received. |
| gap_count | integer | Gaps, meaning intervals longer than `GAP_K` times the station cadence. 1 on each `gap_detail` row. |
| frozen_run_count | integer | Runs of `FROZEN_RUN_MIN_READINGS` or more identical air temperatures. 1 on each `frozen_detail` row. |
| out_of_range_count | integer | Measure values outside their declared plausible bounds. Counted per value, so a reading failing two bounds counts twice. 1 on each `out_of_range_detail` row. |
| missing_values | integer | Blank measure values. In the scorecard and ranking it is the total across all three measures; in `missing_by_measure` it is the count for the named measure alone. |

## bi/exports/mart_station_quality.csv (copy of out/mart_station_quality.csv)

One row per station per day. 46 stations by 14 UTC days, 644 rows, no holes: a station that reported nothing on a day still gets a row and still scores zero. `readings_actual` sums to 234,835, the full snapshot.

The `station_`-prefixed columns repeat the station's window-level scorecard on every one of its fourteen rows, so a matrix or a slicer can work off one table.

| Column | Type | Meaning |
| --- | --- | --- |
| site_id | text | Road weather station code. |
| reading_date | date | UTC day. Contiguous across the window; this is the column the Power BI date table is built from. |
| cadence_seconds | integer, seconds | The station's derived reporting interval for the whole window. |
| readings_actual | integer | Readings received that day, including readings whose measure values are blank. |
| readings_expected | integer | Cadence slots the day called for. |
| slots_covered | integer | Distinct cadence slots that received at least one reading. |
| surplus_readings | integer | `readings_actual - slots_covered`: readings that landed in a slot already covered, so a station reporting faster than its own cadence. |
| uptime_pct | percent, 2 dp | `100 * slots_covered / readings_expected` for the day. 0.00 on a silent day, never above 100.00. |
| gap_count | integer | Gaps starting that day. |
| frozen_run_count | integer | Frozen air-temperature runs starting that day. |
| out_of_range_count | integer | Out-of-range measure values that day. |
| missing_air_temperature | integer | Readings that day with a blank air temperature. |
| missing_relative_humidity | integer | Readings that day with a blank relative humidity. |
| missing_avg_wind_speed | integer | Readings that day with a blank wind speed. |
| missing_values | integer | The three missing counts added together. |
| station_completeness_rank | integer | The station's rank over the whole window, 1 = worst uptime. Ties break on `site_id`. |
| station_uptime_pct | percent, 2 dp | The station's uptime over the whole window. |
| station_readings_actual | integer | The station's readings over the whole window. |
| station_readings_expected | integer | The station's expected slots over the whole window. |
| station_gap_count | integer | The station's gaps over the whole window. |
| station_frozen_run_count | integer | The station's frozen runs over the whole window. |
| station_out_of_range_count | integer | The station's out-of-range values over the whole window. |
| station_missing_values | integer | The station's missing measure values over the whole window. |
| station_days_with_no_readings | integer | Days in the window on which the station reported nothing at all. |
| station_flag | text | `flagged` or `ok`. Flagged when uptime falls below `UPTIME_FLAG_PCT`, or the station has a silent day, a frozen run, an out-of-range value, or a measure it never reported at all. |
| station_flag_reasons | text | The rules that fired, joined with `; `. Empty when the station is `ok`. |
