# Source

**Dataset:** Crime

**Portal:** Halifax Data Mapping and Analytics Hub (https://data-hrm.hub.arcgis.com)

**Hub slug:** `HRM::crime`

**Item id:** `f6921c5b12e64d17b5cd173cafb23677`

**Service:** `Crime` (FeatureServer, layer 0)

**REST query (fields and count):** `https://services2.arcgis.com/11XBiaBYA9Ep0yNJ/arcgis/rest/services/Crime/FeatureServer/0/query?where=1=1&outFields=*&f=json`

**CSV download (snapshot source):** `https://data-hrm.hub.arcgis.com/api/download/v1/items/f6921c5b12e64d17b5cd173cafb23677/csv?layers=0`

**Licence:** Contains information licenced under the Open Government Licence, Halifax. Licence text: https://data-hrm.hub.arcgis.com/pages/open-data-licence.

**Pull date:** 2026-07-13

**Snapshot:** `data/raw/hrm_crime_2026-07-13.csv`, 90 incident rows.

**Observed evt_date window in this snapshot:** 2026-07-05 to 2026-07-11.

## This is a rolling feed, not a multi-year aggregate

The catalog describes Crime as an aggregated summary, but the live layer is a small
rolling incident feed of recent Halifax Regional Police events. Each row is one
event. The feed holds only a short window of recent days and refreshes, so both the
row count and the date window move between pulls: the count was 99 when the catalog
was written, 90 at this pull. This snapshot is therefore a point-in-time capture.
Every figure in the workbook is derived from the committed snapshot, not the live
endpoint, so the workbook is fully reproducible from `data/raw/`; a fresh pull on a
later day would return different incidents and different figures.

## How the snapshot was pulled

The Hub download endpoint generates the CSV asynchronously (a first request can
return a `Pending` status), so the pull requests the CSV item URL above and reads
it once it resolves, saving the response verbatim as the dated snapshot. No app
token or sign-in is needed for public read. The row count was confirmed against the
REST endpoint with `returnCountOnly=true` (90) before the CSV was saved.

## Columns in the source CSV

| Column | Meaning |
| --- | --- |
| `OBJECTID` | ArcGIS feature id, per-layer surrogate key |
| `EVT_RT` | Event record type (all `GO` in this snapshot) |
| `EVT_RIN` | Event record number, the police occurrence number |
| `EVT_DATE` | Event date, formatted `M/D/YYYY 12:00:00 AM` (date only, midnight) |
| `LOCATION` | Street name of the event |
| `RUCR` | Numeric UCR (Uniform Crime Reporting) code |
| `RUCR_EXT_D` | Crime category text, for example `ASSAULT`, `THEFT FROM VEHICLE` |
| `x`, `y` | Web Mercator (EPSG:3857) coordinates; not used by this workbook |

The workbook uses `EVT_DATE`, `EVT_RIN`, `RUCR_EXT_D` (category), `RUCR` (code),
and `LOCATION`. The `x` and `y` projected coordinates and `OBJECTID`/`EVT_RT` are
carried in the raw snapshot but not brought into the workbook.
