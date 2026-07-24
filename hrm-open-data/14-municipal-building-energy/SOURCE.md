# Source

**Dataset:** HRM Building Energy Usage

**Portal page:** https://data-hrm.hub.arcgis.com/datasets/HRM::hrm-building-energy-usage

**Slug:** `HRM::hrm-building-energy-usage`

**ArcGIS item id:** `a2e521d9aed84c8d824d828ee2c676b8`

**Service:** `HRM_Building_Energy_Usage`

**FeatureServer query endpoint:**
`https://services2.arcgis.com/11XBiaBYA9Ep0yNJ/arcgis/rest/services/HRM_Building_Energy_Usage/FeatureServer/0/query`

**CSV download endpoint:**
`https://data-hrm.hub.arcgis.com/api/download/v1/items/a2e521d9aed84c8d824d828ee2c676b8/csv?layers=0`

**Licence:** Open Government Licence, Halifax. Attribution: Contains information licenced under the Open Government Licence, Halifax. Licence text: https://data-hrm.hub.arcgis.com/pages/open-data-licence

**Pull date:** 2026-07-13

**Snapshot:** `data/raw/hrm_building-energy-usage_2026-07-13.csv`, 30,439 rows. This is the whole table, not a filtered or grouped pull.

## Why a full CSV download, not a server-side pull

The table is only **30,439 rows** (confirmed with `where=1=1&returnCountOnly=true`, which returns 30,439), one row per meter reading period, so it is small enough to download and commit whole. The compact, item-keyed CSV download endpoint returns the entire layer in one request with no key and no paging:

    GET https://data-hrm.hub.arcgis.com/api/download/v1/items/a2e521d9aed84c8d824d828ee2c676b8/csv?layers=0

The response carries a UTF-8 byte-order mark and header names with spaces (`Energy Type`, `Portfolio Manager Property Name`, and so on). `01_load.sql` reads those exact header names from the committed snapshot. `run.py` reads only the committed file, never the live endpoint, so the build reproduces byte for byte on any future day.

The layer has no geometry (`geometryType` is null, `type` is Table), so there is nothing to map: this is a tabular cost-and-consumption build aggregated by building and fuel.

## Fields in the snapshot

| Column | Source header | Meaning |
| --- | --- | --- |
| Energy ID | `Energy ID` | Row identifier for the reading. Not used. |
| Energy Type | `Energy Type` | Fuel: Natural Gas, Electricity, Propane, or Fuel Oil. |
| Portfolio Manager Property ID | `Portfolio Manager Property ID` | ENERGY STAR Portfolio Manager property id. Not used. |
| Portfolio Manager Property Name | `Portfolio Manager Property Name` | Building name, one per building. |
| HRM Building ID | `HRM Building ID` | HRM building code (for example `BL614`), one-to-one with the building name. |
| Meter ID | `Meter ID` | Meter identifier. Not used. |
| Start Date | `Start Date` | Start of the reading period. Not used in the aggregate. |
| End Date | `End Date` | End of the reading period. Not used in the aggregate. |
| Consumption | `Consumption` | Metered quantity for the period, in the unit named in Unit of Measure. |
| Unit of Measure | `Unit of Measure` | Unit of the consumption: GJ (Gigajoules), kWh (kilowatt-hours), or L (Litres). |
| Cost | `Cost` | Dollar cost of the reading period, dollars and cents. |
| ObjectId | `ObjectId` | ArcGIS object id. Not used. |

## The unit reality (why consumption is never summed across fuels)

The four fuels are metered in three different units, so a consumption figure is only meaningful within a single fuel:

| Fuel | Unit | Readings | Buildings |
| --- | --- | --- | --- |
| Electricity | kWh (kilowatt-hours) | 17,124 | 157 |
| Fuel Oil | L (Litres) | 8,170 | 79 |
| Natural Gas | GJ (Gigajoules) | 4,132 | 36 |
| Propane | L (Litres) | 1,013 | 13 |

Each fuel maps one-to-one to a single unit (confirmed: no fuel carries two units). Propane and Fuel Oil share the litre unit but are distinct fuels, so their consumption is still summed separately. Consumption is therefore aggregated only within a fuel and its unit; only **Cost** is summed across fuels. This rule is enforced in the SQL: the mart keys on building and energy type, and the only cross-fuel total the build reports is a dollar total.

## Caveats

- **Meter adjustments produce negatives and zeros.** 71 readings carry a negative consumption and 80 a negative cost (corrections and credits), and 926 readings are zero consumption. These are real accounting entries and are kept and summed. At the building-and-fuel grain, two groups net to a non-positive consumption once adjustments are applied (Ilsley Transit Facility fuel oil and Public Gardens Greenhouse 1-6 propane); the SQL renders their `cost_per_unit` as NULL rather than dividing by a zero or negative base.
- **Building name and building id are one-to-one.** No building name maps to more than one HRM building id, and no id to more than one name, so either can key a building; the mart carries both.
- The snapshot spans multiple years of readings. The build reports totals across the whole record, not a single year.
