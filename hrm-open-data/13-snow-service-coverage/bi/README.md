# BI build guides: snow service coverage

The SQL export step freezes three layers into `bi/exports/` and the Tableau workbook reads
them as they are, recomputing nothing:

- `street_winter_areas.geojson`, 32 MultiPolygon features. One row is one street winter
  maintenance area, carrying `area_id`, `serve_by`, `servarea`, and `area_km2`.
- `sidewalk_winter_areas.geojson`, 23 MultiPolygon features. One row is one sidewalk
  service zone, carrying `area_id`, `machine`, `fcode`, and `area_km2`.
- `ice_routes_by_priority.geojson`, 3 MultiLineString features. One row is one snow
  clearing priority (`1`, `2`, `(unassigned)`) with the 18,736 source segments dissolved
  into it, carrying `segment_count` and `length_km`.

`bi/exports/summary.csv` is the coverage summary `run.py` writes, byte-identical to the
golden `expected/coverage_summary.csv`. The committed workbook does not connect to it; it
is there so the map figures can be checked against the same rows the golden diff uses.
Column meanings for every export are in `bi/exports/data_dictionary.md`.

The committed dashboard is the Tableau workbook `bi/tableau/snow_service_coverage.twb`.

Tableau live link: https://public.tableau.com/views/HalifaxSnowServiceCoverage/Snowservicecoverage

- [Tableau guide](#tableau-guide-coverage-map)
- [Numbers must match](#numbers-must-match)

---

## Tableau guide: coverage map

### What this dashboard shows

Halifax's winter maintenance geography on one map: the 32 street areas filled by servicing
body, the 23 sidewalk zones as a second fill on top, and the ice-route network drawn as
lines coloured by priority. The three exports carry no date column, and each layer resolves
to one flat measure: a polygon's ground area, or a priority's total route length across
three rows. The boundaries are the part a table cannot reproduce, so the map carries the
whole view.

### Prerequisites

- Tableau Public Desktop Edition for Windows, free from https://public.tableau.com
  (Download on the top nav). Install with defaults.
- A free public.tableau.com account (Sign Up on the same page). Vizzes published with
  Tableau Public are public, which is fine here because the source is already open data.
- Tableau Public reads a spatial file directly and converts it to an extract when you
  publish. It needs no database connection. The committed workbook holds three extracts,
  one per layer.

### Connect the data

The workbook uses three separate spatial data sources, not one joined source. There is no
join and no blend between them; each layer plots its own geometry.

1. Open Tableau Public. Under **Connect > To a File**, click **Spatial file**. Browse to
   this repo's `bi/exports/street_winter_areas.geojson` and open it. Tableau exposes a
   `Geometry` field plus `area_id`, `serve_by`, `servarea`, and `area_km2`.
2. Add the second layer as its own data source, not as a second connection on this one:
   **Data > New Data Source**, then under **To a File** click **Spatial file** and open
   `bi/exports/sidewalk_winter_areas.geojson`. Its fields are `Geometry`, `area_id`,
   `machine`, `fcode`, `area_km2`. Do not use the **Add** link beside Connections on the
   data source page: that attaches the file to `street_winter_areas` and drops it on the
   relationship canvas, which is not what this workbook does.
3. Add the third the same way, **Data > New Data Source > Spatial file** on
   `bi/exports/ice_routes_by_priority.geojson`, with `Geometry`, `priority`,
   `segment_count`, `length_km`. The source list at the top of the Data pane should now
   show three entries: `street_winter_areas`, `sidewalk_winter_areas`,
   `ice_routes_by_priority`. Click a name to switch which source the sheet builds from.
4. Check the types Tableau inferred. `serve_by`, `servarea`, `machine`, `fcode`, and
   `priority` are strings (Abc). `area_id` and `segment_count` are whole numbers. `area_km2`
   and `length_km` are decimals. `priority` must stay a string; it holds `(unassigned)`
   alongside `1` and `2`.
5. Right-click `length_km` > **Default Properties > Number Format** and set Number with
   2 decimal places and a thousands separator. That is the format the committed workbook
   stores, and it is what makes the tooltip read `1,724.03`.
6. Click **Sheet 1** to start building.

### Sheet 1: Coverage map

The workbook has exactly one worksheet, `Coverage map`, holding three marks layers on a
single map. Build them in this order; the first geometry you plot becomes the base layer
and the later ones stack on top of it.

1. Rename the sheet `Coverage map`.
2. With `street_winter_areas` selected in the Data pane, double-click `Geometry`. The
   polygons plot and Tableau puts `Longitude (generated)` on Columns and
   `Latitude (generated)` on Rows.
3. Drag `area_id` to **Detail**. Without it the 32 polygons collapse into one mark, and
   individual areas stop being selectable.
4. Drag `serve_by` to **Color**. The four servicing bodies (HRM, FED, PROV, HIAA) each get
   a default palette colour. Drag `area_km2` to **Tooltip**; the pill reads
   `SUM(area_km2)`.
5. Rename this marks layer `Street areas`: double-click the layer's name on the Marks card
   and type it.
6. Switch the Data pane to `sidewalk_winter_areas` and drag its `Geometry` onto the map
   canvas. Drop it on the **Add a Marks Layer** target that appears in the upper left. Name
   the new layer `Sidewalk areas`.
7. On the `Sidewalk areas` layer, put `area_id` on **Detail**, and put `machine` and
   `area_km2` on **Tooltip** (`machine` lands as `ATTR(machine)`, which is correct: it is
   unique per zone). Click **Color** and set a flat fill of `#b07aa1` at roughly 50 percent
   opacity. The zones sit over the street areas, so an opaque fill would hide them.
8. Switch to `ice_routes_by_priority` and drag its `Geometry` onto the map as a third marks
   layer. Name it `Ice routes`. Put `priority` on **Color** and `length_km` on **Tooltip**,
   where the pill reads `SUM(length_km)`. Three lines draw: Priority 1, Priority 2, and
   `(unassigned)`.
9. Leave the background on the built-in Tableau map source with washout at 0, and frame the
   view on the HRM boundary. The committed workbook stores a fixed map extent in Web
   Mercator, so it opens on the same frame every time rather than refitting to the marks.

There are no calculated fields in this workbook. Every measure on the view is a direct sum
of a column the SQL already wrote.

### Dashboard

1. Click **New Dashboard** and rename it `Snow service coverage`.
2. Set Size to **Fixed size**, `1000 x 800`.
3. Drag `Coverage map` onto the canvas. It takes the left side of a horizontal container,
   about 82 percent of the width.
4. Keep two colour legends in a fixed 160 pixel vertical container down the right side: the
   `serve_by` legend from the Street areas layer above the `priority` legend from the Ice
   routes layer. Remove any other legend or card Tableau adds. The Sidewalk areas layer is a
   flat colour, so it has no legend.
5. Tableau generates a Phone layout for this dashboard, which stacks the map above the two
   legends. Leave it on.

### Publish and file the artifacts

Tableau Public Desktop has no local Save to disk. `File > Save` and `File > Save As` both
redirect to `Save to Tableau Public As...`, which uploads to the Tableau Public cloud.
Getting the committable `.twb` therefore runs through the cloud and a `.twbx` unzip.

1. **File > Save to Tableau Public As...**, sign in, and name it
   `Halifax Snow Service Coverage`. Publishing uploads the three extracts and opens the viz
   in a browser. That URL is the live link at the top of this file.
2. On the viz page, click **Download Workbook**. It always downloads as a `.twbx`
   (packaged), never a bare `.twb`.
3. A `.twbx` is a zip. Copy it, rename the copy to `.zip`, unzip it, and take the `.twb`
   from the archive root. Commit that file as `bi/tableau/snow_service_coverage.twb`. Never
   commit the `.twbx`: the packaged extract duplicates the data, bloats the repo, and does
   not diff.
4. Repoint the three spatial connections at `../exports` so the committed workbook reopens
   against this repo's frozen layers from `bi/tableau/`. That is what the committed file
   stores.
5. Screenshot the dashboard into `bi/tableau/screenshots/snow_service_coverage.png`, which
   is the image the project README embeds.

---

## Numbers must match

**Priority 1 ice routes total 1,724.03 km across 7,131 segments.** The map reads that figure
because the export already contains it, not because Tableau recomputes anything:

- **SQL golden** (`expected/coverage_summary.csv`): the row with `section` =
  `ice_by_priority` and `category` = `1` has `length_km` = `1724.03` and `feature_count` =
  `7131`. The other two ice rows read `1249.82` on 5,046 segments for Priority 2 and
  `4016.98` on 6,559 segments for `(unassigned)`.
- **Tableau**: on `Coverage map`, hover the Priority 1 line in the `Ice routes` layer. The
  tooltip's `SUM(length_km)` reads `1,724.03`, because that priority is a single dissolved
  feature whose `length_km` property is the golden's value.

The street section ties the same way. The `Street areas` layer holds 32 marks split by
`area_id`. Nothing on the map prints that count, so read it on a scratch worksheet: with
`street_winter_areas` selected in the Data pane, drag `serve_by` to **Rows** and
`street_winter_areas.geojson (Count)` to **Text**. The counts read HRM 14, FED 11, PROV 6,
HIAA 1, 32 in all, which is the `street_by_serve_by` section of the golden. Repeat with
`sidewalk_winter_areas` and `machine` on **Rows** for the 23 zones of the
`sidewalk_by_machine` section, one mark each on the `Sidewalk areas` layer. Delete the
scratch sheet before publishing.

If a figure on the map differs from the golden, the layer loaded is stale: re-run
`python run.py` from the project folder to rewrite `bi/exports/`, then refresh the extract
in Tableau.
