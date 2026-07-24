# Data dictionary: frozen BI mart

One mart, written by the SQL export step and read by both dashboards. Tableau and Power BI recompute nothing structural: they bind to these frozen cents so a viewer can flip between the two faces and read the same figure to the decimal. All dollar figures are rounded to the cent; consumption is a fixed three-decimal number; `cost_per_unit` is a fixed four-decimal figure; an empty `cost_per_unit` marks a building-and-fuel group whose net consumption is not positive.

## mart_energy.csv

One row per building and energy type, 285 rows. Ordered by `building_name`, `energy_type`. This is the Tableau extract and the Power BI import.

| # | Column | Type | Meaning |
| --- | --- | --- | --- |
| 1 | `building_name` | text | Building name (ENERGY STAR Portfolio Manager property name). |
| 2 | `hrm_building_id` | text | HRM building code, one-to-one with the building name. |
| 3 | `energy_type` | text | Fuel: Electricity, Natural Gas, Fuel Oil, or Propane. |
| 4 | `unit_of_measure` | text | The unit this fuel's consumption is metered in: GJ, kWh, or L. |
| 5 | `consumption` | number | Consumption for this building and fuel, in the fuel's unit. Sum only within a fuel, never across fuels. |
| 6 | `cost` | number | Cost for this building and fuel, dollars and cents. Summable across fuels. |
| 7 | `cost_per_unit` | number | `cost / consumption`, four decimals, dollars per unit. Empty where net consumption is not positive. |

## Totals to check after import

- SUM(`cost`) over all 285 rows = **86,444,113.77**, the municipal energy cost. This is the figure the Tableau stacked-bar total and the Power BI Total Cost card both read.
- Cost by fuel: Electricity 64,450,969.11; Natural Gas 15,153,963.12; Fuel Oil 5,938,197.64; Propane 900,983.90.
- Do not sum `consumption` across fuels: the four fuels use three different units (GJ, kWh, L), so a cross-fuel consumption total is meaningless. Aggregate consumption only within one `energy_type`.
