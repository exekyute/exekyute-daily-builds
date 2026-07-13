# Source

This build joins two layers from the Halifax Data Mapping and Analytics Hub: the
attribute-only building permit table and its geolocated sibling that carries the
point coordinates.

## Base attributes: PPL&C Building Permits

**Portal page:** https://data-hrm.hub.arcgis.com/datasets/HRM::pplc-building-permits

**Item id:** `6cef25e4172e4466a1eb8d3fd794f571`

**FeatureServer:** https://services2.arcgis.com/11XBiaBYA9Ep0yNJ/arcgis/rest/services/PPLC_Issued_Building_Permits/FeatureServer/0

**CSV download:** https://data-hrm.hub.arcgis.com/api/download/v1/items/6cef25e4172e4466a1eb8d3fd794f571/csv?layers=0

**Rows:** 18,316. This is the authoritative attribute set (permit number, issuance
date, work type, declared value, community, district, net new units, and more) but
it carries no geometry.

## Coordinates: PPL&C Building Permits Geolocated

**Portal page:** https://data-hrm.hub.arcgis.com/datasets/HRM::pplc-building-permits-geolocated

**Item id:** `6ac34a5bc6554d25b137ef432d506f08` (service `PPLC_Permits_Geolocated`)

**FeatureServer:** https://services2.arcgis.com/11XBiaBYA9Ep0yNJ/arcgis/rest/services/PPLC_Permits_Geolocated/FeatureServer/0

**CSV download:** https://data-hrm.hub.arcgis.com/api/download/v1/items/6ac34a5bc6554d25b137ef432d506f08/geojson?layers=0

**Rows:** 15,949 point features (EPSG:4326). Each carries `PERMIT_NUMBER` plus a
point geometry. This layer is the source of latitude and longitude only.

## Licence

Open Government Licence, Halifax. Attribution:

> Contains information licenced under the Open Government Licence, Halifax.

Licence text: https://data-hrm.hub.arcgis.com/pages/open-data-licence

## Pull date

2026-07-09. The same date is pinned as the literal `pull_date` constant in
`sql/02_transform.sql`; no step calls `CURRENT_DATE`.

## Snapshot

`data/raw/hrm_pplc-building-permits_2026-07-09.csv`, 18,316 rows. This is the
committed reproducibility anchor: the base attribute rows LEFT JOINed to the
geolocated points, so every permit attribute is present and the 18,224 permits
that geolocated also carry a latitude and longitude. `run.py` reads this file,
never the live endpoint.

**Join key:** base `Permit_Number` = geolocated `PERMIT_NUMBER`. The geolocated
layer holds one point per permit number (15,949 distinct, no duplicates), so the
LEFT JOIN adds at most one coordinate pair per base row and the base grain of
18,316 rows is preserved. The 92 base permits whose number has no geolocated match
keep every attribute and simply carry no coordinates.

## How the snapshot was pulled

Both layers cap a response at 2,000 rows (`maxRecordCount` = 2000), so each was
paged with a stable sort and joined in DuckDB. The exact requests, run once on the
pull date:

Base attributes, paged with `resultOffset` in steps of 2,000:

    https://services2.arcgis.com/11XBiaBYA9Ep0yNJ/arcgis/rest/services/PPLC_Issued_Building_Permits/FeatureServer/0/query
      ?where=1=1
      &outFields=OBJECTID,Permit_Number,Date_of_Permit_Issuance,Estimated_Project_Value,Work_Type,Primary_Work_Scope,Permit_Status,Community,District,Net_New_Units,Number_of_Storeys,Type_of_Structure
      &orderByFields=OBJECTID
      &returnGeometry=false
      &f=json

Geolocated points, paged the same way, returning geometry in WGS84:

    https://services2.arcgis.com/11XBiaBYA9Ep0yNJ/arcgis/rest/services/PPLC_Permits_Geolocated/FeatureServer/0/query
      ?where=1=1
      &outFields=PERMIT_NUMBER
      &returnGeometry=true
      &outSR=4326
      &orderByFields=OBJECTID
      &f=json

ArcGIS returns date fields as epoch milliseconds; `Date_of_Permit_Issuance` is
stored at noon UTC, so each value converts to its Halifax calendar date without an
off-by-one. The geometry `x` is longitude and `y` is latitude. No app token or
sign-in is needed for public read.

## Columns in the committed snapshot

| Column | Source | Meaning |
| --- | --- | --- |
| `source_object_id` | base `OBJECTID` | Stable per-record key; fixes row order. |
| `permit_number` | base `Permit_Number` | Permit identifier. Not unique: 16,030 distinct across 18,316 records. |
| `date_of_permit_issuance` | base | Date the permit was issued, `YYYY-MM-DD`. Blank when not yet issued. |
| `estimated_project_value` | base | Declared construction value in dollars. |
| `work_type` | base | New Building, Renovation, or Addition. |
| `primary_work_scope` | base | Finer work scope. |
| `permit_status` | base | Workflow status (Issued, Completed, In Review, and so on). |
| `community` | base | Community name. Blank on some records. |
| `district` | base | Council district (District 01 to District 16, or Unidentified). |
| `net_new_units` | base | Net change in residential units for the permit; can be negative. |
| `number_of_storeys` | base | Storeys in the structure. |
| `type_of_structure` | base | Structure type description. |
| `latitude` | geolocated `y` | WGS84 latitude. Blank when no geolocated match. |
| `longitude` | geolocated `x` | WGS84 longitude. Blank when no geolocated match. |
