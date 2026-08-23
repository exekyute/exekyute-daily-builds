# Data dictionary

Bed counts are whole numbers. Shares, averages, and medians are rounded to two decimals (`params.round_dp`) and stored at that same scale, so a share written as `35.77` is the rounded figure rather than a longer one cut short.

The definition every bed figure below rests on:

```
total_beds = nursing_homes_nh_no_of_beds
           + residential_care_facilities_rcf_no_of_beds
```

Respite beds (`nursing_homes_nh_no_of_respite_beds`, `rcf_respite_beds`) are reported as their own bed types and are excluded from `total_beds`.

## out/ltc_bed_supply.csv (also expected/ltc_bed_supply.csv)

One sectioned result file, 77 rows plus a header. Columns not meaningful for a section are blank.

| Column | Type | Meaning |
| --- | --- | --- |
| section | text | Which block the row belongs to: `summary`, `row_accounting`, `totals_tie`, `zone_totals`, `type_totals`, `bed_type_totals`, `zone_bed_type`, or `top_facilities`. |
| ord | integer | Position within the section. Unique inside a section, so `section` plus `ord` identifies a row. In `top_facilities` it is the bed rank. |
| measure | text | Label for `summary`, `row_accounting`, and `totals_tie` rows (for example `total_beds`, `excluded_unknown_zone`, `sum_by_zone`). Blank elsewhere. |
| zone | text | Health management zone: `Central`, `Eastern`, `Northern`, or `Western`. Filled for `zone_totals`, `zone_bed_type`, and `top_facilities`. |
| facility_type | text | Published facility type label. Filled for `type_totals` and `top_facilities`. |
| bed_type | text | `nursing`, `residential`, `nursing_respite`, or `residential_respite`. Filled for `bed_type_totals` and `zone_bed_type`. |
| facility_id | text | Source facility code, unique across the snapshot. Filled for `top_facilities` and the `largest_facility` summary row. |
| facility_name | text | Facility name as published. Same rows as `facility_id`. |
| town | text | Town as published. Same rows as `facility_id`. |
| facilities | integer | Facility count for the row. In `bed_type_totals` and `zone_bed_type` it is the number of facilities holding at least one bed of that type, so those counts overlap across bed types and do not add to 145. In `row_accounting` it carries the row count for the named class. |
| beds | integer | Bed figure for the row. `total_beds` in `zone_totals`, `type_totals`, and `top_facilities`; beds of the named type in `bed_type_totals` and `zone_bed_type`. |
| share_pct | percent, 2 dp | The row's share of the 8,764 total beds. Blank on the two respite rows of `bed_type_totals`, which sit outside that base by definition, and blank throughout `zone_bed_type` and `row_accounting`. |
| avg_beds | decimal, 2 dp | Mean `total_beds` per facility for the row's group. Filled in `zone_totals`, `type_totals`, and the `avg_beds_per_facility` summary row. |
| median_beds | decimal, 2 dp | Continuous median (`MEDIAN`, the same as `QUANTILE_CONT(x, 0.5)`) of `total_beds` per facility for the row's group. Same rows as `avg_beds`, plus the `median_beds_per_facility` summary row. |

### Section notes

- **summary**: ten fixed measures, in a fixed order, ending in `largest_facility`, which names the single biggest facility.
- **row_accounting**: `rows_read`, `rows_kept`, the six exclusion classes, `rows_read_minus_kept_and_excluded` (0 when the classes cover every row), and `snapshot_row_count_matches_params` (1 when the file still holds the pinned 145 rows).
- **totals_tie**: five independent re-summations of `total_beds`. All five read 8,764 or the build is wrong.

## bi/exports/mart_ltc.csv (copy of out/mart_ltc.csv)

Long form: one row per facility per bed type, 145 x 4 = 580 rows. `(facility_id, bed_type)` is unique. This shape is what makes the zone-by-bed-type matrix a group-by rather than a pivot.

| Column | Type | Meaning |
| --- | --- | --- |
| facility_id | text | Source facility code. Unique per facility, repeated across that facility's four rows. |
| facility_name | text | Facility name as published. |
| town | text | Town as published. |
| postal_code | text | Postal code as published. |
| zone | text | Health management zone. |
| facility_type | text | Published facility type: `Nursing Home`, `Residential Care Facility`, or `Nursing Home and Residential Care Facility`. |
| sea_participating | text | `Y` or `N`, whether the facility takes part in single entry access. |
| longitude | decimal degrees | From the source's `x_coordinate`, which is longitude despite the name. Negative across Nova Scotia. |
| latitude | decimal degrees | From the source's `y_coordinate`, which is latitude despite the name. |
| facility_total_beds | integer | The facility's `total_beds`. **Repeats down all four of the facility's rows, so never SUM it.** Sum `beds` where `is_core_bed = 1` instead, or take `MAX` of this column inside a facility grouping. |
| bed_type | text | `nursing`, `residential`, `nursing_respite`, or `residential_respite`. |
| is_core_bed | integer 0/1 | 1 for the two bed types inside `total_beds`, 0 for the two respite types. |
| beds | integer | Beds of this type at this facility. Zero rows are present, not dropped, so every facility has all four rows. |

## dashboard/data.js (generated)

`const DATA = [...]`, one object per mart row, carrying the nine fields the dashboard uses: `facility_id`, `facility_name`, `town`, `zone`, `facility_type`, `sea_participating`, `bed_type`, `is_core_bed`, `beds`. Plumbing only, so the page loads with no server and no file picker; the aggregation lives in `dashboard/dashboard.js`.

## out/show_beds_by_zone.csv (generated, not committed)

The table `python run.py show` prints: one row per zone ordered by `total_beds` descending with `zone` as the tie-break, then a pinned `ALL ZONES` row. Columns are `zone`, `facilities`, `nursing_beds`, `residential_beds`, `total_beds`, `share_pct`, `avg_beds`, `median_beds`, `nursing_respite_beds`, `residential_respite_beds`, all defined as above.
