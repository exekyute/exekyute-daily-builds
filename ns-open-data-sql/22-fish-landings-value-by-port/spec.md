# Spec: fish landings value by port

## Purpose

Turn the province's fish buyer purchase file into a ranked view of where landed value actually arrives: which ports take the most money, how concentrated that money is, what a kilogram fetches at each port, and how the total has moved year to year. Every figure is deterministic and re-derivable from the committed snapshot.

## Inputs

One file: `data/raw/ns_fish-landings_2026-07-25.csv`, a pinned snapshot of Socrata dataset `j9j2-cpn4` (see SOURCE.md). Columns: year, port, county, kgs, purchase_total. 2,300 rows covering 2017 through 2024 across 18 counties.

## Named constants (00_schema.sql)

Every threshold and marker is declared once in the `constants` table and referenced by name, never retyped inline.

| Constant | Value | What it controls |
| --- | --- | --- |
| `county_total_prefix` | `Total for ` | Identifies a published county aggregate row, which is a different grain from a port row and is excluded from every port, county, and year sum. |
| `residual_port_label` | `Other` | The province's catch-all bucket for landings in a county not attributed to a named port. Kept in every sum, flagged so it can be told apart from a real port. |
| `top_ports_n` | 25 | How deep the Pareto section runs in the golden file. |
| `min_kgs_for_price` | 0 | Price per kg is computed only where kilograms are strictly greater than this, so the division is never by zero and never by NULL. |

## The suppression rule, word for word

**A row with blank kgs is excluded from kg sums and from price-per-kg, but still counted in dollar sums if purchase_total is present. A row with blank purchase_total is excluded from dollar sums and from price-per-kg, but still counted in kg sums if kgs is present. Neither is ever coerced to zero.**

Suppression is per measure, not per row. A blank is missing information, not a landing of nothing, so it withdraws that one measure from that one sum and leaves the row's other measure alone. Price per kg is the single figure that needs both measures on the same row, so it is built from the `both_present` subset only; `priced_dollars` and `priced_kgs` are therefore carried separately from the headline sums throughout `03_analysis.sql`.

Every row lands in exactly one measure class, and all four are counted and reported in the `row_classes` section of the output. Ranks 1 to 7 of that section partition the snapshot; rank 8 is an overlay, not a class of its own:

| Class | Kilograms | Dollars | Snapshot count |
| --- | --- | --- | --- |
| `both_present` | counted | counted | 693 |
| `kgs_only` | counted | excluded | 0 |
| `dollars_only` | excluded | counted | 0 |
| `both_blank` | excluded | excluded | 1,463 |

In this snapshot the two measures are always suppressed together, so the partial classes count zero and the headline dollar and kilogram sums happen to equal their `both_present` subsets. The rule is still applied per measure rather than as a row filter, because that is the correct reading of a suppressed cell and because a later re-pull can split the classes without the pipeline needing a change. The zero counts are printed rather than hidden, so a re-pull that does split them shows up immediately.

## Grain rule (02_transform.sql)

The source table holds two grains. Rows whose port begins with `county_total_prefix` are the province's own `Total for <County> County` aggregates: 18 counties times 8 years, 144 rows. They are not places, and summing them alongside port rows would roughly double every figure.

They are excluded from every port, county, and year total, counted in `row_classes`, and then used in full in the `county_coverage` section, where each county's published figure is set against the sum of that county's port rows for the same year. One coverage output row per excluded input row, so all 144 stay visible rather than being dropped on the floor.

## Cleaning rules (02_transform.sql)

1. **Types.** `kgs` and `purchase_total` cast to `DECIMAL(18,2)`; `year` casts to `INTEGER`. A value that will not cast fails the run instead of silently becoming NULL. Empty strings become NULL through `NULLIF` before the cast, so a blank stays a blank and never becomes zero. The snapshot has no non-numeric, zero, or negative measures.
2. **Text.** Port and county are trimmed and runs of spaces collapsed.
3. **Wharf qualifier roll-in.** A port written `Base (Qualifier)` is the port `Base` when `Base` also appears as a port name in the same county. In 2019 and 2020, and in those two years only, the province writes the wharf out: `Lower Woods Harbour (Falls Point)`, `Lower Woods Harbour (Forbes Point)`, `Lunenburg (Battery Point)`, `Lunenburg (Fishermens Wharf)`, `Lunenburg (Railway Wharf)`, `Freeport (Fish Point Wharf)`, `Freeport (South Cove)`, `Shag Harbour (Prospect Point)`. In the other six years those same wharves appear as repeated bare rows under the port name. Left alone, one port ranks as several and its value splits across labels for two years out of eight, which understated Lower Woods Harbour by $55,152,594.65 before the rule was added. 16 rows carry a qualifier, worth $62,895,781.98, and the count is reported in the output.

   The condition that `Base` must already exist in the same county is what keeps this structural rather than interpretive: it is a naming inconsistency inside one publisher's own file, not fuzzy matching between similar names. A parenthesised name with no bare counterpart in its county would be left exactly as published, because then the qualifier is the only name that port has. This is the one rule in the build that changes a headline rank, so it is worth reading before trusting the Pareto.
4. **Port identity.** Port names are not unique across the province: `Other` appears in all 18 counties, `Little Harbour` in 6, and `Little River` in 2. Grouping on the bare name would merge separate places, so port identity is the `(county, port)` pair. The display label `port_label` carries the county in brackets only when the name needs disambiguating, which leaves 245 labels short and makes the remaining 26 unambiguous. All 271 labels are distinct, so a BI tool can group on the label alone.
5. **Repeated buyer rows.** The underlying records are buyer purchases, so one port in one year can carry several rows, one per reporting buyer, some suppressed. These are separate buyer records at one place, not duplicated rows, so they sum. Nothing is deduplicated.
6. **Residual bucket.** The `Other` row is a real residual, holding landings the province does not attribute to a named port. Its dollars are real, so it stays in every sum, and `is_named_port` flags it 0 so it can be filtered out or shown apart. Across the snapshot the residual buckets hold $1,225,510,549.04, 14.06 percent of the total, and three of them rank inside the top 25.

## Analysis steps (03_analysis.sql)

1. `grand_total`: records, kilograms, dollars, and price per kg over the port rows. Every later breakdown must tie back to this, dollars and kilograms independently.
2. `port_totals`: records, kilograms, dollars, and price per kg per `(county, port)`, ranked by dollars.
3. `county_totals`: the same per county.
4. `year_totals`: the same per year, with the change in landed value against the previous year taken by `LAG` over the observed year sequence.
5. `county_coverage`: the sum of each county's port rows against the province's published county figure for the same year, with the gap in dollars and percent. A `FULL OUTER JOIN`, so neither side can vanish.
6. `fish_landings`: the seven sections stacked into one table with a fixed sort key.
   - `summary`: grand total, top port, top 10, named ports against residual buckets, and the published county total with the port-level shortfall.
   - `row_classes`: all 2,300 snapshot rows accounted for, by grain and by measure, plus one overlay row counting the wharf qualifiers that were rolled in.
   - `totals_tie`: the port, county, and year breakdowns re-summed; all three rows must equal the grand total in both measures.
   - `top_ports`: the Pareto, `top_ports_n` deep, with share and running cumulative share.
   - `by_county`: all 18 counties.
   - `by_year`: the year trend of landed value.
   - `county_coverage`: all 144 county-year coverage rows.
7. `mart_fish_landings`: one cleaned row per analysed port record (2,156 rows) for the BI face. Its dollar and kilogram sums equal the grand total. The excluded county aggregate rows are deliberately left out, because putting them in would let a report double count the province.

## Outputs

- `out/fish_landings.csv`: the sectioned result, 212 rows, diffed against `expected/fish_landings.csv`.
- `out/mart_fish_landings.csv`, copied to `bi/exports/mart_fish_landings.csv`: the port-level BI mart.

## Edge cases

- **Counties with everything suppressed.** 17 county-year pairs have no port-level dollars at all, so their bottom-up figure is blank and no gap can be computed: Colchester in 7 years, Hants in 7, Antigonish in 3. Those rows still appear in the coverage section carrying the published figure, so the reader sees a county the port view cannot reach rather than a county that looks empty.
- **Hants, 2017, 2020, 2023, and 2024.** The published county row itself is blank in those four years, so both sides of the comparison are missing. The rows are kept and left blank rather than being read as zero.
- **Bottom-up above published.** Yarmouth in 2021 is the one county-year where the sum of the port rows exceeds the province's own county total, by $28,816,542.86, 5.78 percent. That is an inconsistency in the source, not in this pipeline. It is reported as a positive gap and left alone; silently clamping it would hide a real defect in the published data.
- **Ports absent in some years.** A port carries only the years it reported, so `records` in the Pareto runs below 8 for ports like Clark's Harbour. Nothing is padded with zeros.
- **Price per kg at coarse grains.** The county and year figures are total dollars over total kilograms, a weighted average across every species landed there, not a price for any one species. A high figure usually means a lobster or scallop port rather than an expensive port.

## Determinism and the money tie

Dollar and kilogram math runs in `DECIMAL(18,2)` end to end. Percentages are rounded to two decimals and price per kg to four, in both cases after the exact decimal division rather than before.

Every result query ends in a total `ORDER BY` whose last term is a unique tie-breaker: `(county, port)` for the Pareto, `county` for the county view, `year` for the year view, `(county, year)` for coverage. Sorting on a measure alone would leave ties undefined, so no ordering in this build stops at a measure. `NULLS LAST` is stated explicitly wherever a measure can be NULL, so ordering does not depend on an engine default. The BI mart sorts across every one of its exported columns; the rows that remain tied after that are byte-identical repeated suppressed buyer rows, so the file is stable whichever order they land in. Three consecutive runs were diffed byte for byte before the golden was baselined.

The `totals_tie` section makes the tie visible inside the golden file itself: three independent re-summations of $8,716,996,237.83 and of 1,265,656,315.49 kilograms, exact to the cent and to the hundredth of a kilogram.
