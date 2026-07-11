# Spec

## Purpose

Rank Nova Scotia municipalities by operating surplus in each fiscal year, track each municipality's surplus over time, and surface the headline: the largest surplus and the largest deficit in the latest year on file.

## Inputs

- Dataset: Municipal Fiscal Statistics Operating Fund, Socrata 4x4 `sbzw-ajrm` (see SOURCE.md).
- Pinned snapshot: `data/raw/ns_municipal-operating-fund_2026-07-05.csv`, 555 data rows, fiscal years 2013-14 through 2023-24.
- Columns used:
  - `region` and `region_type`: together they identify a municipality.
  - `year`: fiscal year label, for example `2023-24`.
  - `total_revenues`: total operating revenue for the year, whole dollars.
  - `total_expenditures`: total operating expenditure for the year, whole dollars.

The dataset also carries its own `operating_surplus_deficit_before_financing_and_transfers` column. This build does not use it as the surplus (see the money note below); it is only a cross-check.

## Cleaning and validation rules

1. Read every source column as text on load, then cast the two money columns explicitly, so a blank field arrives as NULL rather than a silent zero.
2. A municipality is the pair (region, region_type). The names Antigonish, Lunenburg, Yarmouth, Digby, and Shelburne each belong to both a Town and a separate Rural Municipality; treating them as one government would double-count and corrupt the year-over-year series. With region_type included, (region, region_type, year) is unique across the snapshot.
3. Drop any row where `total_revenues` or `total_expenditures` is missing, because a surplus cannot be computed from it. One row is dropped: Mahone Bay (Town) 2023-24, which has both totals blank. This leaves 554 rows.

## Analysis logic, step by step

1. Surplus (02_transform.sql): `operating_surplus = total_revenues - total_expenditures`, each cast to DECIMAL(18,2) so the subtraction is exact to the cent.
2. Rank within year (03_analysis.sql): `surplus_rank_in_year = RANK() OVER (PARTITION BY year ORDER BY operating_surplus DESC)`, so 1 is the largest surplus that year. `deficit_rank_in_year = RANK() OVER (PARTITION BY year ORDER BY operating_surplus ASC)`, so 1 is the largest deficit (most negative surplus). RANK is used so any tie shares a place.
3. Year-over-year (03_analysis.sql): `prior_year_surplus = LAG(operating_surplus) OVER (PARTITION BY region, region_type ORDER BY year)` and `yoy_surplus_change = operating_surplus - prior_year_surplus`. The fiscal-year label sorts chronologically as text, so it is the ordering key. Both are NULL in a municipality's first observed year.
4. Multi-year trend (03_analysis.sql): `years_observed = COUNT(*) OVER (PARTITION BY region, region_type)` and `mean_surplus = ROUND(AVG(operating_surplus) OVER (PARTITION BY region, region_type), 2)`, a per-municipality baseline repeated on each of its rows.
5. Export (99_export.sql): COPY the columns to `out/surplus_league.csv`, ordered `year DESC, operating_surplus DESC, region ASC, region_type ASC`.

## Outputs

`out/surplus_league.csv`, one row per municipality per fiscal year, 554 rows. Columns are defined in data_dictionary.md. `expected/surplus_league.csv` is the golden copy built from a first verified run.

## Edge cases

- Missing totals: the single blank-total row (Mahone Bay Town 2023-24) is excluded, as above.
- Partial history: some municipalities appear in only a few years. Springhill (Town), for example, appears in 2013-14 and 2014-15 only (it was dissolved into Cumberland), so `years_observed = 2` and it has one NULL year-over-year change. This is expected, not an error.
- First observed year: `prior_year_surplus` and `yoy_surplus_change` are empty for the earliest year each municipality appears in (56 rows, one per municipality).
- The number of ranked municipalities changes by year (54 down to 48), so `municipalities_in_year` records the field size behind each rank.

## Determinism and the money tie

- The snapshot is pinned and committed, so the input never shifts under the build.
- All money is DECIMAL(18,2), kept to two decimals. The source values are whole dollars, so surplus, revenue, and expenditure tie exactly and cents read as `.00`.
- Surplus is derived as revenue minus expenditure, so it ties to those two figures by construction on every row. The dataset's own operating-surplus column is populated for only 395 of the 555 rows and, in 5 of those, disagrees with revenue minus expenditure by exactly one dollar (independent rounding at the source). Deriving the figure from the totals sidesteps that and keeps the arithmetic internally consistent.
- The export ends in a fixed ORDER BY down to (region, region_type), so the CSV is byte-for-byte reproducible. `run.py` rebuilds it and diffs it against the golden copy row for row, printing PASS on a match.
