# Source

**Dataset:** Public Trees

**Portal:** Halifax Data Mapping and Analytics Hub (https://data-hrm.hub.arcgis.com)

**Slug:** `HRM::public-trees`

**Item id:** `33a4e9b6c7e9439abcd2b20ac50c5a4d`

**Service:** `Public_Trees` (FeatureServer, layer 0, point geometry)

**REST query base:**
`https://services2.arcgis.com/11XBiaBYA9Ep0yNJ/arcgis/rest/services/Public_Trees/FeatureServer/0/query`

**CSV download (item-keyed, attributes only):**
`https://data-hrm.hub.arcgis.com/api/download/v1/items/33a4e9b6c7e9439abcd2b20ac50c5a4d/csv?layers=0`
(GeoJSON is the same URL with `/geojson`.)

**Licence:** Open Government Licence, Halifax. Attribution: Contains information licenced under the Open Government Licence, Halifax. Licence text: https://data-hrm.hub.arcgis.com/pages/open-data-licence

**Pull date:** 2026-07-09

**Snapshot:** `data/raw/hrm_public-trees_2026-07-09.csv`, 78,896 data rows (one per tree, with WGS84 coordinates).

**Catalog idea:** #18.

## How the snapshot was pulled

The tree points needed their coordinates, so the pull went to the FeatureServer with
`returnGeometry=true` and `outSR=4326` rather than the attribute-only CSV download.
The per-request cap is 2,000 rows, so the pull paged with `resultOffset` and a stable
`OBJECTID` order across 40 requests. Each request was:

    GET .../Public_Trees/FeatureServer/0/query
        ?where=1=1
        &outFields=TREEID,SP_SCIEN,SP_COMM,DBH,INSTYR,OWNER,ASSETSTAT,LOCGEN,WIRES
        &orderByFields=OBJECTID
        &resultOffset=<0, 2000, 4000, ... 78000>
        &resultRecordCount=2000
        &returnGeometry=true
        &outSR=4326
        &f=json

Each feature's geometry `y` and `x` were written as the `LAT` and `LON` columns. The
result is saved verbatim as the dated snapshot above and committed as the
reproducibility anchor: `run.py` reads that file, never the live endpoint. The live row
total was confirmed with `returnCountOnly=true` (78,896) on the pull date.

## Columns in the snapshot

| Column | Source field | Meaning |
| --- | --- | --- |
| `TREEID` | TreeID | Unique asset identifier, e.g. `TRE616082`. |
| `SP_SCIEN` | Scientific Name | Botanical name. |
| `SP_COMM` | Common Name | Common species name. |
| `DBH` | Diameter at breast height | Integer size-class code 1 to 9 (see note below). |
| `INSTYR` | Year Planted | Planting year; sparse and often 0 or blank. |
| `OWNER` | Owner | `HRM` or blank. |
| `ASSETSTAT` | Asset Status | Uniformly `INS` (installed). |
| `LOCGEN` | General Location | `ROW` (street right-of-way) or `OSP` (open space). |
| `WIRES` | Wires Present | `Y`, `N`, or blank. |
| `LAT`, `LON` | geometry (EPSG:4326) | Point latitude and longitude. |

## Notes on the live data (verified on the pull date)

These shape the cleaning rules in spec.md and are recorded so the build's choices are
traceable to the data as published:

- **No condition rating exists.** The `CONDITPERD` field ("Condition Update Period
  (Days)") is empty for all 78,896 rows, and the layer carries no other health or
  condition attribute. The categorical dimensions in this build are therefore the two
  real attributes the inventory does record: general location (`LOCGEN`) and whether
  overhead wires are present (`WIRES`).
- **DBH is a size-class code, not a measurement.** Although the field is labelled
  "Diameter at breast height" with unit `CM`, the stored values are integers 1 to 9
  (mean about 2.7). It is treated as an ordered size-class code and bucketed into tiers.
- **Planting year is sparse.** Only 9,997 rows carry a plausible `INSTYR` in 1900 to
  2026; the remainder are 0, blank, or out of range (one value is 2105). The recorded
  years all fall in 2013 to 2025. Install year is null for every other tree.
- **Scientific-name casing is inconsistent** in the source (for example
  `Acer Platanoides` for Norway Maple next to a correct `Acer rubrum` for Red Maple).
  The pipeline normalizes each to binomial case.
