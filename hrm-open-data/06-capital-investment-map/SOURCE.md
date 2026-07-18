# Source

**Dataset:** Capital Projects

**Portal:** Halifax Data Mapping and Analytics Hub (https://data-hrm.hub.arcgis.com)

**Dataset slug:** `HRM::capital-projects`

**Item id:** `3d468db830e3430b8e4340015e11517e`

**Service name:** `Capital_Projects`

**ArcGIS REST FeatureServer:** https://services2.arcgis.com/11XBiaBYA9Ep0yNJ/arcgis/rest/services/Capital_Projects/FeatureServer/0

**Hub CSV download (reference only, not used here):** https://data-hrm.hub.arcgis.com/api/download/v1/items/3d468db830e3430b8e4340015e11517e/csv?layers=0

**Licence:** Open Government Licence, Halifax. Attribution: Contains information licenced under the Open Government Licence, Halifax. Licence text: https://data-hrm.hub.arcgis.com/pages/open-data-licence.

**Pull date:** 2026-07-09

**Snapshot:** `data/raw/hrm_capital-projects_2026-07-09.geojson`, a FeatureCollection of 2,650 point features spanning budget years 2013 to 2021.

**Catalog idea:** #22 (frontloaded build 6).

## Coordinates: GeoJSON, not the projected grid columns

The dataset carries two coordinate representations. The `NORTHING` and `EASTING`
columns are projected grid values (a metre-based Web Mercator style grid, not
degrees) and would need an `ST_Transform` to become mappable latitude and
longitude. The GeoJSON export instead returns each project as a WGS84 point
(EPSG:4326) in the feature geometry. This build takes latitude and longitude
from that point geometry and never reads `NORTHING` or `EASTING`. A quick check
confirms the geometry is degrees in the Halifax range: longitude from about
-64.05 to -62.51 and latitude from about 44.47 to 45.09.

## No dollars in this dataset

Capital Projects has no budget, cost, or dollar field of any kind. It is a
register of where capital work was located, under which budget category and
year. Every measure in this build is therefore a count of capital projects, not
a sum of investment dollars.

## How the snapshot was pulled

The Hub one-click GeoJSON download is generated asynchronously and was still
pending at pull time, so the snapshot was assembled from the FeatureServer query
endpoint instead, which returns WGS84 geometry directly. The server caps a
single response at 2,000 features (`maxRecordCount` is 2000), so the pull is two
pages under a stable sort, then merged into one FeatureCollection:

    BASE=https://services2.arcgis.com/11XBiaBYA9Ep0yNJ/arcgis/rest/services/Capital_Projects/FeatureServer/0/query

    page 1: $BASE?where=1=1&outFields=*&orderByFields=OBJECTID&resultOffset=0&resultRecordCount=2000&f=geojson
    page 2: $BASE?where=1=1&outFields=*&orderByFields=OBJECTID&resultOffset=2000&resultRecordCount=2000&f=geojson

Page 1 returns 2,000 features (`exceededTransferLimit` true), page 2 returns the
remaining 650, for 2,650 in total. `orderByFields=OBJECTID` fixes the paging so
the two pages never overlap or gap. No app token or sign-in is needed for public
read. The merged result is saved verbatim as the dated snapshot above and
committed as the reproducibility anchor: `run.py` reads that file, never the live
endpoint.

## Fields in the source

| Field | Type | Meaning |
| --- | --- | --- |
| `OBJECTID` | integer | Unique record id; used only as the stable sort key |
| `LOC_ID` | text | Location id |
| `LOC_DESC` | text | Location description (street, park, address) |
| `WORK_DESC` | text | Description of the capital work |
| `PROJ_NAME` | text | Project name |
| `PROJ_NO` | text | Project number; one project can span several locations and years |
| `CATEGORY` | text | Budget category (labels are inconsistent across years; see spec.md) |
| `YEAR` | integer | Budget year |
| `LINK` | text | Link to the year's capital budget book (not used) |
| `NORTHING` | double | Projected grid northing (not used; see above) |
| `EASTING` | double | Projected grid easting (not used; see above) |
| `GLOBALID` | text | Global id (not used) |
| `ASSET_TYPE` | text | Asset type; blank on most records |

There are 2,650 records but only 280 distinct `PROJ_NO` values, so the natural
grain is one row per project location and budget year, not one row per project
number. Each record has its own point, which is what the map plots.
