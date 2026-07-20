# Source

**Dataset:** Residential SolarHomes Program Installations in Nova Scotia

**Portal page:** https://data.novascotia.ca/d/fsvq-ermw

**Resource CSV:** https://data.novascotia.ca/resource/fsvq-ermw.csv

**Socrata 4x4 id:** `fsvq-ermw`

**Licence:** Open Government Licence - Nova Scotia. Attribution: contains information licensed under the Open Government Licence - Nova Scotia.

**Pull date:** 2026-07-06

**Snapshot:** `data/raw/ns_solarhomes_2026-07-06.csv`, 6,057 data rows (installations from 2018 to 2025).

**Catalog idea:** #26.

## How the snapshot was pulled

The Socrata endpoint caps a default response at 1000 rows, so the pull asks for a large page with a stable sort:

    https://data.novascotia.ca/resource/fsvq-ermw.csv?$limit=50000&$order=year_installed,partial_postal_code,total_dc_capacity_kw

The whole dataset is 6,057 rows, so a single page returns everything. No app token is needed for a one-off pull. The result is saved verbatim as the dated snapshot above and committed as the reproducibility anchor: `run.py` reads that file, never the live endpoint.

## Columns in the source

| Column | Meaning |
| --- | --- |
| `partial_postal_code` | First three characters of the installation's postal code (the forward sortation area) |
| `total_dc_capacity_kw` | Installed DC system capacity in kilowatts |
| `year_installed` | Calendar year the system was installed |

The `fsvq-ermw` id resolved on the pull date and returned the expected columns, so no id correction was needed. The source has a handful of unusable region codes (blank cells, the literal `NS`, and malformed values like `B36`); the cleaning rules in spec.md drop 38 such rows.
