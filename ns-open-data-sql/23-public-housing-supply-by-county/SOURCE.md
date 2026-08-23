# Source

This build reads two datasets. Both come from the same portal under the same licence, and both are pinned as committed snapshots.

## Dataset 1: families

- **Dataset:** Public Housing Units - Nova Scotia Families
- **Portal:** Nova Scotia Open Data, https://data.novascotia.ca
- **Dataset page:** https://data.novascotia.ca/d/nxzm-xxps
- **Socrata resource endpoint:** https://data.novascotia.ca/resource/nxzm-xxps.csv
- **Socrata 4x4 id:** `nxzm-xxps`
- **Licence:** Open Government Licence - Nova Scotia (attribution required)
- **Pull date:** 2026-07-25
- **Snapshot:** `data/raw/ns_public-housing-families_2026-07-25.csv`, 2,947 rows plus header
- **Query:** `?$limit=50000&$offset=0&$order=:id`

## Dataset 2: seniors

- **Dataset:** Public Housing Units - Nova Scotia Seniors
- **Portal:** Nova Scotia Open Data, https://data.novascotia.ca
- **Dataset page:** https://data.novascotia.ca/d/2d4m-9e6x
- **Socrata resource endpoint:** https://data.novascotia.ca/resource/2d4m-9e6x.csv
- **Socrata 4x4 id:** `2d4m-9e6x`
- **Licence:** Open Government Licence - Nova Scotia (attribution required)
- **Pull date:** 2026-07-25
- **Snapshot:** `data/raw/ns_public-housing-seniors_2026-07-25.csv`, 342 rows plus header
- **Query:** `?$limit=50000&$offset=0&$order=:id`

Catalog idea: #37.

## Dataset substitution

The catalog entry for this idea named `2it9-2f4a`, "Public Housing Units - Nova Scotia Seniors Locations", as the seniors source. That id is live and reports a row count, but it returns no field values:

- `https://data.novascotia.ca/resource/2it9-2f4a.json?$select=count(1)` returns `[{"count_1":"342"}]`
- `https://data.novascotia.ca/resource/2it9-2f4a.json?$limit=2` returns `[{},{}]`
- `https://data.novascotia.ca/resource/2it9-2f4a.csv?$limit=2` returns an empty body

Checked on the pull date. Because the records come back empty through the API, `2it9-2f4a` cannot be read into this pipeline. The build uses `2d4m-9e6x`, "Public Housing Units - Nova Scotia Seniors", which carries the same 342 records with their fields populated.

## Reproducing the pull

Both snapshots are committed so the pipeline and its golden output stay reproducible after the live datasets move. Re-pulling on a later date means re-baselining `expected/housing_supply.csv` on purpose.

The `$order=:id` clause pins row order to the Socrata row identifier, so a re-pull of unchanged data returns the same file rather than an arbitrary permutation. The `$limit=50000` covers both datasets in a single page; neither is close to that ceiling.
