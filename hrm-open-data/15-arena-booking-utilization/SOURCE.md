# Source

**Dataset:** Parks and Recreation Arena Bookings

**Portal:** Halifax Data Mapping and Analytics Hub (https://data-hrm.hub.arcgis.com)

**Dataset page:** https://data-hrm.hub.arcgis.com/datasets/HRM::parks-and-recreation-arena-bookings

**Slug:** `HRM::parks-and-recreation-arena-bookings`

**ArcGIS item id:** `057ac4a8514e4e12b6085d9d87d98f01`

**Service:** `Parks_and_Recreation_Arena_Bookings`

**CSV download:** https://data-hrm.hub.arcgis.com/api/download/v1/items/057ac4a8514e4e12b6085d9d87d98f01/csv?layers=0

**ArcGIS REST FeatureServer:** https://services2.arcgis.com/11XBiaBYA9Ep0yNJ/arcgis/rest/services/Parks_and_Recreation_Arena_Bookings/FeatureServer/0

**Licence:** Open Government Licence, Halifax. Attribution: Contains information licenced under the Open Government Licence, Halifax. Licence text: https://data-hrm.hub.arcgis.com/pages/open-data-licence.

**Pull date:** 2026-07-13

**Snapshot:** `data/raw/hrm_arena-bookings_2026-07-13.csv`, 39,858 data rows, one row per booking. The dataset carries no geometry, which is expected for a booking ledger. This is the current dataset, not an archived or year-stamped companion.

## How the snapshot was pulled

The whole table was pulled from the Hub CSV download endpoint, which builds an export server-side and serves it once ready:

    https://data-hrm.hub.arcgis.com/api/download/v1/items/057ac4a8514e4e12b6085d9d87d98f01/csv?layers=0

The response is a small JSON status object while the export generates (`ExportingData` with a percent), then a redirect to the finished CSV. The file was saved verbatim as the dated snapshot above and committed as the reproducibility anchor: `run.py` reads that file, never the live endpoint.

The same rows are reproducible from the FeatureServer without waiting on the export, which is how the row count and field names were verified on the pull date. The per-request cap is 2,000 rows and `supportsPagination` is true, so a full pull pages with `resultOffset` and `resultRecordCount`:

    .../FeatureServer/0/query?where=1=1&outFields=FACILITY,DATE,START_TIME,END_TIME,EVENT_TYPE,SERVICE&orderByFields=OBJECTID&resultOffset=0&resultRecordCount=2000&f=json

Incrementing `resultOffset` by 2,000 walks all rows. The row total was confirmed with `returnCountOnly=true` (39,858), and the distinct `SERVICE`, `EVENT_TYPE`, and `FACILITY` values with `returnDistinctValues=true`. No app token or sign-in is needed for public read.

## A note on the CSV rendering of the time fields

In the ArcGIS service, `START_TIME` and `END_TIME` are stored as epoch milliseconds (field type `esriFieldTypeDate`). The CSV export formats them as local datetime strings such as `4/1/2025 10:30:00 AM`, and it renames every column to its display alias. Because this build reads the committed CSV, `02_transform.sql` parses those datetime strings rather than epoch milliseconds; the booked-hours figure it computes is identical either way, since a single booking never crosses a daylight-saving change and so its start and end share one local offset. See `data_dictionary.md`.

## Columns in the source

The CSV header carries the display aliases; the ArcGIS field names are listed alongside.

| CSV header (alias) | ArcGIS field | Type | Meaning |
| --- | --- | --- | --- |
| `OBJECTID` | `OBJECTID` | integer | ArcGIS row id. Not used by this build. |
| `UID` | `ID` | text | Booking identifier (GUID). Not used by this build. |
| `Facility Name` | `LOCATION` | text | Facility building, e.g. Cole Harbour Place. Not used; this build keys on the pad. |
| `Arena Pad Name` | `FACILITY` | text | The ice pad, e.g. Scotia One Arena. This build's `facility`. |
| `Booking Date` | `DATE` | date | Booking date, `YYYY-MM-DD`. Drives `month_start` and `year`. |
| `Day of Week` | `DAY_OF_WEEK` | text | Weekday name. Not used by this build. |
| `Booking Start` | `START_TIME` | datetime | Booking start (epoch ms in the service; local datetime string in the CSV). |
| `Booking End` | `END_TIME` | datetime | Booking end (epoch ms in the service; local datetime string in the CSV). |
| `Event Type` | `EVENT_TYPE` | text | The activity, e.g. Hockey, Figure Skating, System Booking. Carried through but not the use-type source. |
| `Account Name` | `ACCOUNT_NAME` | text | Booking account. Not used by this build. |
| `User Group Type` | `ACCOUNT_TYPE` | text | Account type. Not used by this build. |
| `User Category` | `ACCOUNT_CATEGORY` | text | User category. Not used by this build. |
| `Service` | `SERVICE` | text | Service line, e.g. RBC/GEC - Arena Ice, HRM - Arena Dry Floor, CHP System Booking. Drives `use_type`. |
| `Add Date` | `ADD_DATE` | date | Record add date. Not used by this build. |
| `Modified Date` | `MODIFIED_DATE` | date | Record modified date. Not used by this build. |

The grain is one row per booking. Ice versus dry-floor use is carried by `SERVICE` (a service whose text contains "Ice" or "Dry Floor"), not by `EVENT_TYPE`. The snapshot spans booking dates from 2025-01-01 through 2029-12-31: arenas schedule seasons ahead, so the ledger holds forward bookings, heaviest in 2025 and 2026 and thinning into later years.
