# Source

**Dataset:** Awarded Public Tenders

**Portal page:** https://data.novascotia.ca/Procurement/Awarded-Public-Tenders/m6ps-8j6u

**Resource CSV (Socrata):** https://data.novascotia.ca/resource/m6ps-8j6u.csv

**Resource id (4x4):** `m6ps-8j6u`

**Licence:** Open Government Licence - Nova Scotia. Attribution: contains information licensed under the Open Government Licence - Nova Scotia.

**Pull date:** 2026-07-05

**Snapshot:** `data/raw/ns_awarded-tenders_2026-07-05.csv`, 32,829 rows (plus one header row).

**How it was pulled:** one request to the Socrata CSV endpoint with `$limit=50000` and `$order=:id` (a stable sort on the internal row id), which returned the whole table in one page. No app token is needed for a one-off pull. The 4x4 id resolved on the first try, so no correction was needed.

**Catalog idea:** #4.
