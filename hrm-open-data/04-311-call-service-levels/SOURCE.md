# Source

**Dataset:** 311 Call Volumes

**Portal:** Halifax Data Mapping and Analytics Hub (https://data-hrm.hub.arcgis.com)

**Dataset page:** https://data-hrm.hub.arcgis.com/datasets/HRM::311-call-volumes

**Item id:** `8bfd88fc3de041c894cb69e5c62304fb`

**Service:** `311_Call_Volumes`

**CSV download:** https://data-hrm.hub.arcgis.com/api/download/v1/items/8bfd88fc3de041c894cb69e5c62304fb/csv?layers=0

**ArcGIS REST FeatureServer:** https://services2.arcgis.com/11XBiaBYA9Ep0yNJ/arcgis/rest/services/311_Call_Volumes/FeatureServer/0/query

**Licence:** Open Government Licence, Halifax. Attribution: Contains information licenced under the Open Government Licence, Halifax. Licence text: https://data-hrm.hub.arcgis.com/pages/open-data-licence.

**Pull date:** 2026-07-09.

**Snapshot:** `data/raw/hrm_311-call-volumes_2026-07-09.csv`, 145,363 rows (one per half-hour interval per date), spanning 2017-01-01 through 2026-07-04. Saved verbatim, including the leading byte-order mark the Hub export writes; DuckDB strips it on load.

**Catalog idea:** #10.

## How the snapshot was pulled

The whole table is small enough to take in one download, so the pull uses the Hub's item CSV export rather than paging the FeatureServer:

    https://data-hrm.hub.arcgis.com/api/download/v1/items/8bfd88fc3de041c894cb69e5c62304fb/csv?layers=0

That endpoint is asynchronous: the first request kicks off a server-side export and returns a small JSON status body while the file generates, so the pull polls the same URL until the response is the CSV rather than the status JSON. The full 145,363-row file returned in one piece. No app token or sign-in is needed for public read. The result is saved as the dated snapshot above and committed as the reproducibility anchor: `run.py` reads that file, never the live endpoint.

To reproduce the same data from the REST service instead (for example if the item export is unavailable), page the FeatureServer at its 2000-row cap with a stable sort:

    .../FeatureServer/0/query?where=1=1&outFields=*&orderByFields=ObjectId&resultRecordCount=2000&resultOffset=0&f=json

then increment `resultOffset` by 2000 until fewer than 2000 rows come back.

## Columns in the source

| Column | Type | Used | Meaning |
| --- | --- | --- | --- |
| `CALL_DATE` | date (rendered as a formatted local datetime string in the CSV) | yes | Calendar date of the interval. The CSV renders it with a constant display time (07:00 or 08:00, a daylight-saving offset) that the pipeline discards, keeping the date. |
| `MILITARY_HOUR` | integer | no | Hour of the day, 0 to 23, for the interval. |
| `INTERVAL` | text | no | Half-hour interval label, for example `07:30 AM - 08:00 AM`. |
| `OFFERED` | integer | yes | Calls offered to the queue in the interval. |
| `HANDLED` | integer | yes | Calls answered by an agent in the interval. |
| `ABANDONED` | integer | yes | Calls abandoned before an agent answered. |
| `PROCESSED_IN_IVR` | integer | yes | Calls resolved in the automated menu without reaching an agent. |
| `TOTAL_TALK_TIME` | integer (seconds) | yes | Total agent talk time in the interval. |
| `AVERAGE_TALK_TIME` | integer (seconds) | no | Interval average talk time. Not used: a monthly average is derived from `TOTAL_TALK_TIME` over `HANDLED` so it aggregates correctly. |
| `ObjectId` | integer | no | ArcGIS row id. Carried in the raw table for fidelity, not used in the rollup. |

The item id resolved on the pull date and returned the expected fields (verified against the FeatureServer `?f=json` metadata), so no id correction was needed.
