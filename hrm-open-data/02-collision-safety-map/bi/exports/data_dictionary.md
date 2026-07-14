# Data dictionary: mart_collisions.csv

The frozen dashboard mart. One row per collision, 46,248 rows. Tableau, Power BI,
and the browser dashboard all read this one file, so a viewer can flip between the
three faces and read the same figure. Written by `sql/99_export.sql`, ordered by
`collision_id`.

| # | Column | Type | Meaning |
| --- | --- | --- | --- |
| 1 | `collision_id` | text | Collision surrogate key (`COLLISION_SK`), one per collision and unique across the snapshot. |
| 2 | `accident_date` | date | Calendar date of the collision, in local Halifax time. |
| 3 | `year` | integer | Year of the collision (2018 to 2026; 2026 is partial). |
| 4 | `month` | integer | Month number 1 to 12. |
| 5 | `hour` | integer | Hour of day 0 to 23, local time. |
| 6 | `weekday` | integer | Day of week, 1 = Monday to 7 = Sunday (`isodow`). |
| 7 | `lat` | number | WGS84 latitude. |
| 8 | `lon` | number | WGS84 longitude. |
| 9 | `road_location_1` | text | Primary road location. |
| 10 | `road_location_2` | text | Intersecting road location. Blank when there is no cross street. |
| 11 | `collision_configuration` | text | Movement configuration of the collision (for example, rear end, left turn across opposing traffic). |
| 12 | `light_condition` | text | Light condition at the time (Daylight, Dark, and so on). |
| 13 | `weather_condition` | text | Weather condition at the time (Clear, Rain, Snow, and so on). |
| 14 | `PEDESTRIAN_COLLISIONS` | integer | 1 if a pedestrian was involved, else 0. |
| 15 | `BICYCLE_COLLISIONS` | integer | 1 if a cyclist was involved, else 0. |
| 16 | `IMPAIRED_DRIVING` | integer | 1 if impaired driving was a factor, else 0. |
| 17 | `DISTRACTED_DRIVING` | integer | 1 if distracted driving was a factor, else 0. |
| 18 | `AGRESSIVE_DRIVING` | integer | 1 if aggressive driving was a factor, else 0. Source spelling kept. |
| 19 | `INTERSECTION_RELATED` | integer | 1 if the collision was intersection related, else 0. |
| 20 | `FATAL_INJURY` | integer | 1 if the collision involved a fatal injury, else 0. |
| 21 | `NON_FATAL_INJURY` | integer | 1 if the collision involved a non-fatal injury, else 0. |

The eight factor columns keep their source-style uppercase names so the Power BI
DAX binds to them verbatim (for example, `mart_collisions[PEDESTRIAN_COLLISIONS] = 1`).

## How to bind the geography

Halifax communities and districts are not built-in geographic roles in Tableau, so
the map binds to the `lat` and `lon` this mart already carries, not to a named
role. Every row in this snapshot carries a coordinate, so none drop from the map.

## Reconciliation

- `COUNT` of all rows is **46,248** (46,285 in the raw snapshot, less 37 with no
  usable timestamp).
- `COUNT` of rows with `year = 2025` is **5,734**, the latest full year.
- `SUM(PEDESTRIAN_COLLISIONS)` over `year = 2025` is **169**, the headline figure
  the Tableau count and the Power BI card both must read.
- `SUM(INTERSECTION_RELATED)` over `year = 2025` is **2,512**, which is 43.8 percent
  of that year.
- Grouping all rows by `hour`, hour **16** (4 pm) is the busiest of the day with
  **4,232** collisions across the window.
