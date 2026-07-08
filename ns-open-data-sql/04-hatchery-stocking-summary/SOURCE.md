# Source

- **Dataset title:** Fish Hatchery Stocking Records
- **Portal page:** https://data.novascotia.ca/Fishing-and-Aquaculture/Fish-Hatchery-Stocking-Records/8e4a-m6fw
- **Resource CSV:** https://data.novascotia.ca/resource/8e4a-m6fw.csv
- **4x4 id:** `8e4a-m6fw` (resolves; no correction needed)
- **Licence:** Open Government Licence - Nova Scotia. Attribution required; contains information licensed under the Open Government Licence - Nova Scotia.
- **Pull date:** 2026-07-05
- **Snapshot:** `data/raw/ns_hatchery-stocking_2026-07-05.csv`
- **Snapshot row count:** 15,000 (plus one header row)
- **Catalog idea:** #40

## How the snapshot was pulled

The Socrata export caps a plain request at 1,000 rows, so the pull asked for the
whole table in one call with a raised limit and a stable order:

    https://data.novascotia.ca/resource/8e4a-m6fw.csv?$limit=50000&$order=:id

`:id` is Socrata's internal row identifier, which gives a stable order across
requests. The response held 15,000 rows, well under the 50,000 ceiling, so the
one call returned the full dataset. That file is committed under `data/raw/` and
is the only input the project reads.
