# Data dictionary

## Workbook: area_rate_calculator.xlsx

### Sheet `rates` (one row per rate code and class, 165 rows for bill year 2025)

| Column | Type | Meaning |
| --- | --- | --- |
| `Rate_Code` | text | The rate code. An area's `AREARATE_CODE` joins to this. |
| `Rate_Type` | text | Property class: Residential, Commercial, Resource, plus exempt and acre variants the calculator does not use. |
| `Rate` | number | The rate value. A dollar amount when `Calculation_Type` is `Flat Rate`; dollars per $100 of assessment when it is `Rate`. |
| `Calculation_Type` | text | `Flat Rate` or `Rate` (the general table also holds `Mandatory Rate` and `Tiered Rate`, which no area code uses). |
| `Rate_Description` | text | The source label for the rate. |
| `key` | formula | `=Rate_Code & "|" & Rate_Type`, the composite key the calculator matches against. |

### Sheet `areas` (one row per area code, 46 rows)

| Column | Type | Meaning |
| --- | --- | --- |
| `AREARATE_CODE` | text | The area code; equals a `rates` `Rate_Code`. |
| `DESCRIP` | text | The area label. Where a code carries several labels across years, the last-sorting one is kept. |
| `category` | text | The layer the area came from: Fire Protection, Transit, Transportation, Community Facilities and Services, or Private Road. |

### Sheet `calculator` (inputs, labels, and live formulas)

Two scenario blocks. Scenario A occupies rows 5 to 16, Scenario B rows 18 to 29.

| Region (Scenario A / Scenario B) | Meaning |
| --- | --- |
| `B6` / `B19` | Assessment input, taxable dollars. |
| `B7` / `B20` | Property class input (dropdown: Residential, Commercial, Resource). |
| `A10:A15` / `A23:A28` | Selected area codes (dropdown of `AreaCodes`); first three seeded, rest blank. |
| `B10:B15` / `B23:B28` | Area description, looked up from `areas`. |
| `C10:C15` / `C23:C28` | Composite lookup key, `code & "|" & class`. |
| `D10:D15` / `D23:D28` | Rate, looked up from `rates` on the key. |
| `E10:E15` / `E23:E28` | Calculation type, looked up from `rates` on the key. |
| `F10:F15` / `F23:F28` | Charge: the rate if `Flat Rate`, else rate times assessment over 100, to the cent. |
| `G10:G15` / `G23:G28` | Charge as a share of the scenario total, one decimal. |
| `H10:H15` / `H23:H28` | Note; flags a code and class with no 2025 rate. |
| `F16` / `F29` | Scenario total, `SUM` of the charge column; 392.75 and 664.00. |
| `G16` / `G29` | Total share, 100.0. |

## Golden: expected/key_figures.csv

One row per worked-example figure. Recomputed in plain Python, never read from the
workbook.

| Column | Type | Meaning |
| --- | --- | --- |
| `scenario` | text | `A` or `B`. |
| `figure` | text | `charge` for a per-code row, `total` for the scenario total. |
| `area_code` | text | The area code for a `charge` row; blank for `total`. |
| `class` | text | The property class the scenario used. |
| `calc_type` | text | `Flat Rate` or `Rate` for a `charge` row; blank for `total`. |
| `rate` | number | The looked-up rate for a `charge` row; blank for `total`. |
| `assessment` | integer | The scenario assessment, in dollars. |
| `charge` | number | The charge, or the total, to the cent, half-away-from-zero. |
| `share_pct` | number | Share of the scenario total, percent, one decimal, half-away-from-zero. |

Row order is fixed: for each scenario, one `charge` row per selected code in the
seeded order, then the `total` row.

## Snapshots: data/raw/

### `hrm_tax-rates_2026-07-13.csv` (657 rows, bill years 2022 to 2025)

Source fields `OBJECT_ID`, `Bill_Year`, `Rate_Description`, `Rate_Code`,
`Rate_Type`, `Rate`, `Minimum_Rate`, `Maximum_Rate`, `Calculation_Type`. The build
uses `Bill_Year`, `Rate_Code`, `Rate_Type`, `Rate`, `Calculation_Type`, and
`Rate_Description`, keeping bill year 2025.

### `hrm_area-rates_2026-07-13.csv` (52 feature rows over five layers)

| Column | Meaning |
| --- | --- |
| `category` | The layer the feature came from. |
| `OBJECTID` | ArcGIS feature id, per-layer surrogate key. |
| `AREARATE_CODE` | The area code (the join key). |
| `DESCRIP` | The area label. |
| `ARCODE_RES`, `ARCODE_COM`, `ARCODE_RCE` | Internal assessment-roll codes; carried for reference, not used for the join. |
