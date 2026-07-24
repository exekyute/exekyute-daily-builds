# Spec

## Purpose

Take the committed snapshot of HRM's building energy readings and produce deterministic tables that answer three things: which fuels drive municipal energy cost, which buildings cost the most across all their fuels, and what the blended cost per unit is within each fuel. The controlling rule throughout is that the four fuels are metered in three different units, so consumption is aggregated only within a fuel and only cost is summed across fuels.

## Inputs

Dataset: HRM Building Energy Usage, downloaded whole to `data/raw/hrm_building-energy-usage_2026-07-13.csv` (30,439 rows, one row per meter reading period). See SOURCE.md for the download endpoint and the field list.

Columns used, out of the twelve the download carries: `Energy Type`, `Portfolio Manager Property Name` (building name), `HRM Building ID`, `Unit of Measure`, `Consumption`, `Cost`. The energy id, property id, meter id, start and end dates, and object id are not used in the aggregate.

## Cleaning and validation rules (02_transform.sql)

1. Trim whitespace from the four text fields.
2. Cast `Consumption` to a fixed three-decimal number (the source carries at most three decimals) and round `Cost` to the cent, once. Rounding money here means every later total is a sum of clean cents that ties exactly.
3. Keep negative and zero readings. They are meter adjustments, credits, and corrections, and are real accounting entries. The build does not filter them.
4. Drop any row missing the energy type or the building name.

The result is `energy_clean`, one clean typed row per reading. The grain is unchanged from the raw table.

## Analysis logic step by step (03_analysis.sql)

The build produces one BI mart, three golden result tables, and a headline.

**mart_energy** (one row per building and energy type, 285 rows, the frozen BI face). Groups `energy_clean` by building and fuel and carries:

- `consumption` = `SUM(consumption)`, the within-fuel total in that fuel's unit.
- `cost` = `SUM(cost)`, the summed cents.
- `cost_per_unit` = `round(cost / consumption, 4)`, in dollars per unit. Guarded: NULL when `consumption` is not positive, so the two building-and-fuel groups whose net consumption goes negative once adjustments are applied (Ilsley Transit Facility fuel oil, Public Gardens Greenhouse 1-6 propane) never yield a meaningless per-unit figure.

**cost_by_fuel** (golden 1, one row per fuel, 4 rows). Rolls the mart to the fuel and joins a reading count from `energy_clean`:

- `meter_readings` = count of readings for the fuel; `building_count` = count of buildings that use it.
- `consumption` = within-fuel total; `cost` = summed cents.
- `cost_share` = `round(cost / SUM(cost) OVER (), 6)`, the fuel's share of the municipal energy cost.
- `fuel_rank` = `DENSE_RANK() OVER (ORDER BY cost DESC)`. Rank 1 is the costliest fuel.

**costliest_buildings** (golden 2, one row per building, 160 rows). Rolls the mart to the building. Cost is summable across fuels, so this sums every fuel's cost for the building:

- `fuel_count` = how many of the four fuels the building uses.
- `cost` = cost summed across all its fuels.
- `cost_share` = `round(cost / SUM(cost) OVER (), 6)`, the building's share of the municipal energy cost.
- `building_rank` = `DENSE_RANK() OVER (ORDER BY cost DESC)`. Rank 1 is the costliest building.

There is deliberately no consumption column: consumption cannot be summed across the differing units.

**cost_per_unit_by_fuel** (golden 3, one row per fuel, 4 rows). Rolls the mart to the fuel and computes `cost_per_unit` = `round(SUM(cost) / SUM(consumption), 4)`. Aggregating the cost and the consumption before dividing (rather than averaging the mart's row-level `cost_per_unit`) is the correct way to blend a ratio. Because the units differ, the four figures are not comparable across rows.

**headline** (two rows). Reads the grand total and the costliest building and writes two ready-to-read lines for the console. `run.py` prints these; it does not compute them.

## Outputs

Golden results, written to `out/` and diffed against `expected/`:

- `cost_by_fuel.csv`, 4 rows, ordered by `cost DESC, energy_type`.
- `costliest_buildings.csv`, 160 rows, ordered by `cost DESC, building_name`.
- `cost_per_unit_by_fuel.csv`, 4 rows, ordered by `energy_type`.

Frozen BI mart, written to `bi/exports/` (a deterministic export of the same table, read by both dashboards):

- `mart_energy.csv`, 285 rows, ordered by `building_name, energy_type`.

Every column is defined in data_dictionary.md (golden results) and bi/exports/data_dictionary.md (mart).

## Determinism

The snapshot is pinned and committed. Money is rounded to the cent once in `02_transform.sql`, consumption is pinned to three decimals, `cost_per_unit` is rounded to four decimals and stored as a fixed-scale decimal, and every result query ends in an `ORDER BY`, so the same input always produces byte-identical output. The pull date is a literal in the snapshot filename, not derived from the clock. The golden files under `expected/` were built from a first verified run; `run.py` re-runs the pipeline and diffs the fresh output against them, printing PASS only on an exact row-for-row match on all three.

## Numbers that tie

- Sum of `cost` over the 4 fuel rows = the sum over the 160 building rows = the sum over the 285 mart rows = **$86,444,113.77**, the headline total.
- Electricity is the largest fuel at **$64,450,969.11** (74.6 percent), then Natural Gas at $15,153,963.12, Fuel Oil at $5,938,197.64, and Propane at $900,983.90.
- The costliest building is Scotiabank Centre (BL614) at **$6,127,063.69** (7.1 percent of the municipal energy cost).
- `cost_share` sums to 1.0 up to the sixth-decimal rounding of each ratio (a per-row rounding artifact, not a cost discrepancy; the dollar totals tie exactly).

## Edge cases

- **Meter adjustments (negatives and zeros):** kept and summed as real accounting entries. Where a building-and-fuel group's net consumption is not positive, `cost_per_unit` is NULL (rendered as an empty field), never a divide by zero. The negative cost still counts toward every cost total.
- **Shared litre unit:** Propane and Fuel Oil are both metered in litres but are distinct fuels, so their consumption is summed separately, never combined.
- **Building identity:** building name and HRM building id are one-to-one in this data, so either keys a building; the mart carries both.
- **Cross-fuel consumption:** never computed. The only cross-fuel total the build reports is a dollar total.
