# Spec

## Purpose

Take three pinned GeoJSON snapshots of Halifax's winter maintenance geography and
produce one deterministic summary that answers: how is winter maintenance
responsibility carved up across street servicing bodies, sidewalk service zones,
and ice-route priorities? The build also emits three cleaned map layers for a
single Tableau dashboard. It is a static operational boundary map: the one
headline measure, ice-route kilometres in the top priority class, is a flat
figure, so the BI status is SINGLE (Tableau).

## Inputs

Three layers, pulled to `data/raw/` (see SOURCE.md):

- Street Winter Maintenance Areas (`HRM::street-winter-maintenance-areas`), 32 polygons.
- Sidewalk Winter Maintenance Areas (`HRM::sidewalk-winter-maintenance-areas`), 23 polygons.
- Ice Routes (`HRM::ice-routes`), 18,736 polylines.

Fields used: `SERVE_BY`, `SERVAREA` (street); `MACHINE`, `FCODE` (sidewalk);
`PRIORITY`, `Shape__Length` (ice), plus the WGS84 geometry of each. Other source
fields are read by `ST_Read` but not used by the summary.

## Load (01_load.sql)

`ST_Read` loads each GeoJSON file into a raw table, carrying both attributes and
the WGS84 geometry (`GEOMETRY('EPSG:4326')`). The paths are relative to the
project folder, so `run.py` launches from here. The `spatial` extension is
installed and loaded once in `00_schema.sql`, in the shared connection.

## Cleaning (02_transform.sql)

1. **Whitespace.** Every text field is whitespace-normalized: a
   `regexp_replace` folds every run of whitespace, including the non-breaking
   space (`\x{00a0}`), down to a single space, then `trim` clears the ends. A
   plain `trim()` removes only leading and trailing spaces, so the regex collapse
   is what clears any embedded break.
2. **Priority label.** Ice-route `PRIORITY` is `1`, `2`, or null. A null is
   labelled `(unassigned)` so the group is explicit rather than dropped. The null
   routes are off-street and sidewalk maintenance codes (NPS, PBRS, PBHV, and the
   like) that carry no numbered road priority.
3. **Measures.** Polygon rows get `area_km2` from `ST_Area_Spheroid(geom)`, which
   measures true ground area on the WGS84 ellipsoid (so the source projection does
   not distort it), divided to square kilometres. Ice-route rows keep the source
   `Shape__Length` in metres per segment.

## Roll-up (03_analysis.sql)

- **ice_by_priority.** Count and length come from the ice attribute rows:
  `segment_count` is the number of route records and `length_km` is
  `SUM(Shape__Length)/1000` cast to two decimals. The drawn geometry is built
  separately: every segment is exploded to its component LineStrings with
  `ST_Dump`, then bundled with `ST_Collect` into one MultiLineString per priority.
  Exploding first guarantees a uniform MultiLineString (a raw mix of LineString
  and MultiLineString would collect to a GeometryCollection) and drops the ten
  records whose source geometry is null. Those ten still count toward the
  attribute totals, because they are real routes the map simply cannot draw.
- **coverage_summary.** One long table stacking three sections, each with its own
  `ROW_NUMBER()` order so a single `ORDER BY section_ord, row_ord` fixes the file:
  - `street_by_serve_by`: `COUNT(*)` and total `area_km2` grouped by `serve_by`,
    ordered by feature count descending.
  - `sidewalk_by_machine`: `COUNT(*)` (always 1, since `MACHINE` is unique per
    area) and `area_km2` grouped by `machine`, ordered by area descending.
  - `ice_by_priority`: `segment_count` and `length_km` per priority, ordered
    `1`, `2`, `(unassigned)`.
  Polygon sections carry area and no length; the ice section carries length and
  no area, so each measure column is blank where it does not apply.
- **headline.** Two ready-to-print lines, both computed in SQL: line one is the
  top-priority ice-route length and the wider priority split, line two is how the
  street network splits across servicing bodies. `run.py` prints them; it
  computes nothing.

## Outputs

- `out/coverage_summary.csv` (golden, 30 data rows). Columns `section, category,
  feature_count, length_km, area_km2`. Row order fixed by `section_ord, row_ord`.
  Diffed row for row by `run.py verify`, and copied to `bi/exports/summary.csv`.
- `bi/exports/street_winter_areas.geojson` (32 polygons; `serve_by`, `servarea`,
  `area_km2`).
- `bi/exports/sidewalk_winter_areas.geojson` (23 polygons; `machine`, `fcode`,
  `area_km2`).
- `bi/exports/ice_routes_by_priority.geojson` (3 MultiLineString features;
  `priority`, `segment_count`, `length_km`). Each feature carries the same
  length that sits in the golden. The map layers are written at six-decimal
  coordinate precision and are not part of the golden diff, per the geometry
  convention.

## Headline figures

- Priority 1 ice routes total 1,724.03 km across 7,131 segments; Priority 2 add
  1,249.82 km across 5,046; and 4,016.98 km across 6,559 segments carry no
  numbered priority. Lengths are the source `Shape__Length` (projected metres);
  see SOURCE.md for the true-ground comparison.
- The street network splits across four servicing bodies over 32 areas: HRM 14,
  FED 11, PROV 6, HIAA 1.
- Sidewalks are carved into 23 service zones, from Winter Service Zone 1 at
  157.77 km2 down to HRM WEST Zone 1 Route 5 at 0.05 km2.

## Determinism

The three snapshots are pinned and committed. Every result query ends in an
`ORDER BY`, and each summary section carries a `ROW_NUMBER()` whose ordering keys
are total within the section (`MACHINE` is unique, the street tie-break reaches
the code, and the priority order is a fixed `CASE`), so the row order is total.
Lengths are fixed to two decimals and areas to four via `DECIMAL` casts, so the
same snapshot always yields byte-identical output. The golden was frozen from a
first verified run; `run.py` re-runs the pipeline and diffs the fresh output
against it, printing PASS only on an exact row-for-row match.

## Edge cases

- **Null ice-route priority:** 6,559 of 18,736 segments carry no numbered
  `PRIORITY`. They are labelled `(unassigned)` and kept, not dropped.
- **Null ice-route geometry:** ten route records have a null geometry in the
  source. They count toward the attribute totals (`segment_count`, `length_km`)
  and are absent only from the drawn map layer.
- **Mixed line geometry:** a handful of ice segments arrive as MultiLineString
  rather than LineString. `ST_Dump` explodes them before `ST_Collect`, so every
  dissolved priority feature is a clean MultiLineString that a Tableau spatial
  connection renders directly.
- **Unique sidewalk `MACHINE`:** every sidewalk area has a distinct `MACHINE`
  label, so its group count is always 1; the informative measure there is the
  zone area, which the ordering uses.
- **Web Mercator length:** `Shape__Length` overstates true ground length; the
  build reports it as provided for tool-to-tool consistency and documents the
  true-ground figures in SOURCE.md.
