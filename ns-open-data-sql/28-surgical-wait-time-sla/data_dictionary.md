# Data dictionary

Two files are defined here: the golden output `expected/wait_time_sla.csv`, and
the BI mart `bi/exports/mart_wait_times.csv`.

All day figures are whole days, as published by the source. All rates are
percentages rounded to two decimals. A blank cell means the column does not
apply to that section or that the source published no value.

## Golden output: `wait_time_sla.csv`

193 rows in eight sections. Column meaning is fixed across sections; the notes
say which sections use which columns.

| Column | Type | Definition |
| --- | --- | --- |
| `section` | text | Which of the eight sections the row belongs to. Sections appear in fixed order: `constants`, `coverage`, `exclusions`, `breach_summary`, `worst_facilities`, `worst_procedures`, `worst_lines`, `provincial_trend`. |
| `rank` | integer | Position within the section, starting at 1. In the ranked sections it is the rank itself; elsewhere it is the fixed display order. Unique within a section. |
| `measure` | text | Name of the figure, for the scalar sections (`constants`, `coverage`, `exclusions`, `breach_summary`). Blank in the sections whose rows are named by facility, procedure, or period instead. |
| `zone` | text | Health zone. `Zone 1` to `Zone 4`, or `IWK`. `Total` on the `provincial_trend` rows, which are the source's own rollup. Blank where the row is not zone-specific. |
| `facility` | text | Facility name. In `worst_facilities` and `worst_lines` it names the row. In `worst_procedures` it names the facility of that procedure's worst line. `Provincial` on `provincial_trend`. |
| `procedure` | text | Procedure label, spaces collapsed. In `worst_procedures` and `worst_lines` it names the row. In `worst_facilities` and `provincial_trend` it names the procedure of that group's worst line. |
| `period` | text | Quarterly reporting period, `YYYY_qN`, `2023_q2` through `2025_q2`. In `worst_lines` and `provincial_trend` it names the row. In the two grouped sections it is the period of that group's worst line. |
| `year_quarter_index` | integer | `year * 4 + quarter` for the period on that row. 8094 through 8102. The previous quarter is always this value minus one. |
| `value` | integer | The section's scalar figure: in `constants` the constant itself; in `coverage` and `exclusions` a row count; in `breach_summary` either the target in days or a tail-gap statistic in days; in `worst_facilities`, `worst_procedures` and `provincial_trend` the total published lines in the group, measured or not. Blank in `worst_lines`. |
| `surgery_rows` | integer | Lines in the group carrying a published `surgery_median`. 1 on a `worst_lines` row, which is a single measured line. |
| `surgery_breaches` | integer | Lines in the group whose `surgery_median` exceeds `surgery_target_days`. 0 or 1 on a `worst_lines` row. |
| `surgery_breach_pct` | decimal | `surgery_breaches / surgery_rows` as a percentage. Blank where the group has no measured surgery line. |
| `consult_rows` | integer | Lines in the group carrying a published `consult_median`. |
| `consult_breaches` | integer | Lines in the group whose `consult_median` exceeds `consult_target_days`. |
| `consult_breach_pct` | decimal | `consult_breaches / consult_rows` as a percentage. |
| `qoq_surgery_breach_pct` | decimal | `provincial_trend` only. This quarter's `surgery_breach_pct` minus the previous quarter's, in percentage points, stepped over `year_quarter_index`. Blank on the first quarter in the window. |
| `meets_min_rows` | integer | `worst_facilities` and `worst_procedures` only. 1 when the group has at least `min_measured_rows` measured surgery lines, 0 when it has fewer. Rows flagged 0 are still reported; they sort to the bottom of their section. |
| `surgery_median` | integer | Days. Published median wait from booking to surgery on one line. In `worst_lines` that line is the row itself; in the grouped sections it is the group's longest measured line, named by the facility, procedure, and period columns on the same row. |
| `surgery_90th` | integer | Days. Published 90th-percentile wait to surgery on that same line. |
| `surgery_tail_gap` | integer | Days. `surgery_90th - surgery_median` on that same line. How much longer the slowest tenth waited than the middle patient. Blank when either side is absent. |
| `consult_median` | integer | Days. Published median wait to specialist consultation on that same line. |
| `consult_90th` | integer | Days. Published 90th-percentile wait to consultation on that same line. |
| `consult_tail_gap` | integer | Days. `consult_90th - consult_median` on that same line. Blank when either side is absent. |

### Section contents

| Section | Rows | What each row is |
| --- | --- | --- |
| `constants` | 4 | One named constant declared in `sql/00_schema.sql`: `surgery_target_days` 182, `consult_target_days` 90, `min_measured_rows` 9, `worst_lines_shown` 25. |
| `coverage` | 9 | What the analysis grain contains: snapshot rows, quarterly rows, facility lines kept, distinct zones, facilities, procedures and quarters, and the first and last period. |
| `exclusions` | 13 | Every row class held out with its count, the reconciliation gap and rollup-marker check (both must read 0), the lines missing each median, the blank specialty and provider counts, and the facilities and procedures below the minimum. |
| `breach_summary` | 6 | The two headline breach rates against their own targets, then the median and maximum tail gap for each measure pair. |
| `worst_facilities` | 16 | One facility, ranked by surgery breach rate with the below-minimum facility last. |
| `worst_procedures` | 111 | One procedure, ranked the same way. |
| `worst_lines` | 25 | One facility-procedure-quarter line, the longest published surgery medians in the snapshot. |
| `provincial_trend` | 9 | One quarter of the source's own provincial rollup series, with the quarter-over-quarter change in breach rate. |

## BI mart: `mart_wait_times.csv`

2,853 rows, one per published facility-procedure-quarter line. Provincial rollup
rows and rolling-window rows are not in this file at all, so no BI aggregate can
double count them. `(facility, procedure, period)` is unique.

| Column | Type | Definition |
| --- | --- | --- |
| `period` | text | Quarterly reporting period, `YYYY_qN`. |
| `year` | integer | Calendar year of the period. |
| `quarter` | integer | Quarter number, 1 to 4. |
| `year_quarter_index` | integer | `year * 4 + quarter`. 8094 through 8102. Sortable, one step per quarter, previous quarter at index minus one. This is the column the Power BI prior-quarter measure indexes on. |
| `zone` | text | Health zone: `Zone 1` to `Zone 4`, or `IWK`. Never `Total`. The slicer field in both BI faces. |
| `facility` | text | Facility name. 16 values. Never `Provincial`. |
| `procedure` | text | Procedure label, spaces collapsed. 111 values. |
| `consult_median` | integer | Days. Published median wait to specialist consultation. Blank where the source published none. |
| `consult_90th` | integer | Days. Published 90th-percentile wait to consultation. |
| `consult_tail_gap` | integer | Days. `consult_90th - consult_median`. Blank when either side is absent. |
| `surgery_median` | integer | Days. Published median wait to surgery. Blank where the source published none. |
| `surgery_90th` | integer | Days. Published 90th-percentile wait to surgery. |
| `surgery_tail_gap` | integer | Days. `surgery_90th - surgery_median`. Blank when either side is absent. |
| `surgery_target_days` | integer | 182 on every row. Carried so neither BI face hardcodes the threshold. |
| `consult_target_days` | integer | 90 on every row. Same reason. |
| `surgery_measured` | integer | 1 when the source published a `surgery_median` on this line, 0 when it did not. Sum it to get the denominator of any surgery breach rate. |
| `surgery_breach` | integer | 1 when `surgery_median` exceeds `surgery_target_days`, otherwise 0. Always 0 when `surgery_measured` is 0, so a line with no published median never counts as a breach and never counts as a pass. |
| `consult_measured` | integer | 1 when the source published a `consult_median` on this line, 0 when it did not. |
| `consult_breach` | integer | 1 when `consult_median` exceeds `consult_target_days`, otherwise 0. Always 0 when `consult_measured` is 0. |
