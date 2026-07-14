# Source

**Dataset:** Traffic Collisions

**Portal:** Halifax Data Mapping and Analytics Hub (ArcGIS Hub), https://data-hrm.hub.arcgis.com

**Slug:** `HRM::traffic-collisions`

**Item id:** `e0293fd4721e41d7be4d7386c3c59c16`

**Service:** `Traffic_Collisions`

**REST FeatureServer:** `https://services2.arcgis.com/11XBiaBYA9Ep0yNJ/arcgis/rest/services/Traffic_Collisions/FeatureServer/0/query`

**CSV download:** `https://data-hrm.hub.arcgis.com/api/download/v1/items/e0293fd4721e41d7be4d7386c3c59c16/csv?layers=0`

**Licence:** Open Government Licence, Halifax. Attribution: Contains information licenced under the Open Government Licence, Halifax.

**Pull date:** 2026-07-09

**Snapshot:** `data/raw/hrm_traffic-collisions_2026-07-09.csv`, 46,285 rows (the whole set), 2018 to 2026.

## How the snapshot was pulled

The field list was first confirmed live against the REST FeatureServer with `f=json`, and the row total against `returnCountOnly=true`, which returned 46,285. The whole set was then pulled through the Hub CSV download endpoint:

    https://data-hrm.hub.arcgis.com/api/download/v1/items/e0293fd4721e41d7be4d7386c3c59c16/csv?layers=0

The Hub generates this export asynchronously: the first request returns a `{"status":"Pending"}` body while it builds the file, and the same URL returns the finished CSV once it is ready. No app token or sign-in is needed for the public read. The result is saved verbatim as the dated snapshot above and committed as the reproducibility anchor: `run.py` reads that file, never the live endpoint.

## Field notes

The REST service exposes raw field names; the Hub CSV export renders them as friendly, space-separated headers and localizes the timestamp. The columns this build reads, with the REST field name for each:

| CSV header | REST field | Meaning |
| --- | --- | --- |
| `COLLISION_SK` | `COLLISION_SK` | Surrogate key, one per collision (unique across all 46,285 rows) |
| `Accident Date and Time` | `ACCIDENT_DATETIME` | Collision timestamp, local Halifax wall-clock time |
| `Latitude WGS84` | `WGS84_LAT_COORD` | Latitude, WGS84 |
| `Longitude WGS84` | `WGS84_LON_COORD` | Longitude, WGS84 |
| `Road Location` | `ROAD_LOCATION_1` | Primary road location |
| `Intersecting Road Location` | `ROAD_LOCATION_2` | Intersecting road location |
| `Collision Configuration` | `COLLISION_CONFIGURATION` | Movement configuration of the collision |
| `Non Fatal Injury` | `NON_FATAL_INJURY` | Non-fatal injury flag (`Yes` or blank) |
| `Fatal Injury` | `FATAL_INJURY` | Fatal injury flag (`Yes` or blank) |
| `Pedestrian Collision` | `PEDESTRIAN_COLLISIONS` | Pedestrian-involved flag (`Y` or `N`) |
| `Bicycle Collision` | `BICYCLE_COLLISIONS` | Cyclist-involved flag (`Y` or `N`) |
| `Aggressive Driving` | `AGRESSIVE_DRIVING` | Aggressive-driving flag (`Y` or `N`); source spelling kept |
| `Distracted Driving` | `DISTRACTED_DRIVING` | Distracted-driving flag (`Y` or `N`) |
| `Impaired Driving` | `IMPAIRED_DRIVING` | Impaired-driving flag (`Y` or `N`) |
| `Intersection Collision` | `INTERSECTION_RELATED` | Intersection-related flag (`Y` or `N`) |
| `Light Condition` | `LIGHT_CONDITION` | Light condition at the time |
| `Weather Condition` | `WEATHER_CONDITION` | Weather condition at the time |

**On the timestamp.** The REST service stores `ACCIDENT_DATETIME` as an epoch in milliseconds (UTC). The Hub CSV export renders it in local Halifax time, for example the epoch `1780246800000` renders as `5/31/2026 5:00:00 PM`. This build reads the localized CSV value directly, so the derived hour and weekday read as the local time a collision happened, with no timezone arithmetic and no dependency beyond DuckDB.

**On the current-year rows.** The snapshot runs into 2026, which is only partway complete on the pull date. The headline is stated for 2025, the latest full year, derived from a literal pull-date constant in the SQL rather than `CURRENT_DATE`. The partial 2026 rows are kept in the mart and the per-year table, and are simply the most recent, incomplete year.
