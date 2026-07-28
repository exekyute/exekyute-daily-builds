# Data dictionary

Concentrations are carried as `DECIMAL(18,6)` in SQL and are always expressed in the unit the analyte's guideline is written in, never the unit the source row happened to use. Thresholds are `DECIMAL(12,3)`. Percentages are rounded to two decimals for display; the underlying division happens on exact decimals.

A **sample** in this build means one analyte result: one measurement of one analyte, at one station, on one visit. It does not mean one bottle of water, which typically yields 30 or more analyte results.

## out/water_compliance.csv (also expected/water_compliance.csv)

One sectioned result file, 108 rows plus header. Columns not meaningful for a section are blank.

| Column | Type | Meaning |
| --- | --- | --- |
| section | text | Which block the row belongs to: `summary`, `row_ledger`, `analyte_compliance`, `location_compliance`, `analyte_location`, or `worst_cells`. |
| rank | integer | Position within the section. `analyte_compliance`, `location_compliance`, and `worst_cells` rank by pass rate ascending, so rank 1 is the worst performer. `analyte_location` orders by station then analyte. `summary` and `row_ledger` use a fixed reading order. |
| measure | text | Label for `summary` and `row_ledger` rows (for example `evaluated_samples`, `class_wrong_fraction`). Blank elsewhere. |
| analyte | text | Analyte name as published (`characteristicname`). Filled for `analyte_compliance`, `analyte_location`, and `worst_cells`. |
| location_id | text | Monitoring station id (`monitoringlocationid`), for example `NS01DL0009`. Filled for `location_compliance`, `analyte_location`, and `worst_cells`. |
| location | text | Readable station name (`monitoringlocationwaterbody`), for example `Kelley River at Eight Mile Ford`. Filled wherever `location_id` is. |
| direction | text | `maximum` when the guideline is a ceiling, `minimum` when it is a floor. Filled for `analyte_compliance`. |
| threshold | decimal, 3 dp | The guideline value, in `guideline_unit`. Filled for `analyte_compliance`. |
| guideline_unit | text | The unit the guideline is written in, `mg/l` or `ug/l`. Every reading is converted into this unit before comparison. Filled for `analyte_compliance`. |
| n_samples | integer | Sample count for the row. In `summary` and `row_ledger` this column carries the row's single figure (a row count, an analyte count, or a station count) and the rest of the row is blank. |
| n_passing | integer | Samples meeting the guideline. |
| pass_pct | percent, 2 dp | `n_passing` as a percent of `n_samples`. |
| n_non_detect | integer | Evaluated samples flagged below the laboratory reporting limit. Against a maximum-direction guideline these count as passing. |
| nondetect_pct | percent, 2 dp | `n_non_detect` as a percent of `n_samples`. Filled in `summary`, `analyte_compliance`, and `location_compliance`. |
| n_censored_above | integer | Of the non-detects, how many were reported at a limit above their own guideline. These count as passes under the stated rule, but the pass cannot be confirmed from this data. |
| first_sample_date | date | Earliest evaluated sample date in the row's scope, `YYYY-MM-DD`. |
| last_sample_date | date | Latest evaluated sample date in the row's scope. |
| days_since_last_sample | integer | Days from `last_sample_date` to the pull date of 2026-07-25, which is a fixed constant in the SQL rather than today's date. Filled in `summary`, `analyte_compliance`, and `location_compliance`. |

### The `summary` section, row by row

| measure | What `n_samples` holds |
| --- | --- |
| evaluated_samples | Samples compared against a guideline. This row also fills the passing, pass rate, non-detect, unconfirmable, and date columns; it is the headline. |
| analytes_in_scope | Declared (analyte, fraction) guideline pairs. |
| monitoring_locations | Stations with at least one evaluated sample. |
| duplicate_rows_removed | Byte-identical duplicate records collapsed out of the snapshot. |
| quality_control_rows_excluded | Rows refused because their activity type is not on the allowlist. |
| non_detects_with_unknown_limit | Non-detects published without a usable reporting limit, so the unconfirmable test cannot be run on them. |

### The `row_ledger` section

Thirteen rows that account for every published record. Rows 1 to 3 are the snapshot count, the duplicate count, and the deduped count. Rows 4 to 11 are the eight mutually exclusive `class_` buckets from `sql/02_transform.sql`. Row 12 sums the eight classes and must equal `rows_after_dedup`; row 13 sums the deduped and duplicate counts and must equal `raw_rows_in_snapshot`.

## bi/exports/mart_water.csv (copy of out/mart_water.csv)

One row per deduped source record whose analyte is in scope, 3,052 rows. Out-of-scope analytes are not carried, because they have no guideline to report against; the ledger in the result file is where they are accounted for.

The key is (`location_id`, `analyte`, `sample_fraction`, `sample_date`, `sample_time`) and it is enforced as a primary key in SQL.

| Column | Type | Meaning |
| --- | --- | --- |
| sample_date | date | Date of the sampling visit, `YYYY-MM-DD`. |
| sample_time | text | Clock time of the visit, `HH:MM`, 24 hour. Part of the key: a station is occasionally sampled twice on one date. |
| sample_year | integer | Calendar year of `sample_date`. Use this for year arithmetic in DAX; the mart has no contiguous date column and no date table. |
| location_id | text | Monitoring station id. |
| location | text | Readable station name. |
| analyte | text | Analyte name as published. |
| sample_fraction | text | Published sample fraction, with blanks written as `(not stated)`. `Total` for the metals, `Dissolved` for chloride, `(not stated)` for dissolved oxygen. |
| result_unit | text | The unit the source row used, trimmed and lowercased. Kept so the conversion can be audited against `guideline_unit`. |
| result_value | decimal, 6 dp | The reading converted into `guideline_unit`. Blank when the row has no numeric value (a non-detect or a malformed row) or when no guideline applies to its fraction. |
| guideline_unit | text | The unit the guideline is written in. Blank when no guideline applies to the row's fraction. |
| guideline_threshold | decimal, 3 dp | The guideline value. Blank when no guideline applies. |
| guideline_direction | text | `maximum` or `minimum`. Blank when no guideline applies. |
| row_class | text | Why the row was or was not compared: `evaluated`, `wrong_fraction`, `quality_control`, `unaccepted_status`, `wrong_unit`, `malformed`, or `non_detect_minimum_direction`. Filter to `evaluated` for any rate. |
| is_evaluated | integer 0/1 | 1 when `row_class` is `evaluated`. The denominator flag. |
| is_pass | integer 0/1 | 1 when the row met its guideline, 0 when it breached. Blank for every row that was not evaluated, so a SUM ignores them. |
| is_non_detect | integer 0/1 | 1 when the source flagged the result below the laboratory reporting limit. |
| is_censored_above | integer 0/1 | 1 when the row is an evaluated non-detect whose reporting limit sits above its guideline, so its pass cannot be confirmed. 0 when the limit is at or below the guideline. Blank for measured values and for non-detects with no usable limit. |
