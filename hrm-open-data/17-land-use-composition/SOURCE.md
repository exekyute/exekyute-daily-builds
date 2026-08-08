# Source

This build joins two layers from the Halifax Data Mapping and Analytics Hub. The
zoning layer carries the land use polygons; the community layer supplies the
geometry the "by community" rollup needs, because zoning has no community column.

## Dataset 1: Zoning Boundaries (the land use polygons)

**Portal:** Halifax Data Mapping and Analytics Hub (https://data-hrm.hub.arcgis.com)

**Dataset slug:** `HRM::zoning-boundaries`

**Item id:** `11adc4e1e52a45b5b9f6bc63ef6e0883`

**Service name:** `ZoningBoundaries`

**ArcGIS REST FeatureServer:** https://services2.arcgis.com/11XBiaBYA9Ep0yNJ/arcgis/rest/services/ZoningBoundaries/FeatureServer/0

**Hub GeoJSON download (reference):** https://data-hrm.hub.arcgis.com/api/download/v1/items/11adc4e1e52a45b5b9f6bc63ef6e0883/geojson?layers=0

**Snapshot:** `data/raw/hrm_zoning-boundaries_2026-07-13.geojson`, a FeatureCollection of 11,076 polygon features. 206 distinct `ZONE` codes plus polygons with a null code.

## Dataset 2: Community Boundaries / General Service Areas (the community geometry)

**Dataset slug:** `HRM::community-boundaries`

**Item id:** `b4088a068b794436bdb4e5c31df76fe2`

**Service name:** `GSA`

**ArcGIS REST FeatureServer:** https://services2.arcgis.com/11XBiaBYA9Ep0yNJ/arcgis/rest/services/GSA/FeatureServer/0

**Snapshot:** `data/raw/hrm_community-boundaries_2026-07-13.geojson`, a FeatureCollection of 200 community polygons. `GSA_NAME` is the community name (for example EAST LOON LAKE VILLAGE), `MUN_CODE` the municipality code.

## Licence

Open Government Licence, Halifax. Attribution: Contains information licenced under
the Open Government Licence, Halifax. Licence text:
https://data-hrm.hub.arcgis.com/pages/open-data-licence.

## Pull date

2026-07-13.

## Why the community layer is needed: the spatial join

The zoning layer has no community, district, or area name of any kind. To answer
"what share of each community's land carries each land use class", each zoning
polygon is assigned to a community by a point-in-polygon test: the community
whose General Service Area boundary contains the zoning polygon's centroid
(`ST_Within(ST_Centroid(zoning.geom), gsa.geom)`). Centroid assignment is a
single deterministic test per polygon, far lighter than apportioning each
polygon's area across the boundaries it may straddle, and it lands every polygon
in exactly one community. Of 11,076 polygons, 7 have a centroid that falls
outside every community boundary (coastal edge) and are labelled Unassigned so no
area is lost. 182 of the 200 communities carry at least one zoning polygon.

## How the snapshots were pulled

Both layers were pulled from the FeatureServer query endpoint as GeoJSON in WGS84
(`outSR=4326`). The server caps a single response at 2,000 features
(`maxRecordCount` is 2000), so zoning is paged with `resultOffset` under a stable
`orderByFields=OBJECTID` sort and merged into one FeatureCollection; the 200
community polygons come back in one page.

    BASE=https://services2.arcgis.com/11XBiaBYA9Ep0yNJ/arcgis/rest/services/<Service>/FeatureServer/0/query
    common: ?where=1=1&outFields=*&orderByFields=OBJECTID&f=geojson&outSR=4326&geometryPrecision=6&maxAllowableOffset=0.00003

    ZoningBoundaries: six pages, resultOffset 0, 2000, 4000, 6000, 8000, 10000 (resultRecordCount=2000)
    GSA:              one page, resultOffset 0 (resultRecordCount=2000)

`geometryPrecision=6` limits coordinates to six decimal places (about 0.1 m) and
`maxAllowableOffset=0.00003` degrees (about 3 m) applies a light server-side
generalization, which together keep the committed zoning snapshot near 16 MB
instead of 152 MB. The generalization removes redundant vertices only; it does
not change which community a centroid falls in, and the area measure is computed
from the geometry as true ground area (see below), so the effect on every
reported figure is well under one percent. `orderByFields=OBJECTID` fixes the
paging so pages never overlap or gap. No app token or sign-in is needed for
public read. `run.py` reads the committed snapshots, never the live endpoint.

## Area: true geodesic ground area, not the carried Shape__Area

The zoning service stores its geometry and its `Shape__Area` column in the Web
Mercator projection (EPSG:3857, `wkid` 102100). Web Mercator area is inflated by
roughly a factor of three at Halifax's latitude, so `Shape__Area` sums to about
10,633 km2 of "zoned land", which is far larger than the ground truth. This build
therefore does not use `Shape__Area`. Area is computed as the true geodesic
ground area of each polygon on the WGS84 spheroid (`ST_Area_Spheroid` on the
pulled lon/lat geometry), which totals about 3,637 km2 of zoned land, consistent
with HRM's real scale. Because land use shares are ratios, they are within a few
hundredths of a percent whichever area basis is used; the geodesic basis simply
makes the absolute square-kilometre figures true to the ground.

## Fields read from the source

### Zoning Boundaries

| Field | Type | Meaning |
| --- | --- | --- |
| `OBJECTID` | integer | Unique polygon id; used only as the stable sort key |
| `ZONE` | text | Raw zone code (206 distinct, some null); reused across bylaws with different meanings, so the description is the primary class signal |
| `DESCRIPTION` | text | Plain-language zone label; drives the land use class mapping (see spec.md) |
| `BYLAW_ID` | integer | Source land use by-law id (not used) |
| `Shape__Area` | double | Planar area in the service's Web Mercator projection; not used (see above) |
| `geom` | geometry | Polygon in WGS84 (EPSG:4326); supplies the centroid for the community join and the true geodesic area |

### Community Boundaries (GSA)

| Field | Type | Meaning |
| --- | --- | --- |
| `GSA_NAME` | text | Community name; the rollup key |
| `MUN_CODE` | text | Municipality code |
| `geom` | geometry | Community polygon in WGS84; the containing boundary for the centroid test |

## Domain note

Planning and land use is the portal's largest domain by dataset count. Zoning is
its central layer, and it is one of the few HRM layers where the question needs a
real point-in-polygon join rather than a group-by on a named area column.
