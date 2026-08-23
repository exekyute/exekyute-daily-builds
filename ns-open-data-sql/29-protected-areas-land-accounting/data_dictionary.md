# Data dictionary

All areas are hectares (ha). One hectare is 10,000 square metres, so 100 ha make
one square kilometre. Hectares come from the province's published `ha_gis`
field, rounded once to two decimals at the record level; nothing in this build
measures area off a polygon. Percentages are rounded to two decimals for
display, after the division runs on exact decimals.

A **record** is one row of the published layer, which is one polygon record. It
is not the same thing as one protected area: 1,161 records cover 436 distinct
area names, because larger areas are published as several multipart polygons.
Both counts appear in the output so they are never confused.

## out/protected_areas.csv (also expected/protected_areas.csv)

One sectioned result file. Columns not meaningful for a section are blank.

| Column | Type | Meaning |
| --- | --- | --- |
| section | text | Which block the row belongs to: `summary`, `coverage`, `totals_tie`, `by_designation`, `by_authority`, `by_owner`, `by_status`, or `concentration`. |
| rank | integer | Position within the section. The four breakdown sections rank by hectares descending; `concentration` uses `record_rank`; `summary`, `coverage`, and `totals_tie` use a fixed row order. |
| measure | text | Label for `summary`, `coverage`, and `totals_tie` rows (for example `total_protected_hectares`, `records_missing_designation_year`, `sum_by_owner`). Blank elsewhere. |
| designation | text | The `protect1` designation type, used verbatim, including compound labels such as `Wilderness Area, Conservation Easement`. Filled for `by_designation` and `concentration` rows, and on the largest-record summary row. |
| authority | text | The body responsible for the protection, after the organization-name rules. Filled for `by_authority` and `concentration` rows. |
| owner | text | The body that owns the land, after the organization-name rules. Filled for `by_owner` rows. |
| status | text | Protection status: `Designated`, `Designation decision made`, or `Considered protected`. Filled for `by_status` and `concentration` rows, and on the legally-designated summary row. |
| area_name | text | The `pro_name` of the protected area. Repeats across records of the same multipart area. Filled for `concentration` rows and the largest-record summary row. |
| records | integer | How many published records the row covers. On `summary` rows it also carries plain counts such as `distinct_area_names` and `designation_types`. Always 1 on a `concentration` row. |
| hectares | ha, 2 dp | The hectare figure for the row. On `coverage` rows it is the hectares behind that coverage class, for example the hectares with no designation year. |
| share_pct | percent, 2 dp | The row's share of total protected hectares. 100.00 on the grand-total row and on every `totals_tie` row. On the `share_of_provincial_land_pct` summary row it is instead the share of Nova Scotia's land area. |
| cumulative_hectares | ha, 2 dp | Running hectare total down the concentration curve. Filled only in `concentration`. |
| cumulative_share_pct | percent, 2 dp | Running share of total protected hectares down the concentration curve. Filled only in `concentration`; reaches 100.00 at record 1,161. |

### Summary rows, in order

| measure | What it holds |
| --- | --- |
| `total_protected_hectares` | 743,084.11 ha, the figure every breakdown ties to. |
| `protected_area_records` | 1,161 published records. |
| `distinct_area_names` | 436 distinct `pro_name` values across those records. |
| `designation_types` | 13 distinct `protect1` labels. |
| `authorities` | 25 distinct authority labels after normalization. |
| `land_owners` | 19 distinct owner labels after normalization. |
| `provincial_land_area_hectares` | The named denominator, 5,333,800 ha (see spec.md). |
| `share_of_provincial_land_pct` | Protected hectares over that denominator. |
| `largest_record_hectares` | The single largest record, with its name and designation. |
| `top_10_records_hectares` | Hectares held by the ten largest records, and their share. |
| `records_for_half_of_hectares` | How many records it takes to reach half the protected hectares. |
| `records_for_ninety_pct_of_hectares` | The same at ninety percent. |
| `legally_designated_hectares` | Hectares whose status is `Designated`, with the record count and share. |

## bi/exports/mart_protected.csv (copy of out/mart_protected.csv)

One row per published record, cleaned. 1,161 rows; `hectares` sums to exactly
743,084.11, the same total the golden file proves. Ordered by `record_rank`.

| Column | Type | Meaning |
| --- | --- | --- |
| objectid | integer | The source layer's row identifier. Unique across the snapshot, and the tie-breaker behind `record_rank`. |
| area_name | text | The protected area's published name. Repeats across records of the same multipart area. |
| designation | text | The `protect1` designation type, verbatim. The slicer field in the report. |
| authority | text | The body responsible for the protection. Rows of the report matrix. |
| owner | text | The body that owns the land. |
| status | text | `Designated`, `Designation decision made`, or `Considered protected`. |
| hectares | ha, 2 dp | The record's area in hectares. Set this to Fixed decimal number in Power Query. |
| designation_year | integer | The year the protection took legal effect, from the source's `stat_date`. **Empty in every row of this snapshot**, because the current publication of the layer carries no `stat_date` at all. It stays in the mart as an integer column so a future republication needs no schema change; see spec.md. Never a date, so DAX time-intelligence functions do not apply. |
| record_rank | integer | 1 for the largest record by hectares, 1,161 for the smallest, ties broken by `objectid`. This is the ordered integer index the running-total measure walks in place of a year axis. |
