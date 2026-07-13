# Data dictionary: mart_permits.csv

The frozen dashboard mart. One row per permit, 18,316 rows. Tableau, Power BI, and
the browser dashboard all read this one file, so a viewer can flip between the
three faces and read the same figure to the cent. Written by `sql/99_export.sql`,
ordered by the source record id.

| # | Column | Type | Meaning |
| --- | --- | --- | --- |
| 1 | `permit_number` | text | Permit identifier. Not unique across rows (16,030 distinct across 18,316 records). |
| 2 | `issue_year` | integer | Calendar year the permit was issued. Blank when the permit has no issuance date. |
| 3 | `issue_month` | integer | Month number 1 to 12 of issuance. Blank when the permit has no issuance date. |
| 4 | `community` | text | Community name. Blank on some records. |
| 5 | `district` | text | Council district (District 01 to District 16, or Unidentified). |
| 6 | `work_type` | text | New Building, Renovation, or Addition. |
| 7 | `primary_work_scope` | text | Finer work scope within the work type. |
| 8 | `project_value` | number | Declared construction value in dollars, to the cent. Blank when the source recorded no estimated value (119 permits); excluded from value sums. |
| 9 | `net_new_units` | integer | Net change in residential units for the permit; can be negative. |
| 10 | `storeys` | integer | Storeys in the structure. Blank on 22 records. |
| 11 | `permit_status` | text | Workflow status (Issued, Completed, In Review, and so on). |
| 12 | `lat` | number | WGS84 latitude. Blank when the permit has no geolocated match (92 permits). |
| 13 | `lon` | number | WGS84 longitude. Blank when the permit has no geolocated match (92 permits). |

## How to bind the geography

Halifax communities and districts are not built-in geographic roles in Tableau, so
the map binds to the `lat` and `lon` this mart already carries, not to a named
role. Permits without coordinates keep every attribute and are omitted from the map
only.

## Reconciliation

- Summing `project_value` over rows with `issue_year = 2025` gives
  **3,856,416,602.50**, the headline figure both BI reports must read.
- Summing `project_value` over all rows with a non-blank `issue_year` gives
  **18,683,679,885.12**.
- `COUNT` of rows with `issue_year = 2025` is **3,100**; `SUM(net_new_units)` for
  2025 is **11,793**.
