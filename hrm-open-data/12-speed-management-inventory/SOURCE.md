# Source

Three layers from the Halifax Data Mapping and Analytics Hub
(https://data-hrm.hub.arcgis.com), all read from the shared HRM ArcGIS REST
FeatureServer at organisation id `11XBiaBYA9Ep0yNJ`.

**Pull date:** 2026-07-13 (the literal constant used in every snapshot filename and
in this build).

**Licence:** Open Government Licence, Halifax. Attribution: Contains information
licenced under the Open Government Licence, Halifax. Licence text:
https://data-hrm.hub.arcgis.com/pages/open-data-licence.

## Layer 1: Speed Display Signs (points)

- **Dataset slug:** `HRM::speed-display-signs`
- **Item id:** `92b59f263845457391d9207d7f474e6d`
- **Service name:** `Speed_Display_Signs`
- **FeatureServer:** https://services2.arcgis.com/11XBiaBYA9Ep0yNJ/arcgis/rest/services/Speed_Display_Signs/FeatureServer/0
- **Geometry:** point. **Rows:** 73.
- **Snapshot:** `data/raw/hrm_speed-display-signs_2026-07-13.geojson`, a
  FeatureCollection of 73 point features. Every record is `SIGNTYPE = SPDSGN`
  (Speed Display Sign); 61 are In Service and 12 Disposed, and all 73 are kept.

## Layer 2: Traffic Control Locations (points)

- **Dataset slug:** `HRM::traffic-control-locations`
- **Item id:** `07e30ae319a24614918f77a3483e8652`
- **Service name:** `Traffic_Control_Locations`
- **FeatureServer:** https://services2.arcgis.com/11XBiaBYA9Ep0yNJ/arcgis/rest/services/Traffic_Control_Locations/FeatureServer/0
- **Geometry:** point. **Rows:** 707.
- **Snapshot:** `data/raw/hrm_traffic-control-locations_2026-07-13.geojson`, a
  FeatureCollection of 707 point features across eight `CONTROL_TYPE` codes
  (signalized intersections, flashing beacons, roundabouts, and more).

## Layer 3: Neighbourhood Speed Limit (polylines)

- **Dataset slug:** `HRM::neighbourhood-speed-limit`
- **Item id:** `1bbee08f88ad439d950ef450afbcdaf5`
- **Service name:** `Neighbourhood_Speed_Limit`
- **FeatureServer:** https://services2.arcgis.com/11XBiaBYA9Ep0yNJ/arcgis/rest/services/Neighbourhood_Speed_Limit/FeatureServer/0
- **Geometry:** polyline. **Rows:** 13,835.
- **Snapshot:** `data/raw/hrm_neighbourhood-speed-limit_2026-07-13.geojson`, a
  FeatureCollection of 13,835 line features with a posted `SPEED` and a published
  `Shape__Length` in metres. This same file is committed to
  `bi/exports/speed_limits.geojson` for Tableau to render as a line layer.

## How the snapshots were pulled

The two point layers were pulled with `outSR=4326` and `f=geojson`, so each feature
carries a WGS84 point (EPSG:4326) in its geometry. Both are well under the 2,000
per-request cap, so each came back in one page:

    https://services2.arcgis.com/11XBiaBYA9Ep0yNJ/arcgis/rest/services/Speed_Display_Signs/FeatureServer/0/query?where=1=1&outFields=*&orderByFields=OBJECTID&outSR=4326&f=geojson

    https://services2.arcgis.com/11XBiaBYA9Ep0yNJ/arcgis/rest/services/Traffic_Control_Locations/FeatureServer/0/query?where=1=1&outFields=*&orderByFields=OBJECTID&outSR=4326&f=geojson

The polyline layer holds 13,835 features, past the 2,000 cap, so it was paged with
`resultOffset` and `resultRecordCount=2000` (seven pages, offsets 0 to 12000) and
the feature arrays concatenated in order. It is already published in WGS84, so no
`outSR` override is needed:

    https://services2.arcgis.com/11XBiaBYA9Ep0yNJ/arcgis/rest/services/Neighbourhood_Speed_Limit/FeatureServer/0/query?where=1=1&outFields=*&orderByFields=OBJECTID&f=geojson&resultOffset=0&resultRecordCount=2000

`orderByFields=OBJECTID` fixes the row order in every page. Row totals were confirmed
with `returnCountOnly=true` (73, 707, and 13,835). No app token or sign-in is needed
for public read. The responses are saved verbatim as the dated snapshots above and
committed as the reproducibility anchor: `run.py` reads those files, never the live
endpoint.

## Coded values

`CONTROL_TYPE` on the traffic control locations is an integer with a coded-value
domain, and `SIGNTYPE` on the signs is a short string code with its own domain. Both
are decoded to their published domain labels in `sql/02_transform.sql`; the code-to-
label maps are copied verbatim from each layer's field metadata (`?f=json`). The
`CONTROL_TYPE` codes present in the data are 6, 7, 8, 10, 11, 12, 14, and 15.

## Catalog idea

Idea #9, Speed management inventory. BI status SINGLE (Tableau).
