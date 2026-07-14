# Data dictionary

Three files carry structured output: the frozen BI mart and the two golden results. Types are the DuckDB types the export writes.

## bi/exports/mart_collisions.csv

One row per collision, 46,248 rows. The wide, denormalized table both Tableau and Power BI read. The eight factor columns keep their source-style uppercase names so the Power BI DAX binds to them verbatim.

| # | Column | Type | Meaning | Units |
| --- | --- | --- | --- | --- |
| 1 | `collision_id` | integer | Surrogate key, one per collision (`COLLISION_SK`). | id |
| 2 | `accident_date` | date | Calendar date of the collision, local Halifax time. | date |
| 3 | `year` | integer | Year of the collision. | year |
| 4 | `month` | integer | Month of the collision, 1 to 12. | month |
| 5 | `hour` | integer | Hour of day, 0 to 23, local time. | hour |
| 6 | `weekday` | integer | Day of week, `isodow`: 1 = Monday to 7 = Sunday. | weekday |
| 7 | `lat` | double | Latitude, WGS84. | degrees |
| 8 | `lon` | double | Longitude, WGS84. | degrees |
| 9 | `road_location_1` | text | Primary road location. | text |
| 10 | `road_location_2` | text | Intersecting road location. Empty when not an intersection. | text |
| 11 | `collision_configuration` | text | Movement configuration of the collision. | text |
| 12 | `light_condition` | text | Light condition at the time. | text |
| 13 | `weather_condition` | text | Weather condition at the time. | text |
| 14 | `PEDESTRIAN_COLLISIONS` | integer | 1 if a pedestrian was involved, else 0. | flag |
| 15 | `BICYCLE_COLLISIONS` | integer | 1 if a cyclist was involved, else 0. | flag |
| 16 | `IMPAIRED_DRIVING` | integer | 1 if impaired driving was a factor, else 0. | flag |
| 17 | `DISTRACTED_DRIVING` | integer | 1 if distracted driving was a factor, else 0. | flag |
| 18 | `AGRESSIVE_DRIVING` | integer | 1 if aggressive driving was a factor, else 0. Source spelling kept. | flag |
| 19 | `INTERSECTION_RELATED` | integer | 1 if the collision was intersection-related, else 0. | flag |
| 20 | `FATAL_INJURY` | integer | 1 if the collision had a fatal injury, else 0. | flag |
| 21 | `NON_FATAL_INJURY` | integer | 1 if the collision had a non-fatal injury, else 0. | flag |

## out/collisions_by_year.csv (golden)

One row per year, 9 rows (2018 to 2026; 2026 is a partial year). Counts and shares of the contributing factors.

| # | Column | Type | Meaning | Units |
| --- | --- | --- | --- | --- |
| 1 | `year` | integer | Calendar year. | year |
| 2 | `collisions` | integer | Collisions in the year. | count |
| 3 | `pedestrian` | integer | Collisions involving a pedestrian. | count |
| 4 | `bicycle` | integer | Collisions involving a cyclist. | count |
| 5 | `impaired` | integer | Collisions with impaired driving. | count |
| 6 | `distracted` | integer | Collisions with distracted driving. | count |
| 7 | `intersection` | integer | Intersection-related collisions. | count |
| 8 | `fatal` | integer | Collisions with a fatal injury. | count |
| 9 | `pct_pedestrian` | number | `pedestrian` as a percent of `collisions`, one decimal. | percent |
| 10 | `pct_bicycle` | number | `bicycle` as a percent of `collisions`, one decimal. | percent |
| 11 | `pct_impaired` | number | `impaired` as a percent of `collisions`, one decimal. | percent |
| 12 | `pct_distracted` | number | `distracted` as a percent of `collisions`, one decimal. | percent |
| 13 | `pct_intersection` | number | `intersection` as a percent of `collisions`, one decimal. | percent |
| 14 | `pct_fatal` | number | `fatal` as a percent of `collisions`, one decimal. | percent |

## out/collisions_month_hour.csv (golden)

The month-by-hour count matrix, one row per hour of day, 24 rows.

| # | Column | Type | Meaning | Units |
| --- | --- | --- | --- | --- |
| 1 | `hour` | integer | Hour of day, 0 to 23, local time. | hour |
| 2 to 13 | `m01` to `m12` | integer | Collisions in that hour and calendar month (`m01` = January to `m12` = December), across all years. | count |

Notes:

- The per-year counts and the matrix both sum to 46,248, the collisions with a usable timestamp.
- `out/meta.csv` (`latest_full_year`, `pull_date`) is a two-field helper the browser dashboard reads to pick its headline year; it is not part of the golden diff.
