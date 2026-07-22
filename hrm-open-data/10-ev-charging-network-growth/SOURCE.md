# Source

**Dataset:** EV Charging Station

**Portal:** Halifax Data Mapping and Analytics Hub (https://data-hrm.hub.arcgis.com)

**Dataset slug:** `HRM::ev-charging-station`

**Item id:** `5447b08b3e254c99aedf9665c7e6d5a4`

**Service name:** `EV_Charging_Station`

**ArcGIS REST FeatureServer:** https://services2.arcgis.com/11XBiaBYA9Ep0yNJ/arcgis/rest/services/EV_Charging_Station/FeatureServer/0

**Hub CSV download (reference only, not used here):** https://data-hrm.hub.arcgis.com/api/download/v1/items/5447b08b3e254c99aedf9665c7e6d5a4/csv?layers=0

**Hub GeoJSON download (reference only):** https://data-hrm.hub.arcgis.com/api/download/v1/items/5447b08b3e254c99aedf9665c7e6d5a4/geojson?layers=0

**Licence:** Open Government Licence, Halifax. Attribution: Contains information licenced under the Open Government Licence, Halifax. Licence text: https://data-hrm.hub.arcgis.com/pages/open-data-licence.

**Pull date:** 2026-07-13

**Snapshot:** `data/raw/hrm_ev-charging-station_2026-07-13.geojson`, a FeatureCollection of 33 point features, every one an installed (`ASSETSTAT = INS`), publicly accessible (`EVACCESS = PUBLIC`), HRM-owned charging station, spanning install years 2024 to 2026.

**Catalog idea:** #31.

## How the snapshot was pulled

The whole table is small (33 rows, well under the 2,000 per-request cap), so it was pulled in one request from the FeatureServer query endpoint with `outSR=4326` and `f=geojson`, which returns each station as a WGS84 point (EPSG:4326) in the feature geometry:

    https://services2.arcgis.com/11XBiaBYA9Ep0yNJ/arcgis/rest/services/EV_Charging_Station/FeatureServer/0/query?where=1=1&outFields=*&orderByFields=EVCSID&outSR=4326&f=geojson

`orderByFields=EVCSID` fixes the row order in the response. The row total was confirmed with `returnCountOnly=true` (33). No app token or sign-in is needed for public read. The response is saved verbatim as the dated snapshot above and committed as the reproducibility anchor: `run.py` reads that file, never the live endpoint.

## Coordinates: GeoJSON point, in WGS84

The snapshot was requested with `outSR=4326`, so the feature geometry is degrees (EPSG:4326), not a projected grid. This build takes latitude and longitude straight from that point geometry. A quick check confirms the geometry is degrees in the Halifax range: longitude from about -64.06 to -63.15 and latitude from about 44.63 to 44.79.

## Fields in the source

| Field | Type | Meaning | Used |
| --- | --- | --- | --- |
| `OBJECTID` | integer | ArcGIS row id. | Load only; not a mart column |
| `EVCSID` | text | EV charging station id, unique per station. | Yes (mart key) |
| `ASSETID` | text | Asset id (mirrors `EVCSID`). | No |
| `ASSETCODE` | text | Asset code. | No |
| `OWNER` | text | Owner. Every record is `HRM`. | Yes |
| `HRMINTRST` | text | HRM interest flag. | No |
| `CHARTYPE` | text | Charging level: `L2` (Level 2 AC) or `DCFC` (DC fast). | Yes |
| `LOCATION` | text | Address or place description. | Yes |
| `LOCGEN` | text | General location code. | No |
| `CONNECTYPE` | text | Connector type: `J1772`, `CCSCHADEMO`, `CCSNACS`. | Yes |
| `POWER` | double | Power rating, in the `POWERUNIT` unit. | Yes (`power_kw`) |
| `POWERUNIT` | text | Power unit. Every record is `KW`. | Confirms the unit |
| `COST` | text | Cost-per-minute code. | No |
| `PAYMETHOD` | text | Payment method. | No |
| `HOUR` | integer | Operating hours per day. Every record is `24`. | No (uniform) |
| `QUANTITY` | integer | Available ports at the station. | Yes |
| `ASSETSTAT` | text | Asset status. Every record is `INS` (installed). | Yes (guard) |
| `INSTYR` | integer | Install year (2024, 2025, or 2026). | Yes (`install_year`) |
| `CONDIT` | integer | Condition score. | No |
| `CONDITDTE` | date | Condition date. | No |
| `SOURCE` | text | Data source note. | No |
| `SACC` | text | Source accuracy. | No |
| `ADDDATE` | date | Record add date. | No |
| `MODDATE` | date | Record modified date. | No |
| `CONDITPERD` | integer | Condition update period (days). Mostly null. | No |
| `CONDITEXP` | date | Condition expiry date. | No |
| `EVACCESS` | text | Charger access. Every record is `PUBLIC`. | Yes |
| `GLOBALID` | text | Global id. | No |

There are 33 records and 33 distinct `EVCSID` values, so the natural grain is one row per charging station. Several stations share one `LOCATION` (a site can hold several chargers), which is expected: for example five stations sit at Cole Harbour Place and five at Armdale Rotary.
