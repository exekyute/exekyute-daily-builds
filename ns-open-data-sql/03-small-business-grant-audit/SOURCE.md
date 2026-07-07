# Source

**Dataset title:** Applicants and Recipients of Small Business Impact Grant and Small Business Reopening and Support Grant

**Portal page:** https://data.novascotia.ca/d/xaty-cfpq

**Resource CSV:** https://data.novascotia.ca/resource/xaty-cfpq.csv

**4x4 id:** `xaty-cfpq` (resolves; no correction needed)

**Licence:** Open Government Licence - Nova Scotia. Attribution to the Province of Nova Scotia. See https://novascotia.ca/opendata/licence.asp.

**Pull date:** 2026-07-05

**Snapshot:** data/raw/ns_small-business-grant_2026-07-05.csv, 4,227 data rows (plus one header row).

**Catalog idea:** #32.

## How the snapshot was pulled

The full table was pulled once from the Socrata CSV endpoint with a raised row limit and a stable order, then saved as the dated snapshot above:

    https://data.novascotia.ca/resource/xaty-cfpq.csv?$limit=50000&$order=:id

The Socrata default returns 1,000 rows, so `$limit` was raised past the row count to pull the table in one call. `$order=:id` fixes the order so the pull is complete and repeatable. No app token is needed for a one-off pull. run.py reads the committed snapshot, not the network, so results do not depend on a live fetch.

## Notes on the data

- Every record in this snapshot received at least one of the two grants, so applicants and recipients coincide here. The pipeline still filters to recipients (received at least one grant) so it stays correct if a future snapshot lists applicants who received nothing.
- All records are dated 2020.
- Organization names repeat across records, and some full rows repeat. There is no unique business identifier in the source, so records are counted as published rather than deduplicated. See spec.md.
