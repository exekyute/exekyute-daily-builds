# Source

Two source layers feed this build: the authoritative rate table and the polygons
that enumerate the areas and carry the code that joins to it.

## Tax Rates (the rate table)

**Dataset:** Tax Rates

**Portal:** Halifax Data Mapping and Analytics Hub (https://data-hrm.hub.arcgis.com)

**Hub slug:** `HRM::tax-rates`

**Item id:** `a1d6cb118da642a4ae6a7b3191ae2369`

**Service:** `Tax_Rates` (FeatureServer, layer 0, no geometry)

**REST query (fields and count):** `https://services2.arcgis.com/11XBiaBYA9Ep0yNJ/arcgis/rest/services/Tax_Rates/FeatureServer/0/query?where=1=1&outFields=*&f=json`

**Snapshot pull query:** `https://services2.arcgis.com/11XBiaBYA9Ep0yNJ/arcgis/rest/services/Tax_Rates/FeatureServer/0/query?where=1=1&outFields=*&returnGeometry=false&f=json&resultRecordCount=2000&orderByFields=Bill_Year,Rate_Code,Rate_Type`

**Snapshot:** `data/raw/hrm_tax-rates_2026-07-13.csv`, 657 rows across bill years 2022 to 2025. The build keeps the latest bill year, **2025** (165 rows, 72 distinct rate codes).

## Area-rate polygons (the enumerated areas)

Five polygon layers enumerate the area rates. Each carries `AREARATE_CODE`, a
`DESCRIP` label, and internal roll codes; the build pulls the code and label and
tags each with its layer category.

| Category | Service | Feature rows |
| --- | --- | --- |
| Fire Protection | `FireProtectionAreaRates` | 1 |
| Transit | `TransitAreaRates` | 6 |
| Transportation | `TransportationAreaRates` | 1 |
| Community Facilities and Services | `Community_Facilities_and_Services_Area_Rates` | 20 |
| Private Road | `Private_Road_Area_Rates` | 24 |

Each layer's REST query is
`https://services2.arcgis.com/11XBiaBYA9Ep0yNJ/arcgis/rest/services/<Service>/FeatureServer/0/query?where=1=1&outFields=OBJECTID,AREARATE_CODE,DESCRIP,ARCODE_RES,ARCODE_COM,ARCODE_RCE&returnGeometry=false&f=json`.

**Snapshot:** `data/raw/hrm_area-rates_2026-07-13.csv`, 52 feature rows over the
five layers, resolving to **46 distinct area codes**.

**Licence:** Contains information licenced under the Open Government Licence,
Halifax. Licence text: https://data-hrm.hub.arcgis.com/pages/open-data-licence.

**Pull date:** 2026-07-13

## The join and the rate basis

An area's `AREARATE_CODE` equals a Tax Rates `Rate_Code`. Verified live on the
pull date: area `A000` (Frame Subdivision Homeowners Association) maps to Tax Rates
`Rate_Code` `A000`; `M050` (Fire Protection) to `M050`; `M060` (Local Transit) to
`M060`. The `ARCODE_RES`, `ARCODE_COM`, and `ARCODE_RCE` columns on the polygons
are internal assessment-roll codes and are **not** the join key; they are carried
in the snapshot for reference only.

A charge is looked up on `Rate_Code` **plus property class** (`Rate_Type`), because
Tax Rates holds one row per code and class. The rate basis is set by
`Calculation_Type`:

- `Flat Rate`: `Rate` is a fixed dollar charge per property (for example `A000` is
  a flat `45`).
- `Rate`: `Rate` is dollars **per $100 of taxable assessment** (for example `M060`
  Local Transit is `0.092` per $100, so a $325,000 assessment pays
  `0.092 * 325000 / 100 = 299.00`).

Confirmed live for the 2025 bill year: among the 46 area codes, `Calculation_Type`
takes only the two values `Flat Rate` and `Rate`. The other two values that appear
elsewhere in the table (`Mandatory Rate`, `Tiered Rate`) belong to general
municipal and provincial rate codes, not to the area codes this workbook stacks.

## How the snapshots were pulled

Both snapshots come from the public FeatureServer read; no app token or sign-in is
needed. Each layer returns under the 2000-row per-request cap in a single page, so
no paging was required. The responses are saved verbatim as the dated CSVs above,
which `build.py` reads instead of the live endpoint, so the workbook is fully
reproducible from `data/raw/`.

## Caveats in the source

- **Transportation has no 2025 rate.** Area code `M070` (Regional Transportation)
  is enumerated by the Transportation layer but has a Tax Rates entry only for
  2022, not for 2025. Selecting it in the calculator returns a zero charge and a
  note; it is kept on the areas sheet as a real enumerated area.
- **Class coverage varies.** Not every code carries all three classes: some have
  only Residential and Resource, some only Residential and Commercial. A lookup for
  a class a code does not carry returns a zero charge and a note.
- **Multiple polygons per code.** The Transit code `M060` appears on six polygons,
  one label per year; one private road code appears on two disjoint polygons. The
  areas sheet keeps one row per code, holding the last-sorting label (for `M060`,
  `2025 Local Transit`).
- **Stale label text.** A label may lag the rate (for example `R000` reads
  `Petpeswick Drive $300 Flat Fee` while the 2025 flat rate is `330`). The workbook
  always uses the Tax Rates value, never the label text.
