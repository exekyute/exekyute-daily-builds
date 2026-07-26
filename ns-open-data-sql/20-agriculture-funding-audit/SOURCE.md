# Source

- **Dataset:** Agriculture Funding Programs Details
- **Portal:** Nova Scotia Open Data, https://data.novascotia.ca
- **Dataset page:** https://data.novascotia.ca/d/jv92-pedy
- **Socrata resource endpoint:** https://data.novascotia.ca/resource/jv92-pedy.csv
- **Socrata 4x4 id:** `jv92-pedy`
- **Licence:** Open Government Licence - Nova Scotia (attribution required)
- **Pull date:** 2026-07-06
- **Snapshot:** `data/raw/ns_agriculture-funding_2026-07-06.csv`, 6,324 rows plus header
- **Pull method:** paged Socrata CSV endpoint with `?$limit=50000&$offset=...&$order=:id`; the second page came back empty, confirming the snapshot is complete
- **Catalog idea:** #9

The snapshot is committed so the pipeline and its golden output stay reproducible after the live dataset moves. Re-pulling on a later date means re-baselining `expected/funding_audit.csv` on purpose.
