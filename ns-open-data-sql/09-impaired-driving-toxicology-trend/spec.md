# Spec

## Purpose

Summarize Nova Scotia motor vehicle driver deaths by toxicology outcome. Produce, in one table: the outcome counts for each year from 2015 to 2024, the percent of drivers who tested positive each year, and the count of deaths by calendar month pooled across all years.

## Inputs

Dataset: Motor Vehicle Driver Deaths (`huvt-4vtx`), pinned snapshot in `data/raw/`. Columns used:

- `driver_toxicology_results`: the toxicology category label.
- `frequency`: the count of driver deaths for the row.
- `year`: calendar year, set only on the by-year rows.
- `month`: three-letter month, set only on the by-month rows.

`percent_annual`, `percent_total_all_years`, and `sex` are present in the source but are not used. Percentages are recomputed here from the counts; the by-sex slice is out of scope.

## Cleaning and validation rules

1. Load every column as text so no value is coerced on read (`00_schema.sql`, `01_load.sql`).
2. Cast `frequency` to integer and `year` to integer; trim the category label (`02_transform.sql`).
3. Keep only rows that carry a count. Rows with an empty `frequency` are dropped.
4. Keep only the by-year rows (`year` set, `month` empty) and the by-month rows (`month` set, `year` empty). The by-sex slice is excluded.

## How a positive result is defined

Four category labels form a mutually exclusive, exhaustive split of each period's total driver deaths. This was verified against the snapshot: positive + not_detected + tox_unavailable equals total_deaths exactly, in every year and every month.

- **positive**: `One or more specified drug(s) detected`
- **not_detected**: `Specified drugs not detected`
- **tox_unavailable**: `Toxicology not available` (unknown or pending)
- **total_deaths**: `Total driver deaths`

The source also carries finer labels (various alcohol, THC, and cocaine or methamphetamine bands). Those overlap one another and are not summed. Only the split above is used.

## Analysis logic, step by step

All logic is in `sql/`, one file per step, each query commented with the question it answers.

1. **Per-year outcome counts** (`03_analysis.sql`, year slice): for each year, pivot the four labels into columns using conditional aggregation, giving total_deaths, positive, not_detected, and tox_unavailable.
2. **Percent positive per year**: positive divided by (positive + not_detected), times 100, rounded to one decimal and stored as `DECIMAL(5,1)`. Deaths with no result available are left out of the denominator, so a year with more pending cases does not read as a lower positive rate.
3. **Month seasonality**: the same four counts and the same percent, computed for each calendar month pooled across all years. A month-number column (1 to 12) carries calendar order.
4. **Combine and order** (`99_export.sql`): union the year rows and the month rows into one table, then write it with year rows first (2015 to 2024) followed by the twelve months in calendar order.

## Outputs

`out/toxicology_trend.csv` (checked against `expected/toxicology_trend.csv`). One row per year and one row per month. Columns are defined in `data_dictionary.md`. Twenty-two rows: ten years plus twelve months.

## Edge cases

- **Unknown or pending toxicology**: counted in its own column, `tox_unavailable`, and excluded from the percent-positive denominator rather than treated as a negative.
- **Missing dates or counts**: a row with an empty `frequency` is dropped in transform. Every by-year and by-month row in this snapshot carries both a period and a count, so none are dropped in practice.
- **Overlapping sub-labels**: the alcohol, THC, and cocaine or methamphetamine bands overlap and are deliberately not summed.

## Determinism

The snapshot is pinned and committed. Every published table is a fixed cross-tab, so the counts do not change between runs. The export query ends in an explicit `ORDER BY`, and `pct_positive` is cast to a fixed-scale decimal, so the output is byte-for-byte reproducible. `expected/toxicology_trend.csv` was built from a first verified run and confirmed by a second run printing PASS.
