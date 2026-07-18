# Spec: short-term-rental pressure index by region

## Purpose

Measure how registered short-term rentals concentrate across Nova Scotia's
census divisions, and how commercial each region's registry mix is. The
headline is the region with the most registrations, its share of the province,
and its commercial share.

## Inputs

- **Dataset:** Short-Term Accommodations Registry Data (`a796-4rv8`), pinned
  snapshot at `data/raw/ns_str-registry_2026-07-06.csv`, 19 data rows
  (18 census divisions plus the source's own Total row). Details in SOURCE.md.
- **Columns used (all of them):**
  - `census_division`: the region key, one row per CMHC census division, for
    example `Halifax CD`. This is the only geography column in the dataset,
    so it is the finest available.
  - `commercial_short_term_rental`: count of registrations in the commercial
    short-term rental category.
  - `whole_home_primary_residence`: count of registrations where the host
    rents out a whole home that is their primary residence.
  - `traditional_tourist_accommodation`: count of registered traditional
    tourist accommodations (the registry's non-STR category).
- **How region is keyed:** on the cleaned `census_division` value alone. The
  dataset is already one row per division, so no aggregation across rows is
  needed to form a region.

## Cleaning and validation rules

Applied in `sql/02_transform.sql`:

1. **Region name.** Trim `census_division` and strip the trailing ` CD`
   suffix, so `Halifax CD` becomes `Halifax`. The cleaned names match Nova
   Scotia's county names, which is also what lets Tableau geocode them
   (bi/README.md).
2. **The Total row.** The source ships a `Total` rollup row alongside the 18
   divisions. It is excluded from the regions, but not ignored: the transform
   compares it, category by category, to the sum of the division rows, and a
   CHECK constraint on the `check_totals` table aborts the whole run if any
   category disagrees. In this snapshot all three match (1,221 commercial,
   1,335 whole-home, 2,384 traditional).
3. **Counts.** The three category columns are cast from text to BIGINT.
4. **Unpivot.** The wide source (one column per category) becomes one row per
   (region, category), the shape the analysis groups over: 18 divisions times
   3 categories, 54 rows.

## The type-classification rule

The registry itself files every registration into exactly one of three named
categories, so the rule reads off the source columns:

- A registration counts as a **short-term rental** when it sits in either
  `commercial_short_term_rental` or `whole_home_primary_residence`. These are
  the two categories the Short-term Rental Registration Act aims at: dedicated
  commercial units and hosts renting their own home.
- A registration counts as **commercial** when it sits in
  `commercial_short_term_rental` specifically. The commercial share of a
  region is therefore commercial over (commercial plus whole-home).
- `traditional_tourist_accommodation` (hotels, motels, inns and similar) is
  **not** a short-term rental. It is excluded from the STR total and the
  shares, but carried through as a context column so the mart still shows the
  full registry picture per region.

## Analysis logic, step by step

Applied in `sql/03_analysis.sql`:

1. **Fold per region** (`per_region`): group the long rows by region and sum
   registrations into four measures: `total_registrations` (the two STR
   categories), `commercial_count`, `whole_home_count`, `traditional_count`.
2. **Provincial total** (`province`): one number, the sum of all region STR
   totals (2,556 in this snapshot), the denominator for every region's share.
3. **Assemble the mart:** one row per region with:
   - `pct_of_province`: region STR total divided by the provincial total,
     times 100, rounded to one decimal place.
   - `rank_by_count`: `dense_rank()` over the STR total, descending. Equal
     totals share a rank; in this snapshot all 18 totals differ, so the ranks
     run 1 through 18.
   - `commercial_share_pct`: commercial count divided by the region's STR
     total, times 100, rounded to one decimal place.
   - `rank_by_commercial_share`: `dense_rank()` over the rounded
     `commercial_share_pct`, descending. Ranking on the rounded value means
     two regions that display the same share also share the same rank.
   - `dominant_type`: the larger of the region's two STR categories. A tie
     goes to the alphabetically first name, `commercial short-term rental`;
     Digby (36 and 36) is the one tie in this snapshot.

## Outputs

`sql/99_export.sql` writes the same SELECT twice, ordered by
`total_registrations` descending then `region` ascending:

- `out/str_pressure_index.csv`: the verification target. `python run.py`
  diffs it against the committed golden copy
  `expected/str_pressure_index.csv` (18 data rows).
- `bi/exports/mart_str_pressure.csv`: the committed copy the Tableau guide
  (bi/README.md) connects to. Identical content, so the dashboard reads
  exactly the numbers the golden diff verified.

Columns are defined in data_dictionary.md.

## Edge cases

- **The Total row** is the big one: kept in, it would double every provincial
  figure and appear as a fake region ranked first. It is excluded by name and
  cross-checked against the division sums (cleaning rule 2).
- **The Digby tie.** Digby has 36 commercial and 36 whole-home registrations,
  the only region where the two STR categories are equal. The written
  tie-break (alphabetical, so commercial) makes `dominant_type` deterministic.
- **Regions with no registrations of a category** would produce a null sum;
  every category count in this snapshot is positive, and the SQL still pins
  the behaviour by summing per category over explicit CASE filters.
- **Division by zero.** `commercial_share_pct` divides by the region's STR
  total, which is never zero in this snapshot (the smallest is Guysborough at
  45); a zero-STR region would surface as a null share and fail the golden
  diff rather than pass silently.

## Determinism

The snapshot is pinned, every result query ends in `ORDER BY`, rounding is
fixed at one decimal place, and both rank columns use `dense_rank()` with
written tie-break rules. `expected/str_pressure_index.csv` was built from a
first verified run; `python run.py` rebuilds `out/` and diffs it against that
golden copy row for row, printing PASS only on an exact match.
