# Source

- **Dataset:** Long-term Care and Residential Care Facilities
- **Portal:** Nova Scotia Open Data, https://data.novascotia.ca
- **Dataset page:** https://data.novascotia.ca/d/x76a-axw2
- **Socrata resource endpoint:** https://data.novascotia.ca/resource/x76a-axw2.csv
- **Socrata 4x4 id:** `x76a-axw2`
- **Licence:** Open Government Licence - Nova Scotia (attribution required)
- **Pull date:** 2026-07-25
- **Snapshot:** `data/raw/ns_ltc-facilities_2026-07-25.csv`, 145 rows plus header
- **Pull query:** `https://data.novascotia.ca/resource/x76a-axw2.csv?$limit=50000&$order=facility_id`
- **Catalog idea:** #14

`$order=facility_id` pins the row order, and `facility_id` is unique across the 145 rows, so a re-pull of the same data lands in the same sequence. The limit sits far above the row count, so one request returns the whole table.

The snapshot is committed so the pipeline and its golden output stay reproducible after the live dataset moves. Re-pulling on a later date means re-baselining `expected/ltc_bed_supply.csv` on purpose.

The `location` column carries embedded newlines inside its quotes, so the file has more physical lines than records and any reader has to honour CSV quoting. And `x_coordinate` is longitude while `y_coordinate` is latitude, which is the reverse of what the names suggest.
