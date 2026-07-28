# Spec: water-quality guideline compliance

## Purpose

Take the province's surface water grab-sample results and answer a compliance question: how often does a measured analyte meet the national aquatic-life guideline written for it, broken down by analyte, by monitoring station, and by the two together. The build is deterministic and re-derivable from the committed snapshot, and it is written so that a reader can audit every threshold and every exclusion without reading the SQL line by line.

The second purpose is bookkeeping. Water-quality data is easy to get wrong in ways that still produce a clean-looking percentage, so this build refuses to report a rate without also reporting what went into it: how many rows were duplicates, how many were the wrong sample fraction, how many were non-detects, and how many of the passes cannot actually be confirmed.

## Inputs

One file: `data/raw/ns_surface-water-grab_2026-07-25.csv`, a pinned snapshot of Socrata dataset `wncu-ppda` (see SOURCE.md). 38,143 rows, 26 columns, one row per analyte result. All rows are `River/Stream` locations sampled in `Surface Water` at a depth of -0.3 m, across 8 monitoring stations, 2002-06-12 to 2024-12-16.

## Named constants

Every threshold, bound, and accepted-value list is declared in `sql/00_schema.sql` as a `const_` table. No comparison anywhere in the pipeline reads a literal number or a literal unit string.

### PULL_DATE

`DATE '2026-07-25'`, the date the snapshot was taken. Every elapsed-time figure (the `days_since_last_sample` columns) is measured against this literal, never against `CURRENT_DATE`. Running the build tomorrow moves nothing in the golden file.

### ACCEPTED_ACTIVITY_TYPE

`('Sample-Routine', 'Field Msr/Obs-Portable Data Logger')`

A positive allowlist of WQX activity types that represent a real environmental measurement. `Sample-Routine` is the grab sample sent to the laboratory; `Field Msr/Obs-Portable Data Logger` is the calibrated sonde reading taken on the same visit. The list is an allowlist rather than a blocklist so that the WQX quality-control types are refused by default: `Quality Control Sample-Field Blank` and `Quality Control Sample-Trip Blank` read near zero and would drag a pass rate up, while `Quality Control Sample-Field Replicate` and `Quality Control Sample-Lab Duplicate` repeat one sample and would count it twice.

This snapshot carries none of those four, so the filter excludes 0 rows today. That 0 is a line in the output, not an assumption, and because the list is an allowlist a later pull that does carry them needs no SQL change.

### ACCEPTED_RESULT_STATUS

`('Preliminary')`

The network publishes every result it has released under the single status `Preliminary`; there is no second status in the snapshot to choose between. A row whose status is blank has not been released under a status this pipeline recognises, so it is excluded and counted, not assumed good. One row meets that description.

### UNIT_CONVERSION

| from_unit | to_unit | factor |
| --- | --- | --- |
| mg/l | mg/l | 1 |
| ug/l | ug/l | 1 |
| ug/l | mg/l | 0.001 |
| mg/l | ug/l | 1000 |

This table is the reason the build is trustworthy at all. The same analyte is published in more than one unit, and a milligram-per-litre threshold compared against a microgram-per-litre reading is wrong by a factor of 1000 while still producing a tidy percentage that passes a golden diff. No comparison happens until the row's reading has been converted into the unit its guideline is written in, using a factor from this table.

Boron is what makes that concrete. It is declared at 1.5 mg/L, the unit CCME publishes it in, while the dataset reports boron in ug/L at readings from 5 to 50. Converted, those are 0.005 to 0.050 mg/L and every one passes. Compared raw against 1.5, almost every boron result would "fail" and the analyte would look like the worst problem in the province.

A row whose unit has no entry in this table is excluded as `wrong_unit` and counted. It is never compared and never silently dropped. Unit text is trimmed and lowercased first, which is the whole normalization needed: the snapshot writes the same unit as both `mg/L` and `mg/l`, and as both `ug/l` and `ug/L`.

### ANALYTE_GUIDELINE

One row per (analyte, sample fraction) pair in scope. Every threshold is a Canadian Council of Ministers of the Environment (CCME) Canadian Water Quality Guideline for the Protection of Aquatic Life, freshwater, published in the Canadian Environmental Quality Guidelines summary table (https://ccme.ca/en/summary-table).

| Analyte | Fraction | Guideline unit | Threshold | Direction | CCME basis |
| --- | --- | --- | --- | --- | --- |
| Arsenic | Total | ug/l | 5.0 | maximum | long-term exposure |
| Boron | Total | mg/l | 1.5 | maximum | long-term exposure |
| Chloride | Dissolved | mg/l | 120 | maximum | long-term exposure |
| Dissolved oxygen (DO) | (not stated) | mg/l | 6.5 | minimum | cold-water biota, other than early life stages |
| Iron | Total | ug/l | 300 | maximum | freshwater guideline |
| Molybdenum | Total | ug/l | 73 | maximum | long-term exposure |
| Selenium | Total | ug/l | 1 | maximum | long-term exposure |
| Silver | Total | ug/l | 0.25 | maximum | interim guideline |
| Thallium | Total | ug/l | 0.8 | maximum | interim guideline |
| Uranium | Total | ug/l | 15 | maximum | long-term exposure |

The dissolved oxygen value is the cold-water figure, which is the right one for these eight rivers: they are Atlantic salmon and brook trout waters, and the network samples them year round.

**Sample fraction is part of the key on purpose.** The metals guidelines are written for the total fraction, and this dataset also publishes a dissolved fraction for the same analyte from the same visit. Counting both would measure one sample twice against a guideline that applies to only one of them, so the dissolved rows are excluded and counted (544 of them).

**Analytes deliberately left out of scope.** Only guidelines that are a single fixed number are declared. Cadmium, copper, lead, nickel, and zinc have hardness-dependent guidelines; aluminium's guideline depends on pH; ammonia's depends on pH and temperature; turbidity and total suspended solids are written as a permitted change from background rather than an absolute value. None of those covariates arrive on the same row as the result here, so applying a single number to them would produce a confident answer to the wrong question. pH itself is left out because its guideline is a range with both a floor and a ceiling, and this build's direction model is deliberately one-sided.

### ROW_CLASS_ORDER

The eight buckets a row can land in, declared in `sql/03_analysis.sql` so the ledger prints every class including the ones that caught nothing: `analyte_not_in_scope`, `wrong_fraction`, `quality_control`, `unaccepted_status`, `wrong_unit`, `malformed`, `non_detect_minimum_direction`, `evaluated`.

## Cleaning and validation rules (02_transform.sql)

### 1. Exact duplicate records

The published extract repeats records. 18,274 of the 38,143 rows are byte-identical copies of another row across all 26 columns, down to the laboratory sample id, so they are one lab result published more than once, not two measurements. 18,192 rows appear exactly twice and 41 appear three times. Left in place they inflate every sample count and re-weight every pass rate toward whichever results happen to be repeated.

`SELECT DISTINCT *` collapses them, leaving 19,869 distinct rows. Both counts survive into the ledger in the output, so a reader can watch the collapse happen. This is the double-counting hazard that WQX replicate flags are meant to catch, arriving instead as plain duplication in the extract.

### 2. Typing and normalization

- Unit text is trimmed and lowercased. Matching the raw string would strand `mg/L` and `ug/L` in the `wrong_unit` bucket while their lowercase twins passed.
- A blank or missing sample fraction becomes the literal label `(not stated)`, so it joins and groups like any other fraction instead of vanishing on a NULL comparison. Dissolved oxygen's declared fraction is that label.
- Result status gets the same `(not stated)` treatment, so a row with no status is refused by the allowlist instead of slipping past the test.
- Values and detection limits use `TRY_CAST` to `DECIMAL(18,6)`. A value that will not cast becomes NULL and is classified as `malformed`, where it is counted; it never reaches a comparison. No value in this snapshot fails to cast.
- The published timestamp is `YYYY-MM-DDTHH:MM:SS.mmm`. The date part is cast to DATE and the clock time is kept separately, because a station can be sampled twice on one date and the two visits have to stay distinguishable.

### 3. Location display name

`monitoringlocationwaterbody` is the readable river-and-place name and is already one value per location id in this snapshot. The pipeline does not lean on that: it picks the most frequent spelling per id and breaks ties alphabetically, so a later pull that introduces a second spelling still produces one deterministic label instead of splitting the station in two.

`monitoringlocationname` is not used for this. It is an equipment log code such as `SHE-HYDROLABREMOVED-0M` and changes 21 times across the 8 stations.

### 4. Row classification

Every row leaves 02_transform.sql carrying exactly one `row_class`. The cases are mutually exclusive and evaluated top to bottom, so the counts add back up to the deduped row total. Scope comes first and defects second, so the defect counts describe the analytes actually being measured rather than the whole catalogue.

| Order | Class | Meaning | Rows |
| --- | --- | --- | --- |
| 1 | analyte_not_in_scope | no fixed CCME guideline declared for this analyte | 16,817 |
| 2 | wrong_fraction | analyte in scope, but not the fraction its guideline is written for | 553 |
| 3 | quality_control | activitytype is not on the allowlist | 0 |
| 4 | unaccepted_status | resultstatusid is not on the allowlist | 1 |
| 5 | wrong_unit | the row's unit has no conversion into the guideline's unit | 0 |
| 6 | malformed | not a non-detect, and no value that casts to a number | 2 |
| 7 | non_detect_minimum_direction | a non-detect against a minimum-direction guideline | 0 |
| 8 | evaluated | compared against the guideline | 2,496 |

Those eight sum to 19,869, and 19,869 plus the 18,274 duplicates equals the 38,143 published rows. Both sums appear in the output as `check_` lines, so "no row was silently dropped" is a figure in the file, not a claim in the README.

### 5. The pass rule, both directions

**Maximum direction.** The guideline is a ceiling. A reading at or below the threshold passes; above it fails. A non-detect passes, because the true concentration is below the reporting limit and a ceiling can only be breached from above.

**Minimum direction.** The guideline is a floor. A reading at or above the threshold passes; below it fails. A non-detect against a floor is neither a pass nor a fail: "below the reporting limit" cannot be read as meeting a minimum, so the row is classified `non_detect_minimum_direction`, reported on its own line, and kept out of the pass-rate denominator entirely.

The boundary is inclusive in both directions because CCME writes these guidelines as values that should not be exceeded and levels that should not fall below, so sitting exactly on the number is not a breach.

Dissolved oxygen is the only minimum-direction analyte declared, and it is a sonde reading rather than a laboratory analysis, so it produces no non-detects at all: the `non_detect_minimum_direction` count is 0. The rule is still implemented, because a later snapshot or a later analyte could produce one.

### 6. The detection-limit diagnostic

Counting a non-detect as a pass is only honest when the laboratory could have seen a breach in the first place. If the reporting limit sits above the guideline, "not detected" says nothing about whether the guideline was met, and a pass rate built from those rows is not evidence of compliance.

`is_censored_above` marks exactly those rows:

- **1**: an evaluated non-detect whose converted reporting limit is above its guideline. Counted as a pass by the rule above, but the pass cannot be confirmed from this data.
- **0**: an evaluated non-detect whose reporting limit is at or below its guideline. The pass is real.
- **NULL**: not applicable (a measured value), or not answerable (a non-detect published without a usable reporting limit, counted separately as `non_detects_with_unknown_limit`, which is 0 here).

621 of the 2,401 passes are marked unconfirmable, and they are concentrated: selenium is reported at a limit of 2 ug/L against a 1 ug/L guideline (383 of its 384 results), silver at 2 ug/L against 0.25 (119 of 120), thallium at 2 ug/L against 0.8 (119 of 120). Those three analytes read 100 percent compliant and that number carries almost no information. Their own rows in the output say so.

## Analysis steps (03_analysis.sql)

1. `class_counts`: every declared class joined to its observed count, so the zero-count classes survive into the ledger.
2. `evaluated_results`: the rows classified `evaluated`. Every pass rate is built from this table and nothing else.
3. `overall_totals`: network-wide sample count, passing count, pass rate, non-detect count and share, unconfirmable count, first and last sample date, and days since the last sample measured against PULL_DATE.
4. `analyte_compliance`: the same figures per analyte, driven off the guideline constants with a LEFT JOIN so an analyte with no evaluated sample still gets a row. Ranked worst pass rate first, ties broken on analyte.
5. `location_compliance`: the same figures per monitoring station, ranked worst pass rate first, ties broken on location id. Rank 1 is the worst-performing station.
6. `analyte_location`: the full analyte-by-station matrix, one cell per pair with at least one evaluated sample (65 cells). This is the grid the Power BI matrix mirrors.
7. `worst_cells`: every cell in that matrix that breached at least once, worst first, capped at 15. The `pass_pct < 100` filter is what keeps the section meaningful; padding out to a fixed 15 rows would fill most of the list with cells that never failed and label them worst. Six cells qualify.
8. `water_compliance`: the six sections stacked into one table with a fixed sort key: `summary`, `row_ledger`, `analyte_compliance`, `location_compliance`, `analyte_location`, `worst_cells`.
9. `mart_water`: every deduped row whose analyte is in scope (3,052 rows), carrying the class that decided its fate and the flags already computed. Its primary key is the real sample key of station, analyte, fraction, date, and time, so a later snapshot that publishes two different results for one visit fails the insert loudly instead of quietly counting the visit twice.

## Outputs

- `out/water_compliance.csv`: the sectioned compliance result, 108 rows plus header, diffed against `expected/water_compliance.csv`.
- `out/mart_water.csv`, copied to `bi/exports/mart_water.csv`: the row-level BI mart, 3,052 rows.

## Edge cases

- **The two malformed rows** are dissolved oxygen readings from 2020-09-10 at Salmon River at Murray and East River at Plymouth Park Road, published with no value and no non-detect flag. There is nothing to compare, so they are excluded and counted. Read as zeroes against a minimum-direction guideline, they would have registered as two false failures.
- **The one unaccepted-status row** is a chloride result of 3.6 mg/L from 2023-08-03 at Shelburne River, published with a blank status. In the raw file it appears twice; the duplicate collapse takes it to one row, and the status allowlist then excludes that row.
- **Analytes with a short record.** Arsenic, molybdenum, silver, thallium, and uranium only enter the sampling programme in 2019, so their 120 results each cover 2019 to 2024, while boron, chloride, iron, and selenium reach back to 2003 and dissolved oxygen to 2002. Per-analyte first and last sample dates are in the output so a rate is never read as covering more years than it does.
- **Stations that stopped reporting.** LaHave River, St. Mary's River, and North East Margaree River have no results after 2018, which the `days_since_last_sample` column shows as roughly 2,780 days. Their pass rates describe a closed record, not current conditions.
- **`South West Magaree River near Upper Margaree`** is spelled that way in the source, with the misspelling of Margaree in the river name. Published values are carried through as published, not corrected, because a silent correction here would mean the location label in this build stops matching the label in the portal.
- **Ties in every ranking** break on analyte, on location id, or on the pair, all of which are unique, so rank order never depends on scan order.

## Determinism

Comparisons run on `DECIMAL` values converted into the guideline's own unit; percentages are display values rounded to two decimals after the exact division. Every result query ends in a total order, meaning the sort finishes on a column that is unique within its section (analyte, location id, or both together), so no two rows can tie into an undefined order. That keeps the file byte-stable regardless of DuckDB version or thread count. All elapsed-time arithmetic uses the PULL_DATE constant, so the golden does not drift with the calendar.

The `row_ledger` section makes the accounting visible inside the golden file itself: eight class counts that sum to the deduped row count, and a deduped count plus a duplicate count that sum to the published row count.
