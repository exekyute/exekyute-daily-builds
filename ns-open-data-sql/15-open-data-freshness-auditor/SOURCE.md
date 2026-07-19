# Source

**Dataset:** Nova Scotia Open Data Catalogue

**Portal page:** https://data.novascotia.ca/Public-Service/Nova-Scotia-Open-Data-Catalogue/3km6-ez4q

**Resource CSV:** https://data.novascotia.ca/resource/3km6-ez4q.csv

**Socrata 4x4 id:** `3km6-ez4q`

**Licence:** Open Government Licence - Nova Scotia. Attribution: contains information licensed under the Open Government Licence - Nova Scotia.

**Pull date:** 2026-07-06

**Snapshot:** `data/raw/ns_catalogue_2026-07-06.csv`, 1,269 rows (one per catalogued asset: 705 datasets, 323 charts, 123 maps, 51 filtered views, 44 external links, 22 stories, 1 calendar).

**Catalog idea:** #45.

## How the snapshot was pulled

The Socrata endpoint caps a default response at 1000 rows, so the pull asks for a large page with a stable sort:

    https://data.novascotia.ca/resource/3km6-ez4q.csv?$limit=50000&$offset=0&$order=url

`url` is unique per asset (1,269 distinct values in 1,269 rows), which makes it a stable paging key; the whole catalogue fits in one page anyway. No app token is needed for a one-off pull. The result is saved verbatim as the dated snapshot above and committed as the reproducibility anchor: `run.py` reads that file, never the live endpoint.

This dataset is the portal describing itself: each row is one asset the portal hosts, including the catalogue's own metadata dates. The `3km6-ez4q` id resolved on the pull date and returned the expected columns, so no id correction was needed.

## Columns in the source

| Column | Meaning |
| --- | --- |
| `name` | Asset title as shown on the portal |
| `description` | Free-text description of the asset |
| `detailedmetadata_department` | Owning department or agency |
| `type` | Asset kind: `dataset`, `chart`, `map`, `filter`, `href`, `story`, or `calendar` |
| `category` | Portal subject category (blank for 7 assets) |
| `tags` | Comma-separated keywords |
| `url` | Portal landing URL; ends in the asset's 4x4 id |
| `api_endpoint` | Socrata API URL for the asset |
| `last_metadata_updated_date` | Timestamp of the last metadata edit (UTC) |
| `last_data_updated_date` | Timestamp of the last data change (UTC) |

The pipeline uses `name`, `detailedmetadata_department`, `type`, `category`, `url`, and the two date columns; `description`, `tags`, and `api_endpoint` are loaded but not analyzed.
