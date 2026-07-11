# Source

**Dataset:** Municipal Fiscal Statistics Operating Fund
**Portal:** Nova Scotia Open Data (https://data.novascotia.ca), a Socrata portal
**Dataset page:** https://data.novascotia.ca/Municipalities/Municipal-Fiscal-Statistics-Operating-Fund/sbzw-ajrm
**Resource CSV:** https://data.novascotia.ca/resource/sbzw-ajrm.csv
**Socrata 4x4 id:** `sbzw-ajrm`
**Catalog idea:** #1

**Licence:** Open Government Licence - Nova Scotia. Attribution: contains information licensed under the Open Government Licence - Nova Scotia (https://novascotia.ca/opendata/licence.asp).

**Pull date:** 2026-07-05
**Snapshot:** `data/raw/ns_municipal-operating-fund_2026-07-05.csv`
**Snapshot row count:** 555 data rows (plus header), covering fiscal years 2013-14 through 2023-24.

## Pull method

Pulled once from the Socrata CSV endpoint, ordered for a stable snapshot, no app token:

    https://data.novascotia.ca/resource/sbzw-ajrm.csv?$limit=50000&$order=year,region

The default 1000-row cap does not apply because `$limit` is set well above the 555-row total, so a single request returns the whole dataset. The `$order` keeps the pulled bytes stable across pulls. The result is saved verbatim as the dated snapshot above and committed, so the build is pinned to this exact copy.

## Notes

The 4x4 id `sbzw-ajrm` resolved on the pull date and returned the full dataset, so no id correction was needed.
