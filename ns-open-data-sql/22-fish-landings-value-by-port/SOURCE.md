# Source

- **Dataset:** Fish Buyer Purchase Data by Port
- **Portal:** Nova Scotia Open Data, https://data.novascotia.ca
- **Dataset page:** https://data.novascotia.ca/d/j9j2-cpn4
- **Socrata resource endpoint:** https://data.novascotia.ca/resource/j9j2-cpn4.csv
- **Socrata 4x4 id:** `j9j2-cpn4`
- **Licence:** Open Government Licence - Nova Scotia (attribution required)
- **Pull date:** 2026-07-25
- **Snapshot:** `data/raw/ns_fish-landings_2026-07-25.csv`, 2,300 rows plus header
- **SoQL query, exactly as issued:** `?$limit=50000&$order=:id`
- **Full pull URL:** `https://data.novascotia.ca/resource/j9j2-cpn4.csv?$limit=50000&$order=:id`
- **Catalog idea:** #39

The `$order=:id` clause pins the row order to Socrata's internal row id, so re-pulling the same dataset returns the same sequence rather than whatever order the query planner happens to produce. The `$limit` of 50,000 sits well above the 2,300 rows in the dataset, so the pull is a single complete page.

Columns as published: `year`, `port`, `county`, `kgs`, `purchase_total`.

Two things about the shape of this file are worth knowing before reading any figure out of it. It mixes grains: alongside the port rows sit 144 `Total for <County> County` rows, one per county per year, which are county aggregates rather than places. And because the underlying records are buyer purchases, one port in one year can carry several rows, one per reporting buyer, some of them suppressed. spec.md sets out how both are handled.

The snapshot is committed so the pipeline and its golden output stay reproducible after the live dataset moves. Re-pulling on a later date means re-baselining `expected/fish_landings.csv` on purpose.
