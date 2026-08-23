# Spec: protected-areas land accounting

## Purpose

Account for every hectare in Nova Scotia's protected areas layer: how much land
is protected, under which designation, by which authority, on whose land, and
how far along the legal process each parcel is. Then measure how concentrated
that land is, because a small number of wilderness areas carry most of it. Every
figure is deterministic and re-derivable from the committed snapshot.

## Inputs

One file: `data/raw/ns_protected-areas_2026-07-25.csv`, a pinned snapshot of
Socrata dataset `ticv-5du5` (see SOURCE.md). 1,161 rows, twelve attribute
columns.

## Geometry exclusion

The source layer is a polygon layer. Its `the_geom` column holds a MULTIPOLYGON
string per row, thousands of coordinates long, and it is excluded at the pull by
naming the twelve attribute columns in `$select`. It has no landing column in
`sql/00_schema.sql` either.

**This is a geometry-bearing dataset aggregated tabularly only: no spatial
joins, no spatial extension, no geometry parsed at any point.** Area comes from
the province's own published `ha_gis` field, which is the value the province
reports against, rather than from anything this pipeline measures off a polygon.

## Cleaning rules (02_transform.sql)

1. **Hectares.** `ha_gis` is cast to `DECIMAL(18,8)` and rounded once, at the
   record level, to two decimals. A hard `CAST` is used, not `TRY_CAST`: a
   hectare value that will not parse fails the run rather than becoming a NULL
   that quietly shrinks the total. The snapshot has no blank, non-numeric, zero,
   or negative hectare values.

   Rounding once at the record level is the reason every breakdown re-sums to
   the published total exactly. The trade is six cents of a hectare: the
   unrounded sum is 743,084.05 ha, the record-rounded total is 743,084.11 ha, a
   difference of 0.06 ha. Both numbers are in the coverage section
   (`unrounded_total_hectares`, `record_rounding_difference_hectares`), so the
   gap is reported rather than absorbed.

2. **Text.** Every label is trimmed and runs of whitespace are collapsed to one
   space (`squish`). The snapshot needed neither. Running the rule anyway is
   what proves that.

3. **Organization names** (`owner`, `authority`) get two further rules
   (`norm_org`), applied over the whole string so compound labels are covered:
   a leading `The ` is stripped, and `Nova Scotia Environment and Climate
   Change` is rewritten to `NS Environment and Climate Change`. Both spellings
   of the department appear in the same snapshot for the same body, so this is a
   spelling fix, not a merge of two organizations. It touches 55 authority
   labels and 0 owner labels, both counted in the coverage section.

   Nothing else is folded. `Nature Conservancy of Canada and private owners` and
   `Nature Conservancy of Canada` stay separate, because collapsing a joint
   holding into a sole holding would be an interpretive judgment, not a spelling
   fix.

4. **Designation.** `protect1` is used verbatim. Compound labels such as
   `Wilderness Area, Conservation Easement` stay whole rather than splitting into
   two designations, so no hectare is ever counted twice. Thirteen labels result.

5. **Designation year.** `designation_year` is derived from `stat_date`, which
   the source publishes as a plain year number, via
   `TRY_CAST(nullif(squish(stat_date), '') AS INTEGER)`. `TRY_CAST` here on
   purpose: a missing designation year is a coverage fact to report, not a
   reason to fail the run. Records without one are excluded from any year series
   and counted by name.

## The designation year in this snapshot, and what it costs

**`stat_date` is empty in all 1,161 rows of the current publication.** The
server agrees: `$select=count(stat_date)` returns 0. The layer's older
metadata shows the column populated with years such as 1998, so the province
published it once and the current version does not carry it.

So `designation_year` is NULL for every record, and the coverage section says so
in both units:

| Coverage row | Value |
| --- | --- |
| `records_missing_designation_year` | 1,161 |
| `hectares_missing_designation_year` | 743,084.11 |
| `records_in_year_series` | 0 |
| `hectares_in_year_series` | 0.00 |

The general rule holds: a cumulative line drawn over `designation_year` ends
below the total-hectares figure by exactly the missing-date hectares, and that
shortfall is a data-coverage fact rather than a defect. In this snapshot the
shortfall is the whole total. **A cumulative-growth-over-time chart would be
empty, so this build does not draw one, and the BI guide says so plainly instead
of shipping a blank visual.**

Two things follow, both deliberate:

- `designation_year` stays in the mart and in the pipeline. It is an integer
  column that is currently empty end to end. If the province refills
  `stat_date`, re-pulling and re-baselining produces a working year series with
  no code change, and the running-total measure in the BI guide transfers to it
  as written.
- The cumulative measure the build actually ships runs over a different ordered
  axis: `record_rank`, records sorted largest hectares first. That gives a
  concentration curve, which answers how few parcels hold most of the protected
  land. It is a documented substitution for the time axis, and it runs on the
  same integer-index pattern the year axis would have used.

## Named constants

| Constant | Value | Where it comes from |
| --- | --- | --- |
| `ns_land_area_ha` | 5,333,800 | Nova Scotia's land area, 53,338 km2, times 100 ha/km2. Statistics Canada, "Land and freshwater area, by province and territory" (Canada Year Book table 15.6), https://www150.statcan.gc.ca/n1/pub/11-402-x/2012000/chap/geo/tbl/tbl06-eng.htm. Land only; the province's 1,946 km2 of freshwater is deliberately out of the denominator. |
| `hectare_rounding_dp` | 2 | Decimals kept when hectares are rounded once at the record level (rule 1). |
| `concentration_top_n` | 25 | How many records the concentration curve lists row by row. |
| `half_share` | 0.50 | Milestone on the concentration curve. |
| `ninety_share` | 0.90 | Milestone on the concentration curve. |
| `designated_status` | `Designated` | The `status` label meaning protection is in law rather than pending. |

A note on the land-area denominator: Statistics Canada also publishes a census
land area for Nova Scotia (52,824.71 km2 in the 2021 Census geography), which is
measured on a different basis. Using it would move the share of provincial land
from 13.93 percent to 14.07 percent. The constant is named in SQL and cited here
so the reader can see which basis produced the number, and swap it in one place.

## Analysis steps (03_analysis.sql)

1. `grand`: total hectares, record count, and the unrounded total for the
   rounding reconciliation. Every later breakdown has to re-sum to
   `total_hectares`.
2. `by_designation`, `by_authority`, `by_owner`, `by_status`: hectares and
   record counts per label.
3. `cumulative_records`: records ranked by hectares descending with a running
   hectare total beside each one.
4. `concentration_milestones`: how many records it takes to cover half, then
   ninety percent, of all protected hectares, and what the top 10 hold.
5. `protected_areas`: the eight sections stacked into one table with a fixed
   sort key:
   - `summary`: total hectares, record and label counts, the provincial land
     share, the largest record, top-10 hectares, the two concentration
     milestones, and hectares that are legally designated.
   - `coverage`: rows in, rows out, rows dropped (zero), zero-or-negative
     hectare records, repeated area names, labels rewritten by the organization
     rules, the designation-year gap in records and hectares, and the rounding
     reconciliation.
   - `totals_tie`: the four breakdowns and the concentration curve re-summed;
     all five rows must equal the grand total exactly.
   - `by_designation`, `by_authority`, `by_owner`, `by_status`: hectares,
     records, and share of the provincial protected total.
   - `concentration`: the top 25 records with running hectares and running
     share.
6. `mart_protected`: one row per source record (1,161 rows) with the ordered
   index attached, exported for the Power BI face. Its hectare sum equals the
   grand total.

## Outputs

- `out/protected_areas.csv`: the sectioned result, diffed against
  `expected/protected_areas.csv`.
- `out/mart_protected.csv`, copied to `bi/exports/mart_protected.csv`: the
  record-level BI mart.

## Edge cases

- **Area names repeat.** 1,161 records cover 436 distinct area names; 914
  records share a name with at least one other record. Tobeatic Wilderness Area
  alone appears as several records, and two of them rank in the top 10 by
  hectares. These are multipart polygons published as separate rows, not
  duplicate data, so nothing is merged. The word used throughout is *record*,
  never *site*, and `distinct_area_names` is reported next to the record count so
  the two are never confused.
- **Compound designations** stay whole (rule 4), so
  `Wilderness Area, Conservation Easement` is its own label with its own 1,647.96
  ha, and none of it is also counted under `Wilderness Area`.
- **Compound authorities** stay whole for the same reason. That is why 25
  authority labels cover fewer than 25 organizations.
- **`Considered protected`** covers 794 records but only 22,241.80 ha, three
  percent of the land. Land-trust parcels are numerous and small. Record counts
  and hectares point in opposite directions here, which is why both are reported
  in every breakdown.
- **Ties in rankings** break on the label itself in the grouped sections and on
  `objectid` at the record level, so rank order never depends on scan order.

## Determinism

Hectare math runs in `DECIMAL` end to end; percentages are display values
rounded to two decimals after the exact division. Every result query ends in a
total `ORDER BY` whose final term is unique: the group label in the four
breakdowns, `record_rank` on the concentration curve and the mart, and
`section_order, rank` on the export. Two consecutive runs produce byte-identical
files. The `totals_tie` section makes the tie visible inside the golden file
itself: five independent re-summations of the same 743,084.11 hectares.
