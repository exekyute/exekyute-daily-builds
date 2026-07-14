# Data dictionary

## expected/key_figures.csv

One row per key figure. Three columns.

| Column | Type | Meaning |
| --- | --- | --- |
| `metric` | text | Which figure the row holds. One of the metric names below. |
| `key` | text | Sub-key within the metric (a county, fiscal year, project type, or source). Empty for single-value metrics. |
| `value` | text | The figure itself, formatted as written by build.py: counts as integers, shares as decimals with 4 places (0.3359 means 33.59 percent), kilometres with 2 places. |

### Metrics

| Metric | Key | Value type | Meaning |
| --- | --- | --- | --- |
| `total_projects` | empty | count | All rows in the snapshot, roads and bridges combined. |
| `projects_by_source` | `roads` or `bridges` | count | Rows from each underlying dataset. |
| `leading_county` | empty | text | County with the most planned projects. Ties break to the county earliest in alphabetical order. |
| `leading_county_projects` | empty | count | Project count in that county. |
| `top_type` | empty | text | Project type (the `construct_` grouping) with the most projects. Same tie rule. |
| `top_type_share` | empty | share | That type's share of all projects, rounded half-away-from-zero to 4 decimals. |
| `projects_by_county` | county name | count | Projects per county, every county in the snapshot. |
| `projects_by_year` | fiscal year label | count | Projects per fiscal year (`year_start` as published, for example `2025-2026`). |
| `type_share_overall` | project type | share | Each type's share of all projects, rounded to 4 decimals. |
| `road_km_by_year` | fiscal year label | km | Planned road kilometres per fiscal year, roads dataset only, rounded to 2 decimals. |
| `road_km_total` | empty | km | Sum of the rounded per-year kilometre figures, so the block ties exactly. |

## Data sheet (workbook)

One row per planned project, cleaned and typed from the snapshot.

| Column | Type | Meaning | Units |
| --- | --- | --- | --- |
| `source` | text | Which underlying dataset the row came from: `roads` or `bridges`. | none |
| `project` | text | Project description as published (`project_de`). | none |
| `county` | text | County, whitespace-trimmed. Blank becomes `Unspecified`. | none |
| `type` | text | Project-type grouping as published in `construct_`. Blank becomes `Unspecified`; the stray `Gravel Roads Program` spelling is folded into `Gravel Road Program`. | none |
| `year` | text | Fiscal year label from `year_start`, for example `2025-2026`. Blank becomes `Unknown`. | fiscal year |
| `km` | number | Planned length from the roads dataset. Empty for bridges and for road rows published without a length. | kilometres |
| `status` | text | Project status as published. Blank becomes `Unspecified`. | none |

## Model sheet blocks

Every figure in these blocks is a live formula over the Data sheet. Exact cell
references are in the cell map in spec.md.

| Block | Meaning | Units |
| --- | --- | --- |
| Headline | Total projects (COUNTA), leading county and its count (INDEX/MATCH over the county matrix), largest project type and its share (INDEX/MATCH and MAX over the type-mix block), road/bridge split (COUNTIFS). | counts, text, share |
| Projects by county and fiscal year | COUNTIFS matrix, one row per county, one column per fiscal year, with row totals, column totals, and a grand total that ties to the headline total. | project counts |
| Project-type mix by fiscal year | COUNTIFS matrix, one row per project type, one column per fiscal year, plus a total column and a share column (`ROUND(total / all projects, 4)`). | counts, share |
| Road kilometres by fiscal year | `ROUND(SUMIFS(km, year, source="roads"), 2)` per fiscal year, with a total row that sums the rounded cells. | kilometres |
