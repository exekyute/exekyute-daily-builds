# Source

Three datasets from the Halifax Data Mapping and Analytics Hub
(https://data-hrm.hub.arcgis.com), all pulled on the same date from the shared
ArcGIS REST org `services2.arcgis.com/11XBiaBYA9Ep0yNJ`.

**Pull date:** 2026-07-13

**Licence:** Open Government Licence, Halifax. Attribution: Contains information
licenced under the Open Government Licence, Halifax. Licence text:
https://data-hrm.hub.arcgis.com/pages/open-data-licence.

**Catalog idea:** #16.

---

## 1. Bus Stops

- **Dataset slug:** `HRM::bus-stops`
- **Item id:** `29de9d04a3454e11a1e0a1f78a27bc07`
- **Service name:** `Bus_Stops_2`
- **FeatureServer:** https://services2.arcgis.com/11XBiaBYA9Ep0yNJ/arcgis/rest/services/Bus_Stops_2/FeatureServer/0
- **Snapshot:** `data/raw/hrm_bus-stops_2026-07-13.geojson`, a FeatureCollection of 2348 point features.

The row total was confirmed with `returnCountOnly=true` (2348). The per-request
cap is 2000, so the layer was pulled in two pages and the feature arrays merged
into one FeatureCollection. Each page requested `outSR=4326` and `f=geojson`, so
the geometry is a WGS84 point:

    .../Bus_Stops_2/FeatureServer/0/query?where=1=1&outFields=BUSSTOPID,STOPNUMBER,LOCATION,ACCESSIBLE,BUSSTATUS&orderByFields=BUSSTOPID&resultOffset=0&resultRecordCount=2000&outSR=4326&f=geojson
    .../Bus_Stops_2/FeatureServer/0/query?where=1=1&outFields=BUSSTOPID,STOPNUMBER,LOCATION,ACCESSIBLE,BUSSTATUS&orderByFields=BUSSTOPID&resultOffset=2000&resultRecordCount=2000&outSR=4326&f=geojson

`orderByFields=BUSSTOPID` fixes the row order across the two pages.

## 2. Transit Shelters

- **Dataset slug:** `HRM::transit-shelters`
- **Item id:** `e1ab0076711c4df8828009d248495692`
- **Service name:** `Transit_Shelters`
- **FeatureServer:** https://services2.arcgis.com/11XBiaBYA9Ep0yNJ/arcgis/rest/services/Transit_Shelters/FeatureServer/0
- **Snapshot:** `data/raw/hrm_transit-shelters_2026-07-13.geojson`, a FeatureCollection of 521 point features.

521 rows is under the 2000 cap, so the layer was pulled in one request with
`outSR=4326` and `f=geojson`:

    .../Transit_Shelters/FeatureServer/0/query?where=1=1&outFields=SHELTERID,BUSSTOPID,LOCATION,INSTYR&orderByFields=SHELTERID&resultRecordCount=2000&outSR=4326&f=geojson

Each shelter carries a `BUSSTOPID` that links it to a bus stop. The pipeline uses
that link to flag which stops have a shelter; `INSTYR` is present in the snapshot
but not carried into any output.

## 3. Park & Ride

- **Dataset slug:** `HRM::park-ride`
- **Item id:** `2e1a4a314a6e415bb7d7346e96a62191`
- **Service name:** `Park_Ride`
- **FeatureServer:** https://services2.arcgis.com/11XBiaBYA9Ep0yNJ/arcgis/rest/services/Park_Ride/FeatureServer/0
- **Snapshot:** `data/raw/hrm_park-ride_2026-07-13.geojson`, a FeatureCollection of 15 polygon features.

This layer is polygons, not points, so it was pulled as GeoJSON and each lot is
reduced to its centroid for the map (`ST_Centroid` in DuckDB's `spatial`
extension). 15 rows is well under the cap, so it was pulled in one request with
`outSR=4326` and `f=geojson`:

    .../Park_Ride/FeatureServer/0/query?where=1=1&outFields=PNRID,PNR_NAME,ADDRESS,PARKING_CAPACITY,ROUTES_SERVICED&orderByFields=PNRID&resultRecordCount=2000&outSR=4326&f=geojson

No app token or sign-in is needed for public read. Each response is saved
verbatim as the dated snapshot above and committed as the reproducibility anchor:
`run.py` reads those files, never the live endpoints.

---

## Coordinates: WGS84

All three snapshots were requested with `outSR=4326`, so their geometry is degrees
(EPSG:4326), not a projected grid. A quick check confirms the coordinates fall in
the Halifax range: latitude from about 44.57 to 44.89 and longitude from about
-63.86 to -63.28.

## Fields used

**Bus Stops** (`ACCESSIBLE` coded values from the layer: `A` Accessible, `N`
Non-Standard, `I` Inaccessible; `BUSSTATUS` here is `INS` In Service or `TMP`
Temporary):

| Field | Type | Meaning | Used |
| --- | --- | --- | --- |
| `OBJECTID` | integer | ArcGIS row id. | Not carried |
| `BUSSTOPID` | text | Stop id, unique per stop (2348 distinct). | Yes (mart key, shelter link) |
| `STOPNUMBER` | text | Public stop number. | Yes |
| `LOCATION` | text | Address or place description. | Yes |
| `ACCESSIBLE` | text | Accessibility code (`A`, `N`, `I`). | Yes (reduced to 0/1) |
| `BUSSTATUS` | text | Status code (`INS`, `TMP`). | Yes (carried as `status`) |

**Transit Shelters:**

| Field | Type | Meaning | Used |
| --- | --- | --- | --- |
| `SHELTERID` | text | Shelter id. | Yes |
| `BUSSTOPID` | text | Bus stop the shelter serves. | Yes (link to stop) |
| `LOCATION` | text | Address or place description. | Yes |
| `INSTYR` | integer | Install year. | Not carried |

**Park & Ride:**

| Field | Type | Meaning | Used |
| --- | --- | --- | --- |
| `PNRID` | text | Lot id (used for the pull sort). | Not carried |
| `PNR_NAME` | text | Lot name, unique per lot (15 distinct). | Yes (`name`) |
| `ADDRESS` | text | Lot address. | Not carried |
| `PARKING_CAPACITY` | integer | Posted parking capacity. | Yes (`capacity`) |
| `ROUTES_SERVICED` | text | Routes the lot serves. | Yes (`routes`) |
| polygon geometry | polygon | Lot footprint. | Yes (centroid to lat, lon) |
