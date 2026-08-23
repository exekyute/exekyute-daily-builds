# Spec: long-term care bed supply

## Purpose

Turn the province's list of licensed long-term care and residential care facilities into a bed-supply picture: how many beds exist, what kind they are, where they sit, and how unevenly they are spread across facilities and zones. Every figure is deterministic and re-derivable from the committed snapshot.

## Inputs

One file: `data/raw/ns_ltc-facilities_2026-07-25.csv`, a pinned snapshot of Socrata dataset `x76a-axw2` (see SOURCE.md). 145 rows, one per facility, with four separate bed-count columns, a facility type, a health management zone, and a coordinate pair.

## The bed definition

There are four bed columns in the source, so the headline depends entirely on which ones go into it. This build uses:

```
total_beds = nursing_homes_nh_no_of_beds
           + residential_care_facilities_rcf_no_of_beds
```

`nursing_homes_nh_no_of_respite_beds` and `rcf_respite_beds` are reported as their own bed types, in their own columns and their own rows of the long mart, and are **excluded** from `total_beds`.

The reason is that the two respite columns count short-stay capacity, beds held for temporary admissions rather than standing places in the facility. Folding them into the headline would overstate permanent bed supply by 43 beds. They are not dropped: they are counted, exported, printed by `python run.py show`, and shown on the dashboard, just never inside the total. The definition is carried in code by `bed_type_dim.is_core_bed` in `sql/00_schema.sql`, which is the single place the two core bed types are named.

## Constants and bounds

Every bound is named in `sql/00_schema.sql` and read from there; nothing downstream hard-codes one.

| Constant | Value | What it controls |
| --- | --- | --- |
| `params.top_facility_limit` | 25 | rows in the `top_facilities` section |
| `params.round_dp` | 2 | decimals on every share, average, and median |
| `params.sea_yes_flag` | `Y` | the value that counts as single entry access participation |
| `params.snapshot_row_count` | 145 | committed snapshot size, checked in `row_accounting` |
| `bed_type_dim` | 4 rows | the bed type names, their source columns, and `is_core_bed` |
| `zone_dim` | 4 rows | the accepted zone names |

`params.round_dp` is 2 and the CSV columns are stored as `DECIMAL(12,2)` and `DECIMAL(7,2)`; those scales are the same number by construction, so a share written as `35.77` is the rounded value and not a truncation of something wider.

## Median and rounding

Averages are `AVG(total_beds)` and medians are `MEDIAN(total_beds)`. DuckDB's `MEDIAN` is the continuous median, identical to `QUANTILE_CONT(x, 0.5)`: with an odd facility count it returns the middle value, and with an even count it interpolates, which for the 0.5 quantile means the average of the two middle values. Northern zone has 32 facilities, so its median is interpolated; the other three zones and the provincial figure have odd counts. Both statistics are then rounded to `params.round_dp` decimals and cast to `DECIMAL(12,2)`, which is why a median can read `36.00` or, on a different snapshot, `36.50`.

The dashboard reimplements the same continuous median in JavaScript (`medianCont` in `dashboard/dashboard.js`) so its zone medians match the SQL to the cent rather than approximating with a discrete midpoint.

## Coordinate traps

Three columns in the source describe location, and two of them are traps.

1. **`x_coordinate` is longitude and `y_coordinate` is latitude**, the reverse of the reading most people give those names. The snapshot bears it out: `x_coordinate` runs -66.17 to -59.94 and `y_coordinate` runs 43.55 to 46.81, which is Nova Scotia only if x is the east-west axis. The mart exports them as `longitude` and `latitude` under those names so the mistake cannot travel downstream.
2. **`the_geom` is a projected `POINT`**, with values like `POINT (446161.45 4949718.99)`. Those are metres in a UTM-style grid, not degrees. Nothing in this build reads that column.
3. **`location` carries embedded newlines** and a pre-formatted `(lat, long)` string. It is never parsed; both coordinates come from the two numeric columns.

## No population source

This build carries no population source, so it reports beds and never beds per capita.

## Row accounting (02_transform.sql)

Every raw row is classified into exactly one class, checked in this order, and every class is counted in the `row_accounting` section of the output whether or not the snapshot contains one:

1. `excluded_missing_facility_id`
2. `excluded_duplicate_facility_id`
3. `excluded_non_numeric_beds` (any of the four bed columns fails a numeric cast)
4. `excluded_negative_beds`
5. `excluded_fractional_beds` (a bed count that is not a whole number)
6. `excluded_unknown_zone` (a zone outside `zone_dim`)
7. `kept`

In this snapshot all 145 rows are kept and all six exclusion counts are zero. The section also carries `rows_read_minus_kept_and_excluded`, which is 0 when the classes account for every row, and `snapshot_row_count_matches_params`, which is 1 when the file still holds the pinned 145 rows.

The four bed columns arrive as `"144.0"`, so they are cast through `DOUBLE` and only then to `INTEGER`, with the fractional check standing between the two. That way a genuine `0.5` would be caught and counted rather than silently truncated to 0.

## Analysis (03_analysis.sql)

1. `facility_totals`: facility grain, with `total_beds` and `respite_beds` computed and kept apart.
2. `grand`: provincial facility count, bed totals by type, average, median, and the single entry access count.
3. `row_accounting`: the classification counts above.
4. `zone_totals`: facilities, beds, the nursing and residential split, respite, share, average, and median per zone.
5. `type_totals`: the same per published facility type label.
6. `bed_type_totals`: the four bed types, with the count of facilities holding any of each. `share_pct` is a share of `total_beds`, so it is filled for the two core types and blank for the two respite types, which sit outside that base.
7. `zone_bed_type`: the 4 x 4 zone-by-bed-type grid in long form, all 16 cells present even where a cell is zero.
8. `top_facilities`: the largest `params.top_facility_limit` facilities by `total_beds`.
9. `ltc_bed_supply`: the eight sections stacked into one table.

## Outputs

- `out/ltc_bed_supply.csv`, diffed against `expected/ltc_bed_supply.csv`: the sectioned result, 77 rows.
- `out/mart_ltc.csv`, copied to `bi/exports/mart_ltc.csv`: the long-form BI mart, 580 rows, one per facility per bed type.
- `out/show_beds_by_zone.csv`: the print-ready zone table behind `python run.py show`. Presentation only; `run.py` aligns the columns and computes nothing.
- `dashboard/data.js`: the mart re-emitted as a `const DATA = [...]` literal so the dashboard opens under `file://` with no server and no file picker.

## The dashboard re-derivation

`dashboard/dashboard.js` reads `DATA` and recomputes every figure on the page from the 580 long rows. Nothing is hardcoded, and the derived values must equal the golden output exactly:

| Figure | Value |
| --- | --- |
| Facilities | 145 |
| Total beds | 8,764 |
| Nursing home beds | 8,026 (91.58%) |
| Residential care beds | 738 (8.42%) |
| Nursing home respite beds, excluded | 41 |
| Residential care respite beds, excluded | 2 |
| Facilities in single entry access | 143 |
| Average beds per facility | 60.44 |
| Median beds per facility | 47.00 |
| Largest facility | Northwood Incorporated, Halifax, 385 beds |
| Central zone | 37 facilities, 3,135 beds, 35.77%, average 84.73, median 65.00 |
| Western zone | 43 facilities, 2,174 beds, 24.81%, average 50.56, median 47.00 |
| Eastern zone | 33 facilities, 1,906 beds, 21.75%, average 57.76, median 48.00 |
| Northern zone | 32 facilities, 1,549 beds, 17.67%, average 48.41, median 36.00 |

The page exposes those derivations on `window.LTC_DERIVED`, so the check can be run from the browser console against `expected/ltc_bed_supply.csv` without opening the SQL.

## Edge cases

- **Facilities holding both bed kinds** are counted in both bed types. Eight facilities carry the type `Nursing Home and Residential Care Facility` with nonzero counts in both columns, which is why the bed-type facility counts (107 with nursing beds, 46 with residential beds) add to more than 145.
- **Respite beds** are thin and lopsided. Only 38 facilities hold any respite bed at all, and exactly one facility holds a residential care respite bed. Three of the four zones have zero residential care respite beds, so those cells of the matrix are real zeroes rather than gaps.
- **Zone** is a health management zone, not a geographic one. Dykeland Lodge in Windsor sits in Central zone in the source. The build reports the published zone and never re-derives one from coordinates.
- **The two facilities outside single entry access**, Pont du Marais Boarding Home and Wedgewood House for Seniors, are both Western zone residential care facilities. Their beds stay in every total; single entry access is reported as a count, not a filter.
- **Facility name variants** are left alone. No name normalization runs, because `facility_id` is unique and is the join and tie-break key throughout.
- **The one accented facility name** (Foyer Pere Fiset) is why every file this build writes is UTF-8. `python run.py show` prints only zone and bed-type labels, so its output stays inside plain ASCII on a Windows console.

## Determinism

Every exported query ends in a total `ORDER BY` whose last term is unique, so the files are byte-stable run to run and version to version:

| File | Order |
| --- | --- |
| `out/ltc_bed_supply.csv` | `section_ord, ord`, unique across the whole table |
| `out/mart_ltc.csv` | `facility_id, bed_type`, unique per row |
| `out/show_beds_by_zone.csv` | `ord`, unique |

Inside the sectioned result each section's `ord` is a `ROW_NUMBER` over its own total order: fixed measure ordinals in `summary`, `row_accounting`, and `totals_tie`; `total_beds DESC, zone` in `zone_totals`; `total_beds DESC, facility_type` in `type_totals`; `bed_type_ord` in `bed_type_totals`; `zone, bed_type` in `zone_bed_type`; and `total_beds DESC, facility_id` in `top_facilities`. No section sorts on a measure alone, so a tie can never reorder the file.

The `totals_tie` section makes the arithmetic visible inside the golden file: the zone rollup, the facility-type rollup, the bed-type rollup, the zone-by-bed-type grid, and the raw facility sum all report 8,764.
