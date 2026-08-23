# Source

- **Dataset:** Surgical Wait Times
- **Portal:** Nova Scotia Open Data, https://data.novascotia.ca
- **Dataset page:** https://data.novascotia.ca/d/wu5w-qxki
- **Socrata resource endpoint:** https://data.novascotia.ca/resource/wu5w-qxki.csv
- **Socrata 4x4 id:** `wu5w-qxki`
- **Licence:** Open Government Licence - Nova Scotia (attribution required)
- **Pull date:** 2026-07-25
- **Snapshot:** `data/raw/ns_surgical-wait-times_2026-07-25.csv`, 6,575 rows plus header
- **Exact query:** `https://data.novascotia.ca/resource/wu5w-qxki.csv?$limit=50000&$order=:id`
- **Catalog idea:** #11

`$order=:id` pins the row order to Socrata's own stable row identifier, so a
re-pull of an unchanged dataset returns the file in the same sequence. The
`$limit=50000` ceiling sits well above the 6,575 rows the dataset holds, so the
pull is a single complete page.

The dataset publishes medians and 90th percentiles directly. This build reads
those published figures and never recomputes a percentile from case-level data,
which the dataset does not carry.

The snapshot is committed so the pipeline and its golden output stay
reproducible after the live dataset moves. Re-pulling on a later date means
re-baselining `expected/wait_time_sla.csv` on purpose.
