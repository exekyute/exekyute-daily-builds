# Source

**Dataset:** PPL&C Permit Processing Times

**Portal:** Halifax Data Mapping and Analytics Hub (https://data-hrm.hub.arcgis.com)

**Dataset page:** https://data-hrm.hub.arcgis.com/datasets/HRM::pplc-permit-processing-times

**Slug:** `HRM::pplc-permit-processing-times`

**ArcGIS item id:** `ba0ed0900b274984bcd9e05063ffb388`

**Service:** `PPLC_Permit_Processing_Times`

**CSV download:** https://data-hrm.hub.arcgis.com/api/download/v1/items/ba0ed0900b274984bcd9e05063ffb388/csv?layers=0

**ArcGIS REST FeatureServer:** https://services2.arcgis.com/11XBiaBYA9Ep0yNJ/arcgis/rest/services/PPLC_Permit_Processing_Times/FeatureServer/0

**Licence:** Open Government Licence, Halifax. Attribution: Contains information licenced under the Open Government Licence, Halifax. Licence text: https://data-hrm.hub.arcgis.com/pages/open-data-licence.

**Pull date:** 2026-07-09

**Snapshot:** `data/raw/hrm_permit-processing-times_2026-07-09.csv`, 149,711 data rows across 57,076 permits. This is the current dataset, not an archived or year-stamped companion.

## How the snapshot was pulled

The whole table was pulled from the Hub CSV download endpoint, which builds an export server-side and serves it once ready:

    https://data-hrm.hub.arcgis.com/api/download/v1/items/ba0ed0900b274984bcd9e05063ffb388/csv?layers=0

The response is a small JSON status object while the export generates (`Pending`, then `ExportingData` with a percent), then the CSV once complete. The file was saved verbatim as the dated snapshot above and committed as the reproducibility anchor: `run.py` reads that file, never the live endpoint.

The same rows are reproducible from the FeatureServer without waiting on the export, which is how the row count and field names were verified on the pull date. The per-request cap is 2,000 rows and `supportsPagination` is true, so a full pull pages with `resultOffset` and `resultRecordCount`:

    .../FeatureServer/0/query?where=1=1&outFields=Permit_Number,Issuance_Stage,Jurisdictional_Breakdown,Total_Occurrence,Total_Duration&orderByFields=OBJECTID&resultOffset=0&resultRecordCount=2000&f=json

Incrementing `resultOffset` by 2,000 walks all 149,711 rows. The row total was confirmed with `returnCountOnly=true` (149,711) and the three `Issuance_Stage` and three `Jurisdictional_Breakdown` values with `returnDistinctValues=true`. No app token or sign-in is needed for public read.

## Columns in the source

| Column | Type | Meaning |
| --- | --- | --- |
| `OBJECTID` | integer | ArcGIS row id. Not used by this build. |
| `Permit_Number` | text | Permit identifier. A single permit carries more than one row, one per issuance stage and jurisdictional breakdown. |
| `Issuance_Stage` | text | Stage of the permit timeline: `Pre Issuance`, `Post Issuance`, or `Other Timeline`. |
| `Jurisdictional_Breakdown` | text | Who the time sits with: `Customer`, `Staff`, or `Other Type`. |
| `Total_Occurrence` | integer | Count of occurrences aggregated into this row. |
| `Total_Duration` | number | Processing time for this permit, stage, and jurisdiction. See the unit note in `data_dictionary.md`. |

The grain is one row per permit per issuance stage per jurisdictional breakdown, confirmed by sampling: permit `BLAST-2021-10569` carries a `Post Issuance` / `Customer` row and a separate `Pre Issuance` / `Staff` row. No `(permit, stage, jurisdiction)` triple repeats in the snapshot. The dataset carries no geometry, which is expected for this table.
