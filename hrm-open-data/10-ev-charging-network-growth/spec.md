# Spec

## Purpose

Take a pinned GeoJSON snapshot of Halifax's EV Charging Station layer and produce
one per-charger mart plus three deterministic tables that answer: how the public
charging network has grown by install year (with a running cumulative total), and
how the chargers split by charging level and by connector type. The growth curve
is short by nature (the whole network was installed across three years, 2024 to
2026), so the charging-level and connector breakdowns carry the second dimension
alongside it. Every measure is a count of charger records, never a sum of ports.

## Inputs

Dataset: EV Charging Station (`HRM::ev-charging-station`), pulled to
`data/raw/hrm_ev-charging-station_2026-07-13.geojson`. See SOURCE.md.

Fields used: `OBJECTID` (load only), `EVCSID`, `OWNER`, `CHARTYPE`, `CONNECTYPE`,
`POWER`, `LOCATION`, `EVACCESS`, `ASSETSTAT`, `INSTYR`, `QUANTITY`, and the WGS84
point geometry (longitude, latitude). All other source fields are deliberately
not read; `POWERUNIT` is checked once (every record is `KW`) but not carried.

## Load (01_load.sql)

Each GeoJSON feature is unnested and its properties read into `ev_raw`. The point
geometry is a `[longitude, latitude]` pair; DuckDB list indexing is 1-based, so
`coordinates[1]` is longitude and `coordinates[2]` is latitude. The text fields
land as VARCHAR, and the install year and quantity land as VARCHAR so every cast
happens in one place; `POWER` and the coordinates land as DOUBLE. The snapshot was
requested with `outSR=4326`, so the geometry is already WGS84 degrees.

## Cleaning and normalization (02_transform.sql)

1. **Whitespace.** The source free-text fields can carry stray carriage returns,
   line feeds, tabs, trailing spaces, and non-breaking spaces. A `norm` CTE folds
   every run of whitespace (including the non-breaking space, `chr(160)`) down to
   a single space and trims each text field. This matters here: the Canada Games
   Centre location ships on one record with a trailing space, which the fold
   removes so it reads identically to its five sibling records at the same site. A
   plain `trim()` removes only spaces, so the regex-based collapse is what clears
   any line break.
2. **Types.** `install_year` and `quantity` are cast to INTEGER. `power_kw` is the
   `POWER` rating rounded to two decimals (values are 6.6, 7, and 175 kW).
   Latitude and longitude are rounded to six decimals (about 0.1 m), which is ample
   for a city map and makes the CSV byte-stable.
3. **Text kept verbatim.** `location`, `owner`, `chartype`, `connectype`, and
   `access` are kept as published apart from the whitespace fold.
4. **Installed-only guard.** Only rows with `ASSETSTAT = 'INS'` (installed) are
   kept, so planned or retired assets could never enter the count. Rows missing a
   station id, install year, or charging level are also dropped. The current
   snapshot is entirely installed and complete, so the mart holds all 33 records.

## Count logic (03_analysis.sql)

Three tables plus a headline. One record is one installed public charging station.

- **chargers_by_year**: `COUNT(*)` grouped by `install_year`, with
  `cumulative_chargers` a windowed running total
  (`SUM(chargers) OVER (ORDER BY install_year ROWS UNBOUNDED PRECEDING TO CURRENT
  ROW)`). This is the cumulative growth curve: 10 by 2024, 29 by 2025, 33 by 2026.
- **counts_by_chartype**: `COUNT(*)` grouped by `chartype` (`L2`, `DCFC`).
- **counts_by_connectype**: `COUNT(*)` grouped by `connectype` (`J1772`,
  `CCSCHADEMO`, `CCSNACS`).
- **headline**: three ready-to-print lines. Line one states the total network size
  and the install-year span. Line two reads the cumulative curve off
  `chargers_by_year`. Line three names the charging-level and connector mixes off
  the two count tables. Every figure is assembled from the tables with
  `string_agg`, not hardcoded; `run.py` only prints them.

## Outputs

Four files, all golden and diffed row for row by `run.py verify`:

- `out/mart_ev.csv` (golden, 33 rows). One row per charging station with
  `evcsid, owner, chartype, connectype, power_kw, location, access, install_year,
  quantity, lat, lon`. Row order fixed by
  `ORDER BY install_year, chartype, connectype, evcsid` (evcsid is unique, so the
  order is total). Also copied to `bi/exports/mart_ev.csv` for the two BI tools.
- `out/chargers_by_year.csv` (golden, 3 rows). `ORDER BY install_year`.
- `out/counts_by_chartype.csv` (golden, 2 rows). `ORDER BY chargers DESC, chartype`.
- `out/counts_by_connectype.csv` (golden, 3 rows). `ORDER BY chargers DESC, connectype`.

## Headline figures

- 33 public EV charging stations, every one HRM-owned and publicly accessible,
  installed across 2024 to 2026.
- Cumulative network size: 10 by 2024, 29 by 2025, 33 by 2026.
- By charging level: 26 Level 2 (`L2`), 7 DC fast (`DCFC`).
- By connector: 26 `J1772`, 6 `CCSCHADEMO`, 1 `CCSNACS`.
- Power ratings: 22 chargers at 6.6 kW, 4 at 7 kW, 7 at 175 kW (the DC fast units).

## Determinism

The snapshot is pinned and committed. Every result query ends in an `ORDER BY`
whose tie-break reaches `evcsid`, a unique key, so the row order is total.
Coordinates and the power rating are rounded, so the same snapshot always yields
byte-identical output. No date arithmetic is used, so no `CURRENT_DATE` appears
anywhere; the pull date lives only in the snapshot filename and SOURCE.md. The four
golden CSVs were frozen from a first verified run; `run.py` re-runs the pipeline and
diffs the fresh output against them, printing PASS only on an exact row-for-row
match.

## Edge cases

- **Short growth curve.** The whole network was installed in just three years, so
  `chargers_by_year` has only three rows. This is expected and is why the build
  leans on the charging-level and connector breakdowns for its second dimension
  rather than a longer time series.
- **Several chargers per site.** 33 stations sit at fewer distinct locations: a
  site such as Cole Harbour Place or Armdale Rotary carries several stations, each
  its own `EVCSID` with its own point a few metres apart. The grain is the station,
  not the site, and each station keeps its own coordinate for the map.
- **Source mojibake in one location.** The St. Margaret's Centre location carries a
  mis-encoded apostrophe from a source encoding slip. Text values are preserved
  verbatim apart from whitespace normalization; the mart is UTF-8. The terminal
  `show` table renders only the ASCII year and level aggregates, so it stays
  code-page safe.
- **Uniform columns.** `OWNER` (all HRM), `EVACCESS` (all PUBLIC), `ASSETSTAT` (all
  INS), `POWERUNIT` (all KW), and `HOUR` (all 24) are constant across the snapshot.
  The mart keeps `owner` and `access` for the BI tools to display; `assetstat` is
  used as the installed-only guard; `powerunit` and `hour` are not carried.
