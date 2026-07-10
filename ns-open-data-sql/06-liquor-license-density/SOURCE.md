# Source

- **Dataset title:** Permanent Liquor Licenses
- **Portal page:** https://data.novascotia.ca/Business-and-Industry/Permanent-Liquor-Licenses/en23-iwca
- **Resource CSV:** https://data.novascotia.ca/resource/en23-iwca.csv
- **4x4 id:** `en23-iwca`
- **Licence:** Open Government Licence - Nova Scotia. Attribution: contains information licensed under the Open Government Licence - Nova Scotia.
- **Pull date:** 2026-07-05
- **Snapshot file:** `data/raw/ns_liquor-licenses_2026-07-05.csv`
- **Snapshot row count:** 2474 licenses
- **Catalog idea:** #29

## How the snapshot was pulled

The Socrata resource endpoint caps a default response at 1000 rows, so the pull
requested the full table in one call with an explicit limit and a stable sort:

    https://data.novascotia.ca/resource/en23-iwca.csv?$limit=50000&$order=license_number

The whole dataset (2474 rows) came back inside that single request, so no paging
by `$offset` was needed. The result is committed unchanged as the dated snapshot
above, which is what the SQL reads. The snapshot is pinned so the golden output
in `expected/` reproduces regardless of later changes upstream.

## Notes

- The 4x4 id `en23-iwca` resolved on the pull date and returned the full table,
  so no id correction was required.
- The source `location` column carries a geocoded address block with embedded
  line breaks. It is loaded as text and is not used in the analysis, which keys
  community off `city_town`.
