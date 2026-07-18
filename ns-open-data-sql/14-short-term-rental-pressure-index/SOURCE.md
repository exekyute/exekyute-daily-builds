# Source

- **Dataset title:** Short-Term Accommodations Registry Data
- **Portal page:** https://data.novascotia.ca/d/a796-4rv8
- **Resource CSV:** https://data.novascotia.ca/resource/a796-4rv8.csv
- **4x4 id:** `a796-4rv8`
- **Licence:** Open Government Licence - Nova Scotia. Attribution: contains information licensed under the Open Government Licence - Nova Scotia.
- **Pull date:** 2026-07-06
- **Snapshot file:** `data/raw/ns_str-registry_2026-07-06.csv`
- **Snapshot row count:** 19 data rows (18 census divisions plus the source's own Total row)
- **Catalog idea:** #31

## How the snapshot was pulled

The Socrata resource endpoint caps a default response at 1000 rows, so the pull
requested the full table in one call with an explicit limit and a stable sort:

    https://data.novascotia.ca/resource/a796-4rv8.csv?$limit=50000&$offset=0&$order=census_division

The whole dataset (19 rows) came back inside that single request, so no paging
by `$offset` was needed. The result is committed unchanged as the dated snapshot
above, which is what the SQL reads. The snapshot is pinned so the golden output
in `expected/` reproduces regardless of later changes upstream.

## Notes

- The 4x4 id `a796-4rv8` resolved on the pull date and returned the full table,
  so no id correction was required.
- The dataset is already aggregated by the publisher: one row per Canada
  Mortgage and Housing Corporation (CMHC) census division, with one count
  column per accommodation category (commercial short-term rental, whole-home
  primary residence, traditional tourist accommodation). There is no
  per-registration detail and no date column.
- Registration is required under Nova Scotia's Short-term Rental Registration
  Act for accommodations rented for 28 days or less; the portal describes the
  registry as capturing the supply and location of rental accommodations.
- The source includes a `Total` row alongside the 18 divisions. The pipeline
  excludes it from the regions but verifies it category by category against
  the division sums (`sql/02_transform.sql`); the run aborts on any mismatch.
- The portal reported the rows as last updated 2026-06-08.
