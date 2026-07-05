# Source

**Dataset:** Convictions for Select MVA Offences

**Portal page:** https://data.novascotia.ca/Public-Safety/Convictions-for-Select-MVA-Offences/uvv7-hnbr

**Resource CSV:** https://data.novascotia.ca/resource/uvv7-hnbr.csv

**Socrata 4x4 id:** `uvv7-hnbr`

**Licence:** Open Government Licence - Nova Scotia. Attribution: contains information licensed under the Open Government Licence - Nova Scotia.

**Pull date:** 2026-07-05

**Snapshot:** `data/raw/ns_mva-conviction-trend_2026-07-05.csv`, 28 rows (2 offences over the years 2011 to 2024).

**Catalog idea:** #21.

## How the snapshot was pulled

The Socrata endpoint caps a default response at 1000 rows, so the pull asks for a large page with a stable sort:

    https://data.novascotia.ca/resource/uvv7-hnbr.csv?$limit=50000&$order=offence_statute,year_convicted

The whole dataset is 28 rows, so a single page returns everything. No app token is needed for a one-off pull. The result is saved verbatim as the dated snapshot above and committed as the reproducibility anchor: `run.py` reads that file, never the live endpoint.

## Columns in the source

| Column | Meaning |
| --- | --- |
| `offence_statute` | Motor Vehicle Act section code for the offence |
| `description` | Plain-language description of the offence |
| `year_convicted` | Calendar year the convictions were recorded |
| `convictions` | Number of convictions for that offence in that year |

The `uvv7-hnbr` id resolved on the pull date and returned the expected columns, so no id correction was needed.
