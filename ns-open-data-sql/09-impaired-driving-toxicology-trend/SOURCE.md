# Source

**Dataset title:** Motor Vehicle Driver Deaths

**Portal page:** https://data.novascotia.ca/Public-Safety/Motor-Vehicle-Driver-Deaths/huvt-4vtx

**Resource CSV (Socrata):** https://data.novascotia.ca/resource/huvt-4vtx.csv

**Dataset id (4x4):** `huvt-4vtx`

**Licence:** Open Government Licence - Nova Scotia. Attribution: contains information licensed under the Open Government Licence - Nova Scotia.

**Pull date:** 2026-07-05

**Snapshot:** `data/raw/ns_driver-deaths_2026-07-05.csv`, 312 data rows (13 toxicology categories across a by-year slice, a by-month slice, and a by-sex slice).

**Catalog idea:** #20

## Pull method

One-off request to the Socrata CSV endpoint with a single high row cap, well above the row count:

    https://data.novascotia.ca/resource/huvt-4vtx.csv?$limit=50000

The full table returned in one page (312 rows), so no offset paging was needed. No app token is required for a one-off pull. The `huvt-4vtx` id resolved on the first request and returned data, so no id correction was necessary.

## Notes on the source shape

The published table stacks three cross-tabs in one file. A row belongs to exactly one slice:

- by year: `year` is set, `month` and `sex` are empty
- by month: `month` is set, `year` and `sex` are empty
- by sex: `sex` is set, `year` and `month` are empty

This project uses the by-year and by-month slices. The by-sex slice is not used.
