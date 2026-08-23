# Spec: public-housing supply by county

## Purpose

Nova Scotia publishes its public-housing stock as two separate lists, one for families and one for seniors, with different column names for the same idea. This build stacks them into one table and answers a county question against the pair: how many units and how many property records sit in each county, how each county's share of the provincial total compares, and how the two programs split inside a county. Every figure is deterministic and re-derivable from the two committed snapshots.

## Inputs

Two files, both pinned (see SOURCE.md):

- `data/raw/ns_public-housing-families_2026-07-25.csv`, 2,947 rows, Socrata `nxzm-xxps`. Columns used: `uid`, `civic_address`, `community`, `number_of_units`, `housing_authority`, `county`, `municipality`, `x_coordina`, `y_coordina`.
- `data/raw/ns_public-housing-seniors_2026-07-25.csv`, 342 rows, Socrata `2d4m-9e6x`. Columns used: `id`, `name`, `city`, `residential_units`, `housing_authority`, `county`, `municipality`, `x_coordina`, `y_coordina`.

In both files `x_coordina` is longitude and `y_coordina` is latitude, which reverses the reading the column names suggest. Coordinates ride along on the BI mart only; no county figure depends on them.

## The grain, and what a property record is

The two files count different things per row and this is the first thing to get right.

- A families row is one civic address. Most carry one unit; a handful carry up to 95. The file has 2,947 rows holding 3,479 units.
- A seniors row is one named building. Rows carry 2 to 217 units. The file has 342 rows holding 7,772 units.

So the seniors file has an eighth as many rows and more than twice the units. The result reports `properties` (source rows) and `units` (the summed unit column) as two separate columns everywhere, and never mixes them, because a count of rows means something different in each file.

## Named constants (declared in sql/00_schema.sql)

**`const_program_type`.** The program-type universe: `Families` (order 1) and `Seniors` (order 2). This is the right-hand side of the cross join that builds the county grid.

**`const_county_map`.** County spelling substitutions, raw to canonical. It is applied after a mechanical rule that collapses runs of spaces and drops a trailing ` County`. On the committed snapshots both sources spell all eighteen counties identically and the mechanical rule covers everything, so the table is declared with no rows. That is not an assumption: the summary section reports `county_name_substitutions`, which reads 0, so the emptiness is proven by the output rather than asserted here. A later re-pull that splits a county on spelling gets fixed in this one table.

**`const_authority_map`.** Housing-authority spelling substitutions, raw to canonical. One row: `Metro Regional Housing Authority` maps to `Metropolitan Regional Housing Authority`. The seniors file carries one Halifax property under the short spelling and forty-two under the long one; they are the same authority. The summary reports `authority_name_substitutions`, which reads 1. Housing authority rides on the BI mart and not on the county result, so this substitution changes no headline number.

## Normalization (02_transform.sql)

1. **Stack.** Both files go into `stacked_raw` with a `program_type` column carrying the source label. Once stacked, `program_type` is the only thing that says where a row came from, which is what lets every total split back apart.
2. **Units.** `number_of_units` (families) and `residential_units` (seniors) become the single integer column `units` through `TRY_CAST`. A value that will not cast becomes an exclusion class, counted and reported, rather than a silent NULL.
3. **County.** Collapse runs of spaces, drop a trailing ` County`, then apply `const_county_map`.
4. **Housing authority.** Collapse runs of spaces, then apply `const_authority_map`.
5. **Community.** The families file calls it `community`, the seniors file calls it `city`. Same idea, one column on the mart.
6. **Property label.** `civic_address` for families, `name` for seniors. A street address and a building name are not the same kind of label, which is why the column is called `property_label` and not `address`.

## The county universe and the cross-join rule

A coverage gap is only defined against a declared universe. This build declares the universe as **the distinct normalized counties present in the kept rows of either source**, and then cross joins that list against both program types. Eighteen counties times two program types materializes thirty-six cells, so a county carried by one file and not the other appears as a zero unit count rather than as a missing row. A missing row says no answer was produced, while a zero says the answer is none, and those are different claims.

**A county absent from both sources cannot appear in this result, because the build carries no external county reference list.** Nothing outside the two snapshots is consulted to decide which counties exist. On the committed snapshots both files cover all eighteen counties, so no cell is zero and the summary reports `grid_cells_with_zero_units` as 0. The cross join still runs, because the correctness of the answer should not depend on the snapshot happening to be complete.

## Exclusion classes

Nothing is dropped in silence. Every row that does not make it into `housing_long` lands in `excluded_rows` with a reason, and every reason is reported at its count in the `exclusions` section of the result, including when the count is zero:

- `county_blank`: the county is empty after normalization.
- `units_not_a_number`: the source unit value will not cast to an integer.
- `units_not_positive`: the unit value casts but is below 1.

The section closes with `row_accounting_difference`, which is rows read minus rows excluded minus rows kept. It must be 0. On the committed snapshots all three exclusion classes are empty and all 3,289 rows are kept.

## Reconciliation

This is the first multi-source build in the series, so the output carries an explicit reconciliation section rather than trusting the union. It checks two separate things.

**Per-source totals sum to the combined total.** `units_families` (3,479) plus `units_seniors` (7,772) equals `units_combined_total` (11,251), and `units_sources_minus_combined` is 0. The same three-line pattern runs for property counts.

**The county grid re-sums to the same total.** `units_sum_of_county_grid` totals all thirty-six cells and `units_grid_minus_combined` is 0, again with a property-count twin. The two paths are computed independently: the per-source figures come off the stacked table, the grid figures come off the cross-joined cells. Because neither is derived from the other, agreement between them is a check rather than a restatement.

## Analysis steps (03_analysis.sql)

1. `provincial`: units and property records over the kept rows. Every later breakdown re-sums to these two numbers.
2. `cell_totals`: the thirty-six county-by-program cells, zeros materialized by the cross join.
3. `county_ranked`: county totals across both programs, ranked by units with the county name breaking ties.
4. `program_ranked`: program totals, driven off `const_program_type` so a program with no kept rows would still show a zero line.
5. `source_totals`: per-source units and property counts, computed off the stacked table for the reconciliation section.
6. `housing_supply`: six sections stacked into one table.
   - `summary`: provincial totals, universe sizes, grid size, zero-cell count, substitution counts, and the top county with its share.
   - `exclusions`: the row accounting described above.
   - `reconciliation`: the two proofs described above.
   - `program_totals`: two rows, ranked by units.
   - `county_totals`: eighteen rows, ranked by units.
   - `county_program`: thirty-six rows, ordered by county rank then program order.
7. `mart_housing`: one row per kept property record (3,289 rows) for the Tableau face. Its `units` column sums to 11,251, the same provincial total the result proves.

## Outputs

- `out/housing_supply.csv`: the sectioned result, diffed against `expected/housing_supply.csv`.
- `out/mart_housing.csv`, copied to `bi/exports/mart_housing.csv`: the property-level BI mart.

## No population source

This build carries no population data, so it computes no per-capita figure; comparing Halifax to Victoria on units alone is a supply count, not a needs measure.

## Edge cases

- **Program-type universe over observed values.** Program totals are driven off the constant, not off `SELECT DISTINCT program_type`, so an empty source file would produce a zero row instead of vanishing from the section.
- **A county in one file only** produces a zero cell in the grid, a non-zero cell in the other program, and a county total equal to the one non-zero cell. This does not occur on the committed snapshots, and the mechanism exists so that it would be visible if it did.
- **Rounded shares do not sum to exactly 100.** Each share is the exact division rounded to two decimals for display. The eighteen county shares add to 99.98, not 100.00, and that is the rounding, not a missing county. The exact tie is the one proven in the reconciliation section, on units, not on percentages.
- **Accented place names.** Three families rows sit in Petit Étang, Inverness County. The snapshots and the mart are UTF-8; the Tableau import has to be read as UTF-8 or that community name comes through mangled.
- **Housing-authority names cross county lines.** Regional authorities cover several counties, so authority is not a county proxy and is carried on the mart only.

## Determinism

Every result query ends in a total order. The main export orders by section, then by a rank that is already unique inside its section, then by county and program type as final tie-breakers, so row order never depends on scan order or on a sort over a measure. The mart export orders by county, program type, and source id, which is unique. Shares are computed on `DECIMAL(18,6)` and rounded once, at the end, so no floating-point drift reaches the file. Both snapshots are pinned and committed, `expected/housing_supply.csv` was built from a verified run, and a second run reproduces it byte for byte.
