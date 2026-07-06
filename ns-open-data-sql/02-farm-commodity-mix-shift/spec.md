# Spec: Farm commodity-mix shift

## Purpose

Measure how the commodity mix of Nova Scotia's registered farms shifted across the ten fiscal years in the dataset (2015-2016 to 2024-2025). For each fiscal year, count registered farms by commodity, express each commodity as a share of that year's total, track the year-over-year change in farm counts, and rank which commodities gained or lost the most share of the mix between the first and last fiscal year.

## Inputs

One pinned CSV snapshot: `data/raw/ns_farm-commodity-mix_2026-07-05.csv` (Farm Registration by Commodity, Socrata `kg43-4efs`). Details in SOURCE.md.

Columns used (all three columns the source publishes):

| Column | Meaning |
| --- | --- |
| `commodity` | Commodity label, for example Beef, Apple, Maple. Spellings vary by year. |
| `fiscal_year` | Fiscal year as text, for example `2015-2016`. |
| `total_of_registered_farms` | Registered farms for that commodity in that fiscal year. |

## Cleaning and validation rules

Applied in `sql/02_transform.sql`, in this order:

1. **Trim whitespace** on the commodity label.
2. **Drop null totals.** The source leaves the Turkey 2024-2025 total blank. A blank total is not a zero, so that row is dropped rather than counted as zero. One row is removed this way.
3. **Canonicalize singular and plural labels.** Seven commodities are spelled two ways in different year ranges, and the two spellings never share a fiscal year, so folding each pair onto one label never double counts within a year:

   | Source spellings | Canonical label |
   | --- | --- |
   | Apple, Apples | Apple |
   | Christmas Tree, Christmas Trees | Christmas Tree |
   | Egg, Eggs | Egg |
   | Greenhouse Crop, Greenhouse Crops | Greenhouse Crop |
   | Hog, Hogs | Hog |
   | Strawberry, Strawberries | Strawberry |
   | Vegetable Crop, Vegetable Crops | Vegetable Crop |

4. **Collapse to one row per commodity per fiscal year.** Fiscal 2016-2017 lists three commodities twice, each with two different totals: Strawberries (97 and 30), Turkey (7 and 611), and Vegetable Crops (137 and 407). In each pair the smaller value is the size of the prior year and the larger value is in line with the following year, so the pipeline keeps the larger total with `max`. Grouping by commodity and fiscal year with `max` also passes every non-duplicated row through unchanged.

What is deliberately not merged: commodities that were split or regrouped in the source (for example Blueberries later split into High Bush Blueberries and Low Bush Blueberries, or Chicken and Turkey later combined into Chicken/Turkey). Reconciling those would mean inventing an analytical judgment about which categories are equivalent, so they stay as distinct commodities and are read as entering or leaving the mix.

## Analysis logic, step by step

### Share of the mix (`sql/03_analysis.sql`, table `commodity_mix`)

For each cleaned `(commodity, fiscal_year)` row:

- `farms`: the cleaned registered-farm count.
- `year_total_farms`: the sum of `farms` across all commodities in that fiscal year (built in `sql/02_transform.sql`, table `year_total`).
- `share_pct`: `round(100.0 * farms / year_total_farms, 2)`, the commodity's percent of that year's registered farms.

### Year-over-year change (`commodity_mix`)

Fiscal years are ranked in order in `sql/02_transform.sql` (table `fiscal_year_dim`, a `dense_rank` over the distinct years). For each commodity, `lag` returns the previous listed year's farm count and year rank. The year-over-year columns are filled only when the previous listed year is the immediately adjacent fiscal year (previous rank equals current rank minus one). This avoids a misleading jump when a commodity is absent for one or more years and then reappears.

- `prev_year_farms`: the adjacent prior year's farm count, else empty.
- `yoy_change_farms`: `farms - prev_year_farms`, else empty.
- `yoy_pct`: `round(100.0 * (farms - prev_year_farms) / prev_year_farms, 2)`, else empty. Left empty when the prior year is not adjacent or the prior count is zero.

### Growing versus shrinking (`commodity_growth` and `headline`)

The window's first and last fiscal years are `min` and `max` of the fiscal-year list (2015-2016 and 2024-2025). For each commodity present in **both** endpoint years:

- `first_share_pct`, `last_share_pct`: the commodity's share in each endpoint year.
- `share_change_pp`: `round(last_share_pct - first_share_pct, 2)`, the change in share of the mix, in percentage points.
- `direction`: `growing` if the change is positive, `shrinking` if negative, `flat` if zero.

A commodity present in only one endpoint entered or left the mix inside the window (often because of a relabelling), so it has no comparable pair of endpoint shares and is left out of this ranking.

The `headline` table takes the single largest and smallest `share_change_pp` among named commodities. `Other` is a residual catch-all rather than a commodity, so it is excluded from the ranking (it stays in `commodity_mix`). `run.py` prints the two headline rows.

## Outputs

`out/commodity_mix.csv` (gitignored, regenerated each run) and `expected/commodity_mix.csv` (the committed golden copy). One row per commodity per fiscal year. Columns are defined in `data_dictionary.md`.

Over this snapshot, the headline result is: Beef is the fastest-shrinking named commodity (23.53% down to 22.90%, a 0.63 percentage-point loss of share) and Honey, Bees, Pollination is the fastest-growing (1.61% up to 2.44%, a 0.83 percentage-point gain).

## Edge cases

- **Null total:** the one blank total (Turkey 2024-2025) is dropped, not zeroed.
- **Duplicate rows:** the three doubled 2016-2017 rows collapse to their larger value.
- **Spelling variants:** the seven singular and plural pairs fold to one label each.
- **Gaps in a commodity's history:** year-over-year is computed only across adjacent years, so a reappearance after a gap does not produce a false jump.
- **Volatile counts:** the published farm counts swing sharply from year to year (a commodity can hold a large share in one year and a small share the next). The share and year-over-year columns report the published figures as they stand; the headline compares the two endpoint years only, so the mid-window swings do not drive it.

## Determinism

The snapshot is pinned and committed. Every result query ends in `ORDER BY`, and the export in `sql/99_export.sql` orders by commodity then fiscal year, so `out/commodity_mix.csv` is byte-for-byte identical on every run. All rounding is fixed to two decimals. `expected/commodity_mix.csv` was built from a first verified run; `python run.py` regenerates the output and confirms it matches row for row.
