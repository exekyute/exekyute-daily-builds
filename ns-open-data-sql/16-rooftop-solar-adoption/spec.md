# Spec: rooftop solar adoption by region

## Purpose

Measure residential solar adoption across Nova Scotia from the SolarHomes rebate
program's installation records: how many systems went in, how much capacity they add,
where they cluster, and how the curve grew year over year. One SQL pipeline produces a
provincial year summary (the golden output), an FSA-by-year mart for BI tools, and the
embedded dataset behind the browser dashboard.

## Inputs

- `data/raw/ns_solarhomes_2026-07-06.csv`: pinned snapshot of the Socrata resource
  `fsvq-ermw` (Residential SolarHomes Program Installations), pulled 2026-07-06 with a
  stable `$order` so re-pulls page deterministically. 6,057 data rows across three
  columns: `partial_postal_code`, `total_dc_capacity_kw`, `year_installed`. Details in
  SOURCE.md.

## Cleaning rules (02_transform)

Applied in this order to the raw rows:

1. FSA: `partial_postal_code`, uppercased and trimmed. Keep only values matching
   letter-digit-letter (`^[A-Z][0-9][A-Z]$`). Nova Scotia FSAs start with B, but the
   rule does not enforce that; it only enforces the postal pattern. This drops blank
   cells, the literal `NS`, and malformed codes such as `B36` and `BOK` (letter O).
2. Year: `year_installed` must cast to an integer. Rows that do not cast are dropped.
3. System size: `total_dc_capacity_kw` must cast to a number greater than zero.
4. Rows failing any rule are excluded from `solar_clean` and never counted. On the
   pinned snapshot the rules drop 38 of 6,057 rows (all on rule 1), leaving 6,019
   installs; the drop is visible as the difference between the raw row count in
   SOURCE.md and the total installs in the golden output.

## Analysis, step by step (03_analysis)

1. `fsa_year`: group `solar_clean` by FSA and year; `installs` is a row count,
   `installed_kw` is `ROUND(SUM(kw), 2)`. This is the base grain; everything else sums
   these rows so all outputs agree with each other.
2. `province_year`: sum `fsa_year` by year, then add window columns: cumulative
   installs and cumulative kW (`SUM ... OVER (ORDER BY year)`), year-over-year install
   change (`LAG`), and the change as a percent of the prior year (1 decimal place,
   NULL-safe on a zero prior year).
3. `fsa_totals`: sum `fsa_year` by FSA; add each FSA's share of provincial installs
   (percent, 1 decimal place) and dense rank positions by installs and by kW.

## Outputs (99_export)

- `out/solar_adoption.csv`: `province_year` ordered by year. Golden copy in
  `expected/solar_adoption.csv`.
- `out/mart_solar.csv`: `fsa_year` ordered by FSA then year, copied by `run.py` to
  `bi/exports/mart_solar.csv` for Tableau and re-emitted as `dashboard/data.js`.

## Dashboard re-derivation

`dashboard/dashboard.js` starts from the raw `DATA` rows (the mart, one row per FSA and
year) and recomputes every figure client-side: provincial totals, per-year sums, the
cumulative curve, top FSAs by installs and kW, and the year detail. Nothing is
hardcoded. The derived headline must equal the golden values exactly:

- Total installations: **6,019** (equals `cumulative_installs` in the last golden row,
  year 2025).
- Total installed capacity: **62,489.47 kW** (equals `cumulative_kw` in the last golden
  row, 2 decimal places).
- Leading region: **B0J** (398 installs, 6.6% of the province, 4,163.24 kW), rank 1 by
  installs in `fsa_totals`. The next two are B3Z (317) and B0P (312).

kW figures are rounded to 2 decimal places at the `fsa_year` grain, and every
downstream total (SQL and JavaScript alike) sums those same rounded values, so the two
sides cannot drift through floating-point noise.

## Edge cases

- Missing or malformed postal code: row dropped by rule 1; it cannot be assigned to a
  region, and a province-only bucket would double-count against the FSA views.
- Missing date or size: dropped by rules 2 and 3.
- Edge years: 2018 is the program's launch year and covers only part of a year of
  activity, and the latest year can trail real activity by however far the portal's
  updates lag. The pipeline reports both as-is; the year-over-year columns make the
  edge years easy to spot rather than hiding them.
- Zero prior year in the percent column: guarded with `NULLIF`, yields an empty cell.
- First observed year: `yoy_install_change` and `yoy_install_pct` are empty by
  definition.

## Determinism

The snapshot is pinned and committed; the pipeline reads only that file. Every exported
query ends in ORDER BY, kW sums are rounded to fixed precision, and `run.py` contains
no logic beyond execute, copy, re-emit, and diff. Re-running `python run.py` on any
machine reproduces `expected/solar_adoption.csv` byte for byte.
