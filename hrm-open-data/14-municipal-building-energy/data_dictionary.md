# Data dictionary: golden results

Three golden tables under `out/` (verified against `expected/`). All dollar figures are rounded to the cent; consumption is a fixed three-decimal number; `cost_share` is a fixed six-decimal ratio; `cost_per_unit` is a fixed four-decimal figure. An empty `cost_per_unit` marks a fuel group whose net consumption is not positive.

## out/cost_by_fuel.csv

One row per fuel, all 4. Ordered by `cost` descending, then `energy_type`.

| # | Column | Type | Meaning | Units |
| --- | --- | --- | --- | --- |
| 1 | `energy_type` | text | Fuel: Electricity, Natural Gas, Fuel Oil, or Propane. | category |
| 2 | `unit_of_measure` | text | The unit this fuel's consumption is metered in. | category |
| 3 | `meter_readings` | integer | Reading rows for the fuel across all buildings. | count |
| 4 | `building_count` | integer | Distinct buildings that use the fuel. | count |
| 5 | `consumption` | number | Within-fuel consumption total, in the fuel's unit. Not comparable across fuels. | unit of measure |
| 6 | `cost` | number | Total cost of the fuel across all buildings. | dollars.cents |
| 7 | `cost_share` | number | `cost / municipal total cost`, six decimals. | share (0 to 1) |
| 8 | `fuel_rank` | integer | Rank of the fuel by `cost`, costliest first. | rank (1 = top) |

## out/costliest_buildings.csv

One row per building, all 160. Ordered by `cost` descending, then `building_name`. There is no consumption column: consumption cannot be summed across the differing fuel units.

| # | Column | Type | Meaning | Units |
| --- | --- | --- | --- | --- |
| 1 | `building_name` | text | Building name (ENERGY STAR Portfolio Manager property name). | category |
| 2 | `hrm_building_id` | text | HRM building code, one-to-one with the building name. | code |
| 3 | `fuel_count` | integer | How many of the four fuels the building uses. | count (1 to 4) |
| 4 | `cost` | number | Total cost across every fuel the building uses. | dollars.cents |
| 5 | `cost_share` | number | `cost / municipal total cost`, six decimals. | share (0 to 1) |
| 6 | `building_rank` | integer | Rank of the building by `cost`, costliest first. | rank (1 = top) |

## out/cost_per_unit_by_fuel.csv

One row per fuel, all 4. Ordered by `energy_type` (no cross-fuel magnitude ordering is implied, since the units differ).

| # | Column | Type | Meaning | Units |
| --- | --- | --- | --- | --- |
| 1 | `energy_type` | text | Fuel: Electricity, Fuel Oil, Natural Gas, or Propane. | category |
| 2 | `unit_of_measure` | text | The unit this fuel's consumption is metered in. | category |
| 3 | `consumption` | number | Within-fuel consumption total, in the fuel's unit. | unit of measure |
| 4 | `cost` | number | Total cost of the fuel across all buildings. | dollars.cents |
| 5 | `cost_per_unit` | number | `cost / consumption`, four decimals. Dollars per unit, within the fuel only. | dollars per unit |

## Notes

- `cost_per_unit` is a blended dollars-per-unit within a single fuel. It is computed by aggregating the cost and the consumption before dividing, which is the correct way to blend a ratio, not by averaging per-building figures. Because the units differ (GJ, kWh, L), the four fuel figures are not comparable across rows.
- The `cost` totals all tie: by fuel, by building, and over the mart they all sum to $86,444,113.77. Consumption has no cross-fuel total by design.
