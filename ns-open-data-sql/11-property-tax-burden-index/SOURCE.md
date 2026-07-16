# Data source

- **Dataset:** Municipal Property Tax Rates
- **Portal:** Nova Scotia Open Data, https://data.novascotia.ca
- **Dataset page:** https://data.novascotia.ca/Municipalities/Municipal-Property-Tax-Rates/ure8-3w7m
- **Resource (Socrata CSV):** https://data.novascotia.ca/resource/ure8-3w7m.csv
- **4x4 id:** `ure8-3w7m`
- **Licence:** Open Government Licence - Nova Scotia (attribution required)
- **Pulled:** 2026-07-06, paged with `$limit`/`$offset` and a stable `$order` until exhausted
- **Snapshot:** `data/raw/ns_property-tax-rates_2026-07-06.csv`, 1,112 data rows
- **Catalog:** idea #2 in the series catalog

The snapshot is committed so the pipeline and its golden output stay reproducible
even if the live dataset changes. Columns as published: `area`, `area_type`,
`year` (fiscal label like `2025/2026`), `residential`, `commercial`. The two rate
columns are general tax rates in dollars per $100 of assessed value.
