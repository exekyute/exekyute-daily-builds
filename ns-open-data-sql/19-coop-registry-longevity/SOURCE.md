# Source

- **Dataset title:** Nova Scotia Co-operatives
- **Portal page:** https://data.novascotia.ca/Business-and-Industry/Nova-Scotia-Co-operatives/k29k-n2db
- **Resource CSV:** https://data.novascotia.ca/resource/k29k-n2db.csv
- **4x4 id:** `k29k-n2db`
- **Licence:** Open Government Licence - Nova Scotia. Attribution: contains information licensed under the Open Government Licence - Nova Scotia.
- **Pull date:** 2026-07-06
- **Snapshot file:** `data/raw/ns_coop-registry_2026-07-06.csv`
- **Snapshot row count:** 369 co-operatives
- **Catalog idea:** #33

## How the snapshot was pulled

The Socrata resource endpoint caps a default response at 1000 rows, so the pull
requested the full table in one call with an explicit limit and a stable sort:

    https://data.novascotia.ca/resource/k29k-n2db.csv?$limit=50000&$order=registry_id

The whole dataset (369 rows) came back inside that single request, so no paging
by `$offset` was needed. The result is committed unchanged as the dated snapshot
above, which is what the SQL reads. The snapshot is pinned so the golden output
in `expected/` reproduces regardless of later changes upstream.

## Notes

- The 4x4 id `k29k-n2db` resolved on the pull date and returned the full table,
  so no id correction was required.
- The portal describes the dataset as the co-operatives registered at the
  Registry of Joint Stock Companies as of June 8, 2026 (the portal's own rows
  were last updated 2026-06-22). The extract carries registered co-ops only;
  there is no status column and no dissolved records. spec.md documents how the
  analysis defines its active rule around that.
- The source column `incorporation_year` is misnamed: it carries a full ISO date
  (for example `1998-10-08`), not a bare year. The SQL casts it to DATE and all
  369 rows parse.
