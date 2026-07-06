# Source

**Dataset:** Farm Registration by Commodity
**Portal page:** https://data.novascotia.ca/Agriculture-and-Agri-business/Farm-Registration-by-Commodity/kg43-4efs
**Resource CSV:** https://data.novascotia.ca/resource/kg43-4efs.csv
**Socrata 4x4 id:** `kg43-4efs`
**Publisher:** Province of Nova Scotia (category: Agriculture and Agri-business)
**Licence:** Open Government Licence - Nova Scotia (the portal labels it "Nova Scotia Open Government Licence"; terms at http://novascotia.ca/opendata/licence.asp). Attribution: contains information licensed under the Open Government Licence - Nova Scotia.
**Pull date:** 2026-07-05
**Snapshot:** `data/raw/ns_farm-commodity-mix_2026-07-05.csv`, 263 data rows across 10 fiscal years (2015-2016 to 2024-2025)
**Catalog idea:** #43

## Pull method

The Socrata CSV endpoint caps a default response at 1000 rows, so the pull passed an explicit limit and a stable order:

    https://data.novascotia.ca/resource/kg43-4efs.csv?$limit=50000&$order=fiscal_year,commodity

The full table is small (263 rows), so one request returned everything. No app token is needed for a one-off pull. The combined result is committed as the dated snapshot above and is the only input the pipeline reads.

## Notes on the source data

The 4x4 id `kg43-4efs` resolved on the pull date, so no correction was needed.

Two source-side data-quality points are handled in `sql/02_transform.sql` and described in `spec.md`:

- Several commodities are spelled two ways across the years (for example Apple and Apples, Hog and Hogs, Christmas Tree and Christmas Trees). The two spellings never appear in the same fiscal year, and the pipeline folds each pair onto one canonical label.
- Fiscal 2016-2017 lists three commodities twice (Strawberries, Turkey, Vegetable Crops), each with two different totals. The pipeline keeps one row per commodity per fiscal year.
