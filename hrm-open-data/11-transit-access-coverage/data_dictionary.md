# Data dictionary

Three output files. The two marts are also frozen to `bi/exports/` for Tableau.

## out/mart_stops.csv

One row per bus stop. 2348 rows.

| # | Column | Type | Meaning |
| --- | --- | --- | --- |
| 1 | `busstopid` | text | Stop id, unique per stop (2348 distinct). Shelters link to this. |
| 2 | `stopnumber` | text | Public stop number. |
| 3 | `location` | text | Address or place description, whitespace-normalized. |
| 4 | `accessible` | integer | 1 when the stop is coded `A` (Accessible), else 0. |
| 5 | `status` | text | Stop status code: `INS` (In Service) or `TMP` (Temporary). |
| 6 | `has_shelter` | integer | 1 when at least one shelter record links to this stop, else 0. |
| 7 | `lat` | number | Latitude, WGS84, from the GeoJSON point, six decimals. |
| 8 | `lon` | number | Longitude, WGS84, from the GeoJSON point, six decimals. |

Row order: `busstopid`.

## out/mart_parkride.csv

One row per park and ride lot. 15 rows.

| # | Column | Type | Meaning |
| --- | --- | --- | --- |
| 1 | `name` | text | Lot name, unique per lot (15 distinct). |
| 2 | `capacity` | integer | Posted parking capacity, in spaces. |
| 3 | `routes` | text | Routes the lot serves, as published (comma-separated). |
| 4 | `lat` | number | Latitude of the lot polygon centroid, WGS84, six decimals. |
| 5 | `lon` | number | Longitude of the lot polygon centroid, WGS84, six decimals. |

Row order: `name`, then `lat`, then `lon`.

## out/access_summary.csv

The golden coverage figures. 1 row.

| # | Column | Type | Meaning |
| --- | --- | --- | --- |
| 1 | `total_stops` | integer | Count of bus stops (2348). |
| 2 | `accessible_stops` | integer | Count of stops coded `A` (1711). |
| 3 | `accessible_share_pct` | number | `accessible_stops` as a percent of `total_stops`, one decimal (72.9). |
| 4 | `total_shelters` | integer | Count of shelter records (521). |
| 5 | `stops_with_shelter` | integer | Count of distinct stops with at least one shelter (454). |
| 6 | `shelter_coverage_pct` | number | `stops_with_shelter` as a percent of `total_stops`, one decimal (19.3). |
| 7 | `parkride_lots` | integer | Count of park and ride lots (15). |
| 8 | `parkride_capacity` | integer | Total posted parking capacity across the lots (2444). |

Row order: `total_stops` (single row).

Notes:

- `total_shelters` (521) exceeds `stops_with_shelter` (454) on purpose: several
  shelters sit at the same stop, and a few reference a stop id outside the current
  stop layer, so they add to the shelter count without adding a covered stop.
- `accessible` counts only the `A` code. `N` (Non-Standard) and `I` (Inaccessible)
  stops are not accessible.
