# Source

- **Dataset:** Invest NS Financial Programs
- **Portal:** Nova Scotia Open Data, https://data.novascotia.ca
- **Dataset page:** https://data.novascotia.ca/d/6aac-8xtn
- **Socrata resource endpoint:** https://data.novascotia.ca/resource/6aac-8xtn.csv
- **Socrata 4x4 id:** `6aac-8xtn`
- **Licence:** Open Government Licence - Nova Scotia (attribution required)
- **Pull date:** 2026-07-25
- **Snapshot:** `data/raw/ns_invest-ns-financial-programs_2026-07-25.csv`, 4,553 rows plus header
- **Query:** `https://data.novascotia.ca/resource/6aac-8xtn.csv?$limit=50000&$order=object_id_`
- **Catalog idea:** #34

`$order=object_id_` pins the row order at the endpoint, so re-pulling the same day gives a byte-identical file. The limit sits well above the row count, so the whole table comes back in one request.

The snapshot is committed. The pipeline and its golden output stay reproducible after the live dataset moves, and re-pulling on a later date means re-baselining `expected/deal_book.csv` on purpose.
