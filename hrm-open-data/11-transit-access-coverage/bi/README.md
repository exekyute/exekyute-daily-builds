# BI build guides: transit access coverage

The SQL export step freezes two marts into `bi/exports/`. `mart_stops.csv` holds one
row per bus stop, 2348 rows, each carrying an `accessible` flag, a `has_shelter` flag,
and a WGS84 `lat` and `lon`. `mart_parkride.csv` holds one row per park and ride lot,
15 rows, each carrying `capacity`, the routes it serves, and its centroid `lat` and
`lon`. The committed dashboard is the Tableau workbook
`bi/tableau/transit_access_coverage.twb`. It reads those two files and recomputes
nothing, so a figure read off the dashboard equals the same figure in the SQL golden.
Column meanings are in `bi/exports/data_dictionary.md`.

Tableau live link: https://public.tableau.com/views/HalifaxTransitAccessCoverage/Transitaccesscoverage

- [Tableau guide](#tableau-guide-two-map-layers)
- [Numbers must match](#numbers-must-match)

---

## Tableau guide: two map layers

### What this dashboard shows

Two maps stacked in one view. The upper map plots all 2348 bus stops, coloured by
whether the stop has a shelter and sized so sheltered stops read larger. The lower map
plots the 15 park and ride lots at their centroids, sized by posted parking capacity.
Neither mart carries a date column, and each row is a fixed point carrying one flag or
one capacity number, so the data has no time dimension and no second grain to pivot on.
Both marts are geography plus a single attribute, which is what the two map layers read.

### Prerequisites

- Tableau Public Desktop Edition for Windows, free from https://public.tableau.com
  (Download on the top nav). Install with defaults.
- A free public.tableau.com account (Sign Up on the same page). Vizzes published with
  Tableau Public are public, which is fine here because the source is already open data.
- Tableau Public works extract-only from files: it loads each CSV into an extract when
  you publish. It needs no database connection.
- A `python run.py` PASS in the project folder, so `bi/exports/` holds current marts.

### Connect the data

The two marts have no key in common and are never joined. They stay two independent
data sources, one per sheet.

1. Open Tableau Public. Under **Connect > To a File**, click **Text file** and open
   this repo's `bi/exports/mart_stops.csv`. The data source is named `mart_stops`.
2. Check the field types Tableau inferred:
   - `busstopid`, `location`, `status` are strings (Abc icon), used as dimensions.
   - `accessible` and `has_shelter` are whole numbers (#), used as measures.
   - `lat` and `lon` are decimal numbers (#). Tableau types `stopnumber` as a whole
     number too; nothing on the view uses it, so leave it.
3. Give the coordinates their geographic roles: right-click `lat` and pick
   **Geographic Role > Latitude**, then `lon` and pick **Geographic Role > Longitude**.
   Both stay measures aggregating as **Average**, which is what puts one mark per stop
   once a stop id is on Detail. Halifax place names are not a built-in Tableau
   geographic role, so the map binds to these columns and to nothing else.
4. Add the second file as its own source: **Data > New Data Source > Text file**, open
   `bi/exports/mart_parkride.csv`. It is named `mart_parkride`. Set `name` and `routes`
   to strings, `capacity` to a whole number, and give `lat` and `lon` the Latitude and
   Longitude roles the same way.
5. Leave both connections on **Extract**.

### Sheet 1: Transit access map

The bus-stop layer, split by shelter.

1. New worksheet, rename it `Transit access map`, and select the `mart_stops` source.
2. Drag `lon` to **Columns** and `lat` to **Rows**. The pills read `AVG(lon)` and
   `AVG(lat)` and the base map draws.
3. Drag `busstopid` to **Detail**. That breaks the single averaged mark into one mark
   per stop, 2348 of them.
4. Set the Marks type to **Circle**.
5. Drag `has_shelter` to **Color**, then right-click the pill and choose **Discrete**
   so it colours as two buckets rather than a continuous ramp. Set bucket `0` to
   `#bab0ac` (grey, no shelter) and bucket `1` to `#f28e2b` (orange, has a shelter).
6. Drag a second copy of `has_shelter` to **Size**. The pill reads `SUM(has_shelter)`,
   which resolves to 0 or 1 on a single-stop mark, so sheltered stops draw larger.
7. Drag `location` to **Tooltip** (it lands as `ATTR(location)`) and `accessible` to
   **Tooltip** (it lands as `SUM(accessible)`), so a hovered stop names its address and
   states whether it is coded accessible.
8. On the Color card, set **Border** to white. Downtown stops sit close enough to merge
   into a blob without it.
9. Pull the size slider back to roughly a third of its range. The committed workbook
   stores this sheet with mark scaling off, so the circles hold their size as the map
   zooms, and it keeps **Map > Map Layers** washout at 0 so the base map reads at full
   strength.

### Sheet 2: Park and ride

The lot layer, sized by capacity.

1. New worksheet, rename it `Park and ride`, and select the `mart_parkride` source.
2. Drag `lon` to **Columns** and `lat` to **Rows**, again `AVG(lon)` and `AVG(lat)`.
3. Drag `name` to **Detail**. One mark per lot, 15 of them.
4. Set the Marks type to **Circle** and set the mark colour to `#4e79a7`.
5. Drag `capacity` to **Size**. The pill reads `SUM(capacity)`, so Woodside Ferry
   Terminal at 515 spaces draws largest and Alderney Ferry Terminal at 20 smallest.
6. Drag `name` to **Label** as well, so each lot names itself on the map. Leave
   **Allow labels to overlap other marks** unticked on the Label card: the workbook
   culls labels where lots crowd rather than stacking text on text.
7. Drag `routes` to **Tooltip**. It lands as `ATTR(routes)` and prints the route list
   the lot serves.

### Dashboard

1. Click **New Dashboard**. Set Size to **Fixed size**, **Desktop Browser (1000 x 800)**.
2. Tick **Show dashboard title**. The title zone renders the dashboard name, so name
   the dashboard `Transit access coverage`.
3. Drag `Transit access map` into the upper half and `Park and ride` into the lower
   half. They split the space below the title evenly.
4. Move the two legend cards into a single vertical container pinned to the right,
   fixed at 160 px wide: the `has_shelter` colour legend from the stops sheet on top,
   the `capacity` size legend from the lots sheet below it.
5. No filters and no dashboard actions. The two sheets sit on separate data sources
   with no shared key, so neither one drives the other.

### Publish and file the artifacts

Tableau Public Desktop has no local Save to disk. `File > Save` and `File > Save As`
both redirect to `Save to Tableau Public As...`, which uploads to the Tableau Public
cloud. Getting the committable `.twb` therefore runs through the cloud and a `.twbx`
unzip.

1. **File > Save to Tableau Public As...**, sign in, name it
   `Halifax Transit Access Coverage`. Publishing uploads both extracts and opens the
   viz in a browser. That is the live link at the top of this file.
2. On the viz page, click **Download Workbook**. It always downloads as a `.twbx`
   (packaged), never a bare `.twb`.
3. A `.twbx` is a zip. Copy it, rename the copy to `.zip`, unzip, and pull the `.twb`
   from the archive root. Commit that file as
   `bi/tableau/transit_access_coverage.twb`. Never commit the `.twbx`: the packaged
   extract duplicates the data, bloats the repo, and does not diff.
4. Repoint the two connections at the repo copies so the workbook reopens locally. The
   committed workbook stores them relative, `../exports/mart_stops.csv` and
   `../exports/mart_parkride.csv`, which resolve to `bi/exports/` from `bi/tableau/`.
   Only the workbook XML is committed, so the data comes back from those two CSVs.
5. Screenshot the dashboard into `bi/tableau/screenshots/`. The committed shot is
   `bi/tableau/screenshots/01-dashboard.png`.

---

## Numbers must match

With no filters applied, shelter coverage reads the same on both sides.

**454 of 2348 bus stops have a shelter, 19.3 percent**:

- **SQL golden** (`expected/access_summary.csv`): `stops_with_shelter` = 454,
  `total_stops` = 2348, `shelter_coverage_pct` = 19.3. Those are the figures the
  project README quotes.
- **Tableau** (`Transit access map`): the map draws 2348 circle marks, one per
  `busstopid`, and `SUM(has_shelter)` across all of them totals 454. Filtering
  `has_shelter` to 1 leaves 454 orange marks and drops the 1894 grey ones.

The second layer ties the same way: `expected/access_summary.csv` gives
`parkride_lots` = 15 and `parkride_capacity` = 2444, and on `Park and ride` the map
draws 15 marks whose `SUM(capacity)` totals 2444.

If either figure differs, the CSV loaded is stale: re-run `python run.py` from the
project folder and refresh the extract.
