# Data dictionary

Definitions for the two generated outputs. Column names are lowercase with
underscores in both files.

## out/solar_adoption.csv (golden: expected/solar_adoption.csv)

One row per calendar year, province-wide. Built from the FSA-by-year aggregate,
so it sums to exactly the same totals as the mart.

| Column | Type | Definition |
| --- | --- | --- |
| `year` | integer | Calendar year the systems were installed (`year_installed` in the source). |
| `installs` | integer | Count of residential SolarHomes installations that year, after cleaning (rows with a valid FSA, an integer year, and a positive system size). |
| `installed_kw` | decimal (2 dp) | Sum of system size in kW for that year's installs. |
| `cumulative_installs` | integer | Running total of `installs` from the first observed year through this one. |
| `cumulative_kw` | decimal (2 dp) | Running total of `installed_kw`, rounded to 2 decimal places. |
| `yoy_install_change` | integer | `installs` minus the prior year's `installs`. Empty for the first observed year. |
| `yoy_install_pct` | decimal (1 dp) | Year-over-year change as a percent of the prior year's `installs`. Empty for the first observed year. |

## bi/exports/mart_solar.csv (copy of out/mart_solar.csv)

One row per FSA per year. This is the grain the dashboard and the Tableau guide
consume; both re-derive the provincial figures by summing these rows.

| Column | Type | Definition |
| --- | --- | --- |
| `fsa` | string | Forward sortation area: the first three characters of the installation's postal code, uppercased. Pattern letter-digit-letter, e.g. `B3H`. |
| `year` | integer | Calendar year the systems were installed (`year_installed` in the source). |
| `installs` | integer | Count of installations in this FSA and year. |
| `installed_kw` | decimal (2 dp) | Sum of system size in kW for this FSA and year. |

Sort order is `fsa`, then `year`, fixed by the export query.

## dashboard/data.js

The same rows as `bi/exports/mart_solar.csv`, re-emitted by `run.py` as a
JavaScript array literal named `DATA` so the dashboard opens from disk with no
server and no fetch. Keys match the mart columns exactly.
