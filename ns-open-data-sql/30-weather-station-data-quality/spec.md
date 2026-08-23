# Spec: weather-station data-quality auditor

## Purpose

Audit the province's road weather information network the way an operator would: how much of the time did each station actually report, where did it go quiet, where did a sensor stop moving, and where did it send a value that cannot be real. Every figure is deterministic and re-derivable from the committed snapshot, and nothing in the pipeline assumes how often a station is supposed to report.

## Inputs

One file: `data/raw/ns_weather-station_2026-07-25.csv`, a pinned snapshot of Socrata dataset `kafq-j9u4` (see SOURCE.md). Five columns: `site_id`, `datetimeutc`, `air_temperature`, `relative_humidity`, `avg_wind_speed`. 234,835 rows covering 46 stations over fourteen whole UTC days.

## The narrowing decision and why

The live table is 31.8 million rows, so the audit needs a window before it needs anything else. January 2024 is the right month for a road weather network: winter is when the stations matter and when most of them are reporting. The whole month came to 522,003 rows, roughly 27 MB at the measured row width, over the 25 MB snapshot ceiling, so the window was cut to the first fourteen days of the month. Fourteen whole days is still long enough for a station's cadence to establish itself and for multi-day outages to show up as outages rather than as edge effects. SOURCE.md records the exact query and both counts.

Days are UTC days, matching the timestamp column. Shifting to Atlantic time would move readings across the window boundary and leave the first and last audited days partial, which would put two artificial dips in a completeness chart.

## Deriving the cadence, and why the naive reading of "modal interval" is wrong

Nothing here hardcodes a reporting rate. Each station's cadence is measured: take every interval between consecutive readings for that station, count them, and keep the most common value. Ties break on the shorter interval so the expectation never falls below what the station demonstrably sustains.

That works on this window because the January cadence is genuinely regular. 43 of 46 stations report every 240 seconds, `RNSCA` and `RNSSI` every 120, and `RNSWM` every 600. The weakest modal share is `RNSWA` at 85.34 percent of its intervals; the strongest is `RNSBW` at 99.70 percent. No station fell below `MIN_INTERVALS_FOR_MODE`, so the fallback never fired.

The reason to be careful is that this network is not always that regular. Sampled outside winter, the same stations run at irregular offsets, something like five readings an hour landing at 10, 15, 25, 40 and 55 past. The intervals there are 5, 10, 15, 15 and 15 minutes, so the modal interval is 15 minutes and a denominator of `86400 / 900` gives 96 expected readings a day against 120 actual. That is 125 percent uptime, which is not a number a completeness audit is allowed to print.

So the audit measures **slot coverage** rather than a raw count ratio:

- A **slot** is one cadence period inside the day. A 240-second station has 360 slots in a 86,400-second day.
- A slot is **covered** when at least one reading falls in it: `slot_index = floor(seconds_since_day_start / cadence_seconds)`.
- `uptime_pct = 100 * slots_covered / readings_expected`.

Because slot indices run `0 .. readings_expected - 1` by construction, coverage can never exceed the expectation, whatever the station does inside a slot. A station that bursts above its own cadence still shows its full raw count in `readings_actual`; the excess lands in `surplus_readings` and is reported, never dropped. `RNSCB` on 2024-01-11 is the live case: it emitted 588 readings against 360 expected by alternating 60-second and 180-second intervals. Slot coverage reads 360 of 360, uptime 100.00 percent, surplus 228.

`readings_expected` is the day's duration divided by the station's cadence, rounded up to a whole reading. The day's duration is the overlap of the calendar day with the declared window, in seconds, so a leap day, a short month, or a window that starts mid-day cannot break the denominator. There is no 24, no 8760, no 8784 anywhere in the SQL.

## Named constants

All of them live in one place, `audit_constants` in `sql/00_schema.sql`, and all of them are echoed into the `constants` section of the golden output so a reader never has to open the SQL to know what was applied.

| Constant | Value | Justification |
| --- | --- | --- |
| `WINDOW_START` | `2024-01-01` | Inclusive UTC date. A literal, never `CURRENT_DATE`, so the golden output does not drift. |
| `WINDOW_END_EXCL` | `2024-01-15` | Exclusive UTC date. Fourteen whole days. |
| `GAP_K` | 3 | An interval longer than three times the station's own cadence is a gap. Two would fire on ordinary telemetry jitter, since a single skipped reading already doubles the interval. Three needs two consecutive misses, which is a station that stopped rather than a station that stuttered. At 240 seconds that is a twelve-minute silence. |
| `FROZEN_RUN_MIN_READINGS` | 30 | Air temperature is published to 0.1 degrees. Thirty identical readings in a row is two hours of a 240-second station never moving a tenth of a degree, which does not happen in January weather. Twenty would catch calm overnight stretches (70 runs in this window); thirty catches 12. Because the threshold counts readings rather than minutes, the wall-clock span differs for the three off-cadence stations: 30 readings is two hours at 240 seconds, one hour at 120, five hours at 600. |
| `MIN_INTERVALS_FOR_MODE` | 30 | Below thirty measured intervals a station's mode is noise, so it inherits the window-wide modal interval instead and is labelled `window fallback` in the output. No station needed it here. |
| `UPTIME_FLAG_PCT` | 99.0 | One percent of a fourteen-day window at 240 seconds is about 50 missing readings, roughly three and a half hours of silence. Past that a station is having an outage, not a bad afternoon. |
| `AIR_TEMP_MIN_C` | -50.0 | Nova Scotia's record low is -41.1 C. The bound sits nine degrees below it, so no real cold snap trips the flag. |
| `AIR_TEMP_MAX_C` | 45.0 | Nova Scotia's record high is 38.3 C. Same idea from the other end. |
| `RH_MIN_PCT` | 1.0 | Outdoor air in Nova Scotia does not reach one percent relative humidity. The first percentile in this snapshot is 52 percent. Every reading below the bound turns out to be exactly 0.0 inside a frame where air temperature and wind speed are also exactly 0.0, which is a fault frame, not weather. |
| `RH_MAX_PCT` | 100.0 | Definitional. Saturation at exactly 100.0 is common in a Nova Scotia January (19,919 readings here) and is not flagged. |
| `WIND_MIN` | 0.0 | Wind speed cannot be negative in any unit. |
| `WIND_MAX` | 200.0 | The portal publishes no unit for `avg_wind_speed` and the column carries no description. The distribution (median 2.4, 99th percentile 13.3, maximum 21.0) reads as metres per second, but the bound is set above the physical ceiling under the *other* reading, kilometres per hour, so a real gale is never flagged whichever unit is correct. The check is aimed at sentinel values and sign errors, not at meteorological extremes. |

## Detection rules

**Gaps.** An interval longer than `GAP_K` times the station's cadence. Dated by the reading that starts the gap, because that is the moment reporting stopped. 36 in this window. The longest is `RNSKM` going quiet for 203,220 seconds, 846.8 times its cadence, from 2024-01-04T04:21:00 to 2024-01-06T12:48:00.

**Frozen sensors.** A gap-and-island pattern over the reading stream: number the readings per station by time, number them again per station *and value* by time, and subtract. The difference is constant across a contiguous run of one value and changes the moment the value changes, which gives each run a group id to aggregate on. Runs of `FROZEN_RUN_MIN_READINGS` or more are reported.

A missing air temperature sits in its own value partition, so a dropout breaks a run rather than bridging two identical stretches on either side of it. Runs of missing values are discarded here and counted as missing values instead. The longest real run is `RNSCP` holding -1.5 C for 62 readings, just over four hours.

The rule has one known limit. A run is contiguous in the *reading stream*, not in wall-clock time, so a station that went silent and came back on the same value would show one run rather than two. It does not bite in this window: dividing each run's `seconds` by `readings_actual - 1` gives the station's exact cadence for nine of the twelve runs, and for the other three (`RNSTN`, `RNSLV`, `RNSCA`) it comes to at most 1.03 times the cadence, which is a single skipped sample inside the run rather than an outage bridged by it. The golden output carries every run's duration in seconds so a reader can redo that check without rerunning anything.

**Out-of-range values.** Each measure is checked against its named bounds. The count is of offending measure *values*, not rows, so a reading that failed two bounds would count twice. Missing is never out of range; missing is counted separately. Six values in this window, all `relative_humidity` at exactly 0.0.

## Exclusion classes, all counted

Nothing is dropped quietly. The `window` section of the golden output reports every class, and the `coverage_tie` section re-proves it from the far end by re-summing readings three ways:

| Class | Count |
| --- | --- |
| Snapshot rows | 234,835 |
| Rows with an unparseable timestamp | 0 |
| Rows outside the declared window | 0 |
| Readings kept | 234,835 |
| Values present but not parseable as a number | 0 for all three measures |

Missing measure values are kept, not excluded: the reading arrived, the measurement did not. 41,711 of the 704,505 measure values in the snapshot are blank (19,902 air temperature, 19,968 relative humidity, 1,841 wind speed), reported per station and per measure in `missing_by_measure`.

## The mart grain

`bi/exports/mart_station_quality.csv` is **one row per station per day**: 46 stations by 14 days, 644 rows, no holes. The station-day rows come from a cross join of the stations against the window's calendar dates, not from the data, so a station that went completely silent on a day still gets a row and still scores zero rather than vanishing from the denominator. `RNSKM` has two such days.

`reading_date` is a real contiguous date column, which is what the Power BI date table is built from. Each row also carries the station-level scorecard values as `station_`-prefixed columns so the flagged-station matrix is buildable without a second table.

## Outputs

- `out/station_quality.csv`, diffed against `expected/station_quality.csv`: the sectioned audit result, eleven sections, 359 rows.
- `out/mart_station_quality.csv`, copied to `bi/exports/mart_station_quality.csv`: the station-day BI mart, 644 rows.

## Edge cases

- **A station too sparse to establish a mode** inherits the window-wide modal interval and is labelled `window fallback` in the `station_cadence` section. Zero stations needed it here, but the branch is live.
- **Silent days.** `RNSKM` reported nothing on 2024-01-05 and 2024-01-09. Those days are rows in the mart at 0.00 percent, and they are why it ranks last at 59.78 percent.
- **Over-reporting.** Slot coverage caps at 100 percent by construction, so a burst never inflates uptime. The surplus is carried in its own column instead. 1,123 surplus readings across the window, 228 of them on one `RNSCB` day.
- **Dead sensors.** `RNSMF` and `RNSSI` reported air temperature and relative humidity zero times in fourteen days while their wind channel kept working. Their uptime is near the network average, which is exactly why the audit reports missing values separately from completeness: a station can be perfectly punctual and still be sending nothing useful.
- **Ties.** Completeness percentages tie constantly, so every ranking breaks on `site_id` and every export carries a total `ORDER BY` ending in a unique key.

## Determinism

Window bounds are literal `DATE` constants; nothing reads the clock. Every threshold is a named constant in one table, echoed into the output. Every result query ends in a total `ORDER BY` whose last key is unique (`site_id`, plus `reading_date` where the grain is daily), so no ordering depends on scan order, engine version, or thread count. Percentages are `DECIMAL(9,2)` so the CSV text is byte-stable rather than depending on float formatting.
