# Spec

## Purpose

Take three pinned GeoJSON snapshots of Halifax Transit access assets (bus stops,
shelters, park and ride lots) and produce two marts plus one summary that answer:
how many bus stops there are, how many are accessible and what share, how many
carry a shelter and what share, and how many park and ride lots there are with
what total capacity. Every stop measure is a count of stops; the shelter flag is
one per stop even where a stop carries more than one shelter.

## Inputs

Three datasets, all pulled 2026-07-13. See SOURCE.md.

- Bus Stops (`HRM::bus-stops`) to `data/raw/hrm_bus-stops_2026-07-13.geojson`,
  2348 point features.
- Transit Shelters (`HRM::transit-shelters`) to
  `data/raw/hrm_transit-shelters_2026-07-13.geojson`, 521 point features.
- Park & Ride (`HRM::park-ride`) to `data/raw/hrm_park-ride_2026-07-13.geojson`,
  15 polygon features.

Fields used: bus stops `BUSSTOPID`, `STOPNUMBER`, `LOCATION`, `ACCESSIBLE`,
`BUSSTATUS`, and the WGS84 point; shelters `SHELTERID`, `BUSSTOPID`, `LOCATION`;
park and ride `PNR_NAME`, `PARKING_CAPACITY`, `ROUTES_SERVICED`, and the polygon.

## Load (01_load.sql)

The two point layers are read with `read_json`: each GeoJSON feature is unnested
and its properties read into the raw table. The point geometry is a
`[longitude, latitude]` pair; DuckDB list indexing is 1-based, so `coordinates[1]`
is longitude and `coordinates[2]` is latitude. The park and ride layer is
polygons, so it is read with `ST_Read` (the `spatial` extension, loaded in
00_schema) and each lot's polygon is reduced to a single interior point with
`ST_Centroid`; `ST_X` is longitude and `ST_Y` is latitude. All three snapshots
were requested with `outSR=4326`, so the geometry is already WGS84 degrees.

## Cleaning and normalization (02_transform.sql)

1. **Whitespace.** The source free-text fields can carry stray carriage returns,
   line feeds, tabs, trailing spaces, and non-breaking spaces. A `norm` step folds
   every run of whitespace (including the non-breaking space, `chr(160)`) down to
   a single space and trims each text field, so a stray character can never split
   a CSV row or leave a hidden difference on a value.
2. **Accessibility flag.** `ACCESSIBLE` is reduced to a 0/1 integer: 1 only when
   the code is `A` (Accessible). The other coded values, `N` (Non-Standard) and
   `I` (Inaccessible), and any blank, are 0. This is the one place a business rule
   turns a code into the accessible count.
3. **Coordinates.** Latitude and longitude are rounded to six decimals (about
   0.1 m), which is ample for a city map and makes the CSV byte-stable.
4. **Text kept verbatim.** Stop status, stop number, location, lot name, and lot
   routes are kept as published apart from the whitespace fold. The stop status
   code (`INS` or `TMP`) is carried as `status`.
5. **Guard.** A stop with a blank `BUSSTOPID` is dropped (the current snapshot has
   none, so the stops mart holds all 2348 records). Shelters keep every record,
   because `total_shelters` counts the whole shelter layer.

## Analysis logic (03_analysis.sql)

Two marts, one summary, one headline.

- **mart_stops** (one row per bus stop, 2348 rows). Carries `busstopid`,
  `stopnumber`, `location`, `accessible` (0/1), `status`, `has_shelter` (0/1),
  `lat`, `lon`. `has_shelter` is an `EXISTS` test: 1 when at least one shelter
  record links to this stop by `BUSSTOPID`. It is an existence test, not a count,
  so a stop with two shelters (both directions of a street) still reads 1. Shelter
  records with a blank or non-matching `BUSSTOPID` set no flag on any stop.
- **mart_parkride** (one row per lot, 15 rows). Carries `name`, `capacity`,
  `routes`, and the centroid `lat`, `lon`.
- **access_summary** (one row). Rolls the marts up to the golden coverage
  figures. `total_shelters` counts every shelter record (521), which exceeds
  `stops_with_shelter` (454) because several shelters sit at the same stop and a
  few reference a stop id outside the current stop layer. Both shares are rounded
  to one decimal.
- **headline** (two lines). Ready-to-print sentences assembled from
  `access_summary`; `run.py` only prints them.

## Outputs

Three files, all golden and diffed row for row by `run.py verify`:

- `out/mart_stops.csv` (golden, 2348 rows). `ORDER BY busstopid` (unique, so the
  order is total). Also copied to `bi/exports/mart_stops.csv`.
- `out/mart_parkride.csv` (golden, 15 rows). `ORDER BY name, lat, lon` (`PNR_NAME`
  is unique across the 15 lots; the coordinate tie-breakers are belt and braces).
  Also copied to `bi/exports/mart_parkride.csv`.
- `out/access_summary.csv` (golden, 1 row). `ORDER BY total_stops`.

## Headline figures

- 2348 bus stops.
- 1711 accessible stops, a 72.9 percent share.
- 521 shelter records; 454 distinct stops carry a shelter, a shelter coverage of
  19.3 percent.
- 15 park and ride lots, 2444 total parking spaces.

## Determinism

The three snapshots are pinned and committed. Every result query ends in an
`ORDER BY` whose key is unique, so the row order is total. Coordinates are rounded
and shares are rounded to one decimal, so the same snapshots always yield
byte-identical output. No date arithmetic is used, so no `CURRENT_DATE` appears
anywhere; the pull date lives only in the snapshot filenames and SOURCE.md. The
three golden CSVs were frozen from a first verified run; `run.py` re-runs the
pipeline and diffs the fresh output against them, printing PASS only on an exact
row-for-row match.

## Edge cases

- **Shelters per stop and unmatched shelters.** 521 shelter records reference 492
  distinct `BUSSTOPID` values; 454 of those match a bus stop in the current layer,
  which is `stops_with_shelter`. The rest sit at a repeated stop, are blank, or
  reference a stop id (for example a retired stop) not in the layer. `has_shelter`
  is therefore an existence flag per stop, and `total_shelters` (521) and
  `stops_with_shelter` (454) are deliberately different measures.
- **Accessibility codes.** Only `A` counts as accessible. The layer also carries
  `N` and `I` and one blank, all treated as not accessible, so the accessible
  share is a strict count of `A` stops.
- **Temporary stops.** Twelve stops carry `BUSSTATUS = TMP` (Temporary) rather
  than `INS` (In Service). They are kept in the mart with their status code, so a
  reader can filter on it; the coverage totals count all 2348 stops.
- **Polygon centroid.** Park and ride lots are polygons; the centroid is an
  interior point used only to place the lot on a map, not a survey coordinate.
