# Source

- **Dataset:** Emergency Department Closure Hours by Zone, Facility, and Facility Type
- **Portal:** Nova Scotia Open Data, https://data.novascotia.ca
- **Dataset page:** https://data.novascotia.ca/d/75nx-yut7
- **Socrata resource endpoint:** https://data.novascotia.ca/resource/75nx-yut7.csv
- **Socrata 4x4 id:** `75nx-yut7`
- **Licence:** Open Government Licence - Nova Scotia (attribution required)
- **Pull date:** 2026-07-25
- **Snapshot:** `data/raw/ns_ed-closure-hours_2026-07-25.csv`, 456 rows plus header
- **Exact query:** `https://data.novascotia.ca/resource/75nx-yut7.csv?$limit=50000&$order=:id`

The `$order=:id` clause pins the row order to the portal's internal row id, so
re-pulling on the same data returns the same file byte for byte. The `$limit` of
50,000 is well above the 456 rows the dataset holds, so the single request is the
whole table.

The snapshot is committed so the pipeline and its golden output stay reproducible
after the live dataset moves. Re-pulling on a later date means re-baselining
`expected/ed_closures.csv` on purpose.

## Provenance and the dataset substitution

The catalog idea behind this slot was #13, CTAS Level Breakdown by Zone
(`6kt2-5vdn`). That dataset is unusable through the API: the resource endpoint
reports a row count but returns empty objects for every row, so there is nothing
to aggregate. This build uses `75nx-yut7` instead, which answers the same
question the catalog idea was aimed at, emergency department pressure broken out
by zone, from data that does return.

The README describes this project by the dataset it actually uses and makes no
claim to catalog idea #13.

## Columns as reported

| Column | Notes |
| --- | --- |
| `year` | Fiscal year label, for example `2023-24`. Twelve labels, `2012-13` through `2023-24`. |
| `zone` | Management zone code: `1`, `2`, `3`, `4`, or `IWK`. Reported as text, not a number. |
| `type` | Facility type: `CEC`, `Community`, `Regional`, `Tertiary`, or `UTC`. |
| `site` | Facility name. |
| `temporary` | Temporary (unplanned) closure hours, one decimal place. |
| `scheduled` | Scheduled closure hours, one decimal place. |
| `total` | Total closure hours, one decimal place. |

Two things in the raw file need canonicalizing before the site column groups
correctly, and both are handled by named rules in `sql/00_schema.sql`:

1. Site names are written with a curly apostrophe (U+2019) for `2012-13` through
   `2018-19` and a straight one from `2019-20` on. Three facilities are affected.
2. Roseway Hospital appears as `Roseway` for `2012-13` through `2018-19` and as
   `Roseway Hospital` from `2019-20` on.

Left alone, those four facilities read as eight. After canonicalizing, the
snapshot holds 38 sites, each reporting in all twelve fiscal years.
