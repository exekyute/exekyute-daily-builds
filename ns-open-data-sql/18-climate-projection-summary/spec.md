# Spec: climate-projection summary model

## Purpose

Summarize Nova Scotia's CMIP5 climate projections as scenario deltas: for each county, how much the projected annual mean temperature departs from its 1981-2010 baseline under RCP4.5 and RCP8.5 at the 2045 and 2095 horizons, inside a formula-driven Excel workbook. The workbook holds no pasted results: every key figure is a live formula over the Data sheet, and `build.py` proves each one by recomputing it in plain Python and diffing against a golden file.

## Inputs

One pinned snapshot in `data/raw/`, pulled from the Socrata resource endpoint for dataset `r7d9-j7wx` (NS Climate Change Projections CMIP5). The snapshot is wide: one row per (region, variable), with 24 value columns named `rcp{45,85}_p{05,50,95}_{2010,2045,2065,2095}`.

The model uses:

| Slice | Choice |
| --- | --- |
| Variable | `tgmean_annual`, Average Daily Mean Temperature, annual, degrees C |
| Percentile | p50, the median of the model range (p05 and p95 are ignored) |
| Scenarios | RCP4.5 (low emissions) and RCP8.5 (high emissions) |
| Periods | `2010` = the 1981-2010 baseline, `2045` = 2015-2045, `2095` = 2065-2095; the 2065 columns are not used |
| Regions | The 18 counties; the province-wide `Nova Scotia` row is dropped so the ranking compares counties with counties |

## Cleaning rules

Applied by `prepare_rows()` before anything else sees the data:

1. Keep only rows whose `variable` is `tgmean_annual`.
2. Drop the `Nova Scotia` (province-wide) row and any row with a blank region.
3. Unpivot the six p50 columns the model uses into canonical long rows `(region, scenario, period, value)`, with scenario `RCP4.5` or `RCP8.5` and period `2010`, `2045`, or `2095`. A cell that fails to parse as a number is skipped, which leaves that slot empty rather than wrong.
4. Sort by region, scenario, period for a stable Data sheet.

The pinned snapshot yields 108 canonical rows: 18 counties, two scenarios, three periods, no losses.

## Delta logic, step by step

All formulas live on the Model sheet and reference the Data sheet.

1. **Slot means.** For each county, six cells (columns B to G): the RCP4.5 and RCP8.5 baselines and the four scenario-horizon values, each `=ROUND(AVERAGEIFS(Data!$D:$D, criteria...),2)` with the criteria pinning region, scenario, and period. Each cell is wrapped as `=IF(COUNTIFS(criteria...)=0,"n/a", ROUND(AVERAGEIFS(...),2))` so an empty slot shows `n/a` instead of an error. With one snapshot row per slot the mean is just that value, but the formulas stay correct if a future snapshot carries several.
2. **Deltas.** Four columns per county (H to K): each projection minus the SAME scenario's baseline, `=ROUND(<proj>-<baseline>,2)`, guarded with `ISTEXT` so a missing slot propagates `n/a` rather than a wrong number. RCP4.5 deltas subtract column B; RCP8.5 deltas subtract column C.
3. **Sort key.** Column L holds a tie-safe integer per county: `=ROUND($K<r>*100,0)*1000+(<last pivot row>-ROW())`, the 2095 RCP8.5 delta in hundredths shifted three digits plus the reverse row position. Equal deltas therefore rank the alphabetically earlier county first, and every county gets exactly one rank.
4. **Ranking.** The ranked block orders counties by 2095 RCP8.5 delta. The k-th region is `=INDEX(<regions>,MATCH(LARGE(<keys>,k),<keys>,0))` and its delta is the matching `INDEX` into column K.
5. **Headline.** The largest-delta county and value reference the ranked block's first row. Scenario averages are `=ROUND(AVERAGE(<delta column>),2)`; `AVERAGE` ignores `n/a` text cells, and the Python mirror excludes missing deltas the same way. The scenario gap is the RCP8.5 average minus the RCP4.5 average.

The Python verification recomputes the same figures with plain arithmetic (`sum / len`, subtraction, the same integer sort key) and rounds with `decimal.Decimal` and `ROUND_HALF_UP`, which rounds halves away from zero exactly as Excel's `ROUND` does. Python's built-in `round()` is never used on reported figures because it rounds halves to even. Deltas subtract already-rounded slot means, exactly as the Model sheet's delta cells subtract already-rounded `AVERAGEIFS` cells, so a delta can differ from the raw difference by a hundredth of a degree; the workbook and the golden file still agree because they share the rule.

## Cell map of key figures

With 18 counties the pivot occupies rows 4 to 21, alphabetical by county.

| Key figure | Cell(s) |
|---|---|
| `baseline_rcp45_<county>` | B4:B21 |
| `baseline_rcp85_<county>` | C4:C21 |
| `rcp45_2045_<county>` | D4:D21 |
| `rcp85_2045_<county>` | E4:E21 |
| `rcp45_2095_<county>` | F4:F21 |
| `rcp85_2095_<county>` | G4:G21 |
| `delta_rcp45_2045_<county>` | H4:H21 |
| `delta_rcp85_2045_<county>` | I4:I21 |
| `delta_rcp45_2095_<county>` | J4:J21 |
| `delta_rcp85_2095_<county>` | K4:K21 |
| `rank_2095_rcp85_<county>` | A25:A42 (rank), with the county in B25:B42 and its delta in C25:C42 |
| `top_region_2095_rcp85` | B45 |
| `top_delta_2095_rcp85` | B46 |
| `avg_delta_rcp45_2095` | B47 |
| `avg_delta_rcp85_2095` | B48 |
| `scenario_gap_2095` | B49 |

Column L (rows 4 to 21) is the sort key described above; it feeds the ranked block and is not itself a key figure.

## Edge cases

- **A county missing a horizon.** Its `AVERAGEIFS` cell shows `n/a` (the `COUNTIFS` guard), its deltas show `n/a` (the `ISTEXT` guard), its sort key shows `n/a`, and `LARGE` and `AVERAGE` skip text cells. The county drops out of the ranked block and the golden file records `n/a` for those figures. No county in the pinned snapshot triggers this, but the guards are in the formulas either way.
- **A county missing a baseline.** Same handling: that scenario's deltas are `n/a` because there is nothing to subtract.
- **Tied deltas.** Three counties tie at a 4.66 delta in the pinned snapshot (Colchester, Pictou, Victoria). The sort key breaks the tie by pivot order, so they take ranks 3, 4, and 5 alphabetically, each exactly once, in the workbook and in the golden file alike.

## Determinism

The build is deterministic end to end: a pinned snapshot read from disk, a fixed sort into the Data sheet, closed-form arithmetic, half-away-from-zero rounding at defined points, and an integer sort key with no floating-point comparison ambiguity. Running `python build.py` twice produces the same workbook and the same PASS. A recalculation of the generated workbook in Excel reproduces the golden figures cell for cell (checked for the headline block, the Halifax pivot row, and the tied ranks).
