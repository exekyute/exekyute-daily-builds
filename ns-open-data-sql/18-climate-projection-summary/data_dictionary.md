# Data dictionary

## expected/key_figures.csv

One row per key figure. Two columns.

| Column | Type | Meaning |
|---|---|---|
| `figure` | text | Key-figure name. County-level figures carry the county as a lower-case hyphenated suffix, for example `delta_rcp85_2095_cape-breton`. |
| `value` | text | The figure's value, written exactly as the verification compares it. Temperatures and deltas carry two decimals; ranks are whole numbers; the top region is a text label. A slot with no source rows is `n/a`. |

### Figure names

All temperatures are annual mean temperature at the CMIP5 model-range median (p50), in degrees C. Deltas subtract the same scenario's 1981-2010 baseline.

| Figure | Type | Meaning | Units |
|---|---|---|---|
| `baseline_rcp45_<county>` | number | RCP4.5 value for the 1981-2010 baseline period, rounded to two decimals | degrees C |
| `baseline_rcp85_<county>` | number | RCP8.5 value for the 1981-2010 baseline period | degrees C |
| `rcp45_2045_<county>` | number | RCP4.5 value at the 2045 horizon (2015-2045) | degrees C |
| `rcp85_2045_<county>` | number | RCP8.5 value at the 2045 horizon | degrees C |
| `rcp45_2095_<county>` | number | RCP4.5 value at the 2095 horizon (2065-2095) | degrees C |
| `rcp85_2095_<county>` | number | RCP8.5 value at the 2095 horizon | degrees C |
| `delta_rcp45_2045_<county>` | number | RCP4.5 2045 value minus the RCP4.5 baseline, rounded to two decimals | degrees C |
| `delta_rcp85_2045_<county>` | number | RCP8.5 2045 value minus the RCP8.5 baseline | degrees C |
| `delta_rcp45_2095_<county>` | number | RCP4.5 2095 value minus the RCP4.5 baseline | degrees C |
| `delta_rcp85_2095_<county>` | number | RCP8.5 2095 value minus the RCP8.5 baseline | degrees C |
| `rank_2095_rcp85_<county>` | integer | The county's rank by 2095 RCP8.5 delta, 1 = largest; ties break alphabetically | rank |
| `top_region_2095_rcp85` | text | County with the largest 2095 RCP8.5 delta | none |
| `top_delta_2095_rcp85` | number | That county's 2095 RCP8.5 delta | degrees C |
| `avg_delta_rcp45_2095` | number | Average of the 18 county RCP4.5 2095 deltas, unweighted | degrees C |
| `avg_delta_rcp85_2095` | number | Average of the 18 county RCP8.5 2095 deltas, unweighted | degrees C |
| `scenario_gap_2095` | number | Average RCP8.5 2095 delta minus average RCP4.5 2095 delta | degrees C |

## Data sheet (workbook)

Canonical long rows prepared from the snapshot: 108 rows, one per (county, scenario, period) slot the model uses, sorted by county, scenario, period. Values only, no formulas.

| Column | Type | Meaning | Units |
|---|---|---|---|
| `region` | text | County name as published (the province-wide `Nova Scotia` row is excluded) | none |
| `scenario` | text | `RCP4.5` or `RCP8.5` | none |
| `period` | text | `2010` (the 1981-2010 baseline), `2045`, or `2095` | none |
| `value_degc` | number | Annual mean temperature at the model-range median (p50) for that slot | degrees C |

## Model sheet (workbook)

Every figure below is a live formula; nothing is pasted.

| Block | Contents |
|---|---|
| Pivot table (rows 4 to 21, one row per county) | The two per-scenario baselines and the four scenario-horizon values as `AVERAGEIFS` over the Data sheet, each wrapped in a `COUNTIFS` guard that shows `n/a` when a slot has no rows; four delta columns subtracting the same scenario's baseline, guarded with `ISTEXT`; a tie-safe integer sort key in column L (the 2095 RCP8.5 delta in hundredths, shifted three digits, plus the reverse row position) |
| Ranked block (rows 25 to 42) | Counties ranked by 2095 RCP8.5 delta with `LARGE` over the sort keys and `INDEX`/`MATCH` back to the county and its delta, so ties resolve alphabetically and each county appears exactly once |
| Headline (rows 45 to 49) | Largest-delta county and value (references into the ranked block's first row), average 2095 delta per scenario as `AVERAGE` over the delta columns, and the scenario gap as their difference |
