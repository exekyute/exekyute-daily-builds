# Source

- **Dataset:** Surface Water Grab Sample
- **Portal:** Nova Scotia Open Data, https://data.novascotia.ca
- **Dataset page:** https://data.novascotia.ca/d/wncu-ppda
- **Socrata resource endpoint:** https://data.novascotia.ca/resource/wncu-ppda.csv
- **Socrata 4x4 id:** `wncu-ppda`
- **Licence:** Open Government Licence - Nova Scotia (attribution required)
- **Pull date:** 2026-07-25
- **Snapshot:** `data/raw/ns_surface-water-grab_2026-07-25.csv`, 38,143 rows plus header
- **Pull method:** paged Socrata CSV endpoint with a stable sort key, `?$limit=50000&$offset=0&$order=:id`; the second request, `?$limit=50000&$offset=50000&$order=:id`, returned a header and no data rows, confirming the snapshot is complete
- **Catalog idea:** #25

The dataset publishes the NS Government Surface Water Quality Monitoring Network grab data: laboratory results and field sonde readings from eight river stations, 2002-06-12 through 2024-12-16, one row per analyte result.

The snapshot is committed so the pipeline and its golden output stay reproducible after the live dataset moves. Re-pulling on a later date means updating the filename in `sql/01_load.sql`, updating the `PULL_DATE` constant in `sql/00_schema.sql`, and re-baselining `expected/water_compliance.csv` on purpose.
