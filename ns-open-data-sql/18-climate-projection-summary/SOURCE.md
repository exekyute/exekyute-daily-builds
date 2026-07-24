# Source

**Dataset title:** NS Climate Change Projections (CMIP5)

**Portal page:** https://data.novascotia.ca/d/r7d9-j7wx

**Resource CSV:** https://data.novascotia.ca/resource/r7d9-j7wx.csv

**4x4 id:** `r7d9-j7wx` (resolves; no correction needed)

**Licence:** Open Government Licence - Nova Scotia. Attribution to the Province of Nova Scotia. See https://novascotia.ca/opendata/licence.asp.

**Pull date:** 2026-07-06

**Snapshot:** data/raw/ns_climate-projections_2026-07-06.csv, 1,672 data rows (plus one header row).

**Catalog idea:** #27.

## How the snapshot was pulled

The full table was pulled once from the Socrata CSV endpoint with a raised row limit and a stable order, then saved as the dated snapshot above:

    https://data.novascotia.ca/resource/r7d9-j7wx.csv?$limit=50000&$order=:id

The Socrata default returns 1,000 rows, so `$limit` was raised past the row count to pull the table in one call. `$order=:id` fixes the order so the pull is complete and repeatable. At 1,672 rows the dataset sits far under the 200,000-row size guard, so no SoQL narrowing was needed and the snapshot carries every column and row as published. No app token is needed for a one-off pull. build.py reads the committed snapshot, not the network, so results do not depend on a live fetch.

## Notes on the data

- The table is wide: one row per (region, variable), 1,672 rows = 19 regions times 88 variables. Regions are the province-wide `Nova Scotia` row plus the 18 counties (census divisions).
- The 24 value columns are named `rcp{45,85}_p{05,50,95}_{2010,2045,2065,2095}`: scenario (RCP4.5 low emissions, RCP8.5 high emissions), percentile of the model range (5th, 50th, 95th), and time period. Per the dataset's column descriptions, `2010` covers 1981-2010, `2045` covers 2015-2045, `2065` covers 2035-2065, and `2095` covers 2065-2095.
- The `2010` columns are the dataset's baseline period, and each scenario carries its own baseline value; the two differ slightly for the same region, so the model subtracts each scenario's own baseline.
- The model uses one variable, `tgmean_annual` (Average Daily Mean Temperature, annual, degrees C), at the p50 percentile, for the `2010`, `2045`, and `2095` periods. Everything else stays in the snapshot untouched.
- The portal carried the title above on the pull date. It has since retitled the resource "NS Climate Change Projections (outdated: CMIP5/2022)" and marked the description legacy, alongside the same treatment for its CMIP3 and sea-level resources. The 4x4 id still resolves and still serves this data, and the pinned snapshot is unaffected, so the build reproduces regardless.
