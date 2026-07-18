# Spec

## Purpose

Take a pinned GeoJSON snapshot of Halifax's Capital Projects and produce one
per-record mart plus three deterministic count tables that answer: how many
capital projects fall under each normalized category, how the categories rank,
how project counts move by budget year, and which asset types appear. The
dataset carries no dollar field, so every measure is a count of projects, never a
spend.

## Inputs

Dataset: Capital Projects (`HRM::capital-projects`), pulled to
`data/raw/hrm_capital-projects_2026-07-09.geojson`. See SOURCE.md.

Fields used: `OBJECTID` (stable sort key only), `PROJ_NO`, `PROJ_NAME`,
`LOC_ID`, `LOC_DESC`, `WORK_DESC`, `CATEGORY`, `YEAR`, `ASSET_TYPE`, and the
WGS84 point geometry (longitude, latitude). `NORTHING`, `EASTING`, `LINK`, and
`GLOBALID` are deliberately not used.

## Load (01_load.sql)

Each GeoJSON feature is unnested and its properties read into `cap_raw`. The
point geometry is a `[longitude, latitude]` pair; DuckDB list indexing is
1-based, so `coordinates[1]` is longitude and `coordinates[2]` is latitude. The
text fields land as VARCHAR and the year lands as VARCHAR so every cast happens
in one place; the coordinates land as DOUBLE.

## Cleaning and normalization (02_transform.sql)

1. **Whitespace.** The source free-text fields carry stray carriage returns,
   line feeds, tabs, and non-breaking spaces. A `norm` CTE folds every run of
   whitespace (including the non-breaking space, `chr(160)`) down to a single
   space and trims each text field, so no key or description carries a hidden
   line break. This matters: a raw project number such as `CR000005\r\n` would
   otherwise split a CSV row. A plain `trim()` removes only spaces, so the
   regex-based collapse is what actually clears the line breaks.
2. **Types.** `year` is cast to INTEGER; latitude and longitude are rounded to
   six decimals (about 0.1 m), which is ample for a city map and makes the CSV
   byte-stable.
3. **Category normalization.** The raw `CATEGORY` is kept, and a `category_norm`
   is derived from the mapping below.
4. **Asset type.** Trimmed; a blank becomes the explicit label `(unspecified)`.
5. **Guard.** Rows with no project number, year, or category are dropped. The
   current snapshot loses none, so the mart holds all 2,650 records.

### Category normalization mapping

The raw `CATEGORY` labels drift across budget years: the same programme appears
under several spellings and renames. `category_norm` folds those obvious
duplicates. The 24 raw labels collapse to 16 normalized categories.

| Raw `CATEGORY` | `category_norm` |
| --- | --- |
| Roads & Active Transportation | Roads |
| Roads & Streets | Roads |
| Parks & Playgrounds | Parks & Playgrounds |
| Parks and Playgrounds | Parks & Playgrounds |
| Parks | Parks & Playgrounds |
| Buildings | Buildings |
| Buildings/Facilities | Buildings |
| Halifax Transit | Transit |
| Metro Transit | Transit |
| Sidewalks | Sidewalks |
| Sidewalks, Curbs & Gutters | Sidewalks |
| Equipment & Fleet | Equipment & Fleet |
| Equipment & Machinery | Equipment & Fleet |
| Vehicles | Equipment & Fleet |
| Halifax Water (CWWF) | Halifax Water |
| Traffic Improvements | Traffic Improvements |
| Solid Waste | Solid Waste |
| Business Systems | Business Systems |
| Community & Property Development | Community & Property Development |
| Industrial Parks | Industrial Parks |
| Bridges | Bridges |
| Art & Cultural Assets | Art & Cultural Assets |
| Landfill | Landfill |
| Outdoor Sport Facilities | Outdoor Sport Facilities |

Folding decisions and the false friends left alone:

- **Roads** merges "Roads & Active Transportation" and "Roads & Streets", the
  two names the road-network programme carried across years.
- **Parks & Playgrounds** merges the ampersand spelling, the "and" spelling, and
  the bare "Parks". **Industrial Parks** is deliberately kept separate: it is
  industrial land development, not green space, so it is not folded into parks.
- **Buildings** merges "Buildings" and "Buildings/Facilities".
- **Transit** merges "Halifax Transit" and its former name "Metro Transit".
- **Sidewalks** merges "Sidewalks" and "Sidewalks, Curbs & Gutters".
- **Equipment & Fleet** merges the two "Equipment & ..." labels and "Vehicles".
- **Halifax Water** drops the "(CWWF)" programme suffix.
- Everything else already had one clean label and passes through unchanged. The
  `CASE` ends in `ELSE category`, so any future or unseen label survives rather
  than being silently blanked. **Bridges** and **Landfill** are left as their own
  categories rather than folded into Roads or Solid Waste, to avoid over-merging
  distinct asset classes.

The mapping is an exact-string `CASE` on the whitespace-normalized category, so
it is fully deterministic.

## Count logic (03_analysis.sql)

Three count tables plus a headline. One record is one project at one location in
one budget year.

- **counts_by_category_year**: `COUNT(*)` grouped by `category_norm` and `year`.
  The category-by-year grid the area chart and the year chart read.
- **counts_by_asset_type**: `COUNT(*)` grouped by `asset_type`.
- **category_ranking**: `COUNT(*)` per `category_norm`, with
  `category_rank = DENSE_RANK() OVER (ORDER BY projects DESC)` and
  `pct_of_total = round(100.0 * projects / total, 1)`. Rank 1 is the largest
  category. Ties share a rank (two categories tie at rank 13 with two projects
  each, and two more at rank 14 with one each).
- **headline**: two ready-to-print lines. Line one states the total count, the
  category count, and the year span. Line two names the single largest category
  with its count and share. `run.py` prints these; it does not compute them.

## Outputs

Five files, four of them golden and diffed row for row by `run.py verify`:

- `out/mart_capital.csv` (golden, 2,650 rows). One row per project record with
  `proj_no, proj_name, loc_desc, work_desc, category, category_norm, asset_type,
  year, lat, lon`. Row order fixed by
  `ORDER BY category_norm, year, proj_no, loc_desc, objectid`. Also copied to
  `bi/exports/mart_capital.csv` for the two BI tools and re-emitted as
  `dashboard/data.js` for the browser view.
- `out/counts_by_category_year.csv` (golden). `ORDER BY category_norm, year`.
- `out/counts_by_asset_type.csv` (golden). `ORDER BY projects DESC, asset_type`.
- `out/category_ranking.csv` (golden). `ORDER BY category_rank, category_norm`.

## Headline figures

- 2,650 capital projects across 16 normalized categories and the years 2013 to
  2021 (eight years are present; 2020 carries no records).
- Largest category: Roads, 1,245 projects, 47.0% of the total.
- Next: Parks & Playgrounds 558 (21.1%), Buildings 386 (14.6%).
- 15 asset-type values, of which `(unspecified)` covers 2,388 records because
  most records leave the asset type blank.

## Determinism

The snapshot is pinned and committed. Every result query ends in an `ORDER BY`
whose tie-break reaches `objectid`, a unique key, so the row order is total.
Coordinates are rounded and percentages are fixed to one decimal, so the same
snapshot always yields byte-identical output. The four golden CSVs were frozen
from a first verified run; `run.py` re-runs the pipeline and diffs the fresh
output against them, printing PASS only on an exact row-for-row match.

## Edge cases

- **Repeated project numbers:** 280 distinct `PROJ_NO` across 2,650 records. The
  grain is project-by-location-and-year, not project number, and each record
  keeps its own point. Counts are of records, framed as capital projects.
- **Blank asset type:** reported as `(unspecified)` rather than dropped.
- **Corrupt source characters:** two records carry mojibake in `WORK_DESC` from a
  source encoding slip. Text values are preserved verbatim apart from whitespace
  normalization; the mart is UTF-8. The terminal `show` table renders only the
  ASCII category and asset-type aggregates, so it stays code-page safe.
- **Missing 2020:** no records carry budget year 2020. The year charts show the
  eight years that exist rather than inventing a zero bar.
