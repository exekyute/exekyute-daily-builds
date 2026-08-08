# BI build guides: traffic collision safety map

Both dashboards read one frozen file, `bi/exports/mart_collisions.csv`. One row is one
reported collision that carries a usable local timestamp and a coordinate, 46,248 rows
in all, written by `sql/99_export.sql` and ordered by `collision_id`. Tableau and Power
BI aggregate that file as written and recompute none of the analysis, so a figure read
off one dashboard equals the same figure on the other and in the SQL golden. Column
meanings, including the eight 0/1 factor flags, are in `bi/exports/data_dictionary.md`.

Tableau live link: https://public.tableau.com/views/HRMTrafficCollisionSafety/Collisionsafety

- [Tableau guide](#tableau-guide-map-and-heatmap)
- [Power BI guide](#power-bi-guide-shares-and-matrix)
- [Numbers must match](#numbers-must-match)

---

## Tableau guide: map and heatmap

### What this dashboard shows

Where collisions land and when they happen. A density map plots every collision at its
own coordinate, a month-by-hour grid counts collisions in each of the 288 month and hour
cells, and one year filter drives both. A third worksheet holds the pedestrian count
that ties back to the SQL golden.

### Prerequisites

- Tableau Public Desktop Edition, free from https://public.tableau.com (Download on the
  top nav). Install with defaults.
- A free public.tableau.com account (Sign Up on the same page). Vizzes published with
  Tableau Public are public, which is fine here because the source is open data.
- Tableau Public works extract-only from files. It loads the CSV into an extract when
  you publish, and needs no database connection.

### Connect the data

1. Open Tableau Public. Under **Connect > To a File**, click **Text file**.
2. Browse to this repo's `bi/exports/mart_collisions.csv` and open it.
3. Check the field types Tableau inferred on the data source page:
   - `collision_id`, `year`, `month`, `hour`, `weekday` are whole numbers (#).
   - `accident_date` is a Date.
   - `lat` and `lon` are numbers (#), decimal.
   - `road_location_1`, `road_location_2`, `collision_configuration`,
     `light_condition`, `weather_condition` are strings (Abc).
   - The eight factor columns (`PEDESTRIAN_COLLISIONS`, `BICYCLE_COLLISIONS`,
     `IMPAIRED_DRIVING`, `DISTRACTED_DRIVING`, `AGRESSIVE_DRIVING`,
     `INTERSECTION_RELATED`, `FATAL_INJURY`, `NON_FATAL_INJURY`) are whole numbers.

   Tableau cleans text-file column names for display, so the data pane lists these as
   `Collision Id`, `Year`, `Month`, `Hour`, `Lat`, `Lon`, `Pedestrian Collisions` and so
   on. This guide names the CSV columns; the cleaned-up labels are the same fields.
4. Set the geographic roles: right-click `lat` > **Geographic Role > Latitude**, and
   `lon` > **Geographic Role > Longitude**. Halifax communities are not a built-in
   Tableau role, so the map binds to these two columns and to nothing else.
5. Leave the connection on **Extract**. Click **Sheet 1** to start building.

### Sheet 1: Collision density

Every collision as a point, drawn as a density surface.

1. Rename the sheet `Collision density`.
2. Drag `lon` to **Columns** and `lat` to **Rows**. Both pills must read `AVG(lon)` and
   `AVG(lat)`. A base map appears.
3. `collision_id` came in as a whole number, so convert it first: right-click it in the
   data pane and choose **Convert to Dimension**. Then drag it to **Detail** on the Marks
   card. The pill must be a blue `Collision Id`, not `SUM(Collision Id)`. That splits the
   aggregate into one mark per collision instead of one averaged point. Convert `month`
   the same way now, so it lands blue on Columns in Sheet 3, and convert `year` too, then
   right-click `year` again and choose **Continuous** so it stays green. The committed
   workbook holds `year` as a continuous dimension, which is what makes the filter in
   step 7 open on a range of values instead of asking for an aggregation first. `hour`
   stays a measure here; Sheet 3 converts its pill on the shelf instead.
4. Set the mark type to **Density**.
5. Open **Map > Map Layers** and set **Washout** to 0 so the base map stays at full
   strength under the density.
6. Zoom to Halifax Regional Municipality. The committed workbook stores that extent, so
   the published viz opens on HRM rather than on the whole projection.
7. Drag `year` to the **Filters** shelf. It is a continuous dimension now, so the range
   dialog opens straight away with no aggregation prompt: set the range to 2018 to 2026.
   Right-click the pill and set **Apply to Worksheets > All Using This Data Source**, so
   that single filter drives all three sheets. Right-click it again and choose
   **Show Filter**.

### Sheet 2: Pedestrian check

The single number the golden is checked against.

1. New worksheet, rename it `Pedestrian check`.
2. Drag `PEDESTRIAN_COLLISIONS` into the Dimensions area (or right-click it and choose
   **Convert to Dimension**), then drag it to the **Filters** shelf and tick **1** only.
3. Drag the table's count field, `mart_collisions.csv (Count)`, to **Text**. The sheet is
   now a single count with no rows and no columns.
4. Leave the mark type on **Automatic** and turn on mark labels.
5. The year filter from Sheet 1 already applies here, so the number moves with the year
   selection.

### Sheet 3: When collisions happen

The month-by-hour calendar grid.

1. New worksheet, rename it `When collisions happen`.
2. Drag `month` to **Columns**. It was converted to a dimension back in Sheet 1 step 3,
   so it lands as a blue discrete pill, 1 to 12.
3. Drag `hour` to **Rows** and convert it to a discrete dimension as well (blue pill, 0
   to 23). It arrives as a measure, so use the pill dropdown to switch it.
4. Set the mark type to **Square**.
5. Drag `mart_collisions.csv (Count)` to **Color**, and drag it to **Text** as well so
   each cell carries its own count. Pick the sequential **Orange** palette so the busiest
   cells read darkest.
6. The year filter from Sheet 1 applies here too.

### Dashboard

1. Click **New Dashboard**. Size: **Automatic**.
2. Set the layout to a horizontal flow. Drag `Collision density` in on the left and
   `When collisions happen` to its right. The committed dashboard gives the map about 39
   percent of the width and the heatmap about 50 percent.
3. In the remaining right-hand column, stack the `year` filter card on top and the count
   colour legend from `When collisions happen` below it.
4. Name the dashboard `Collision safety`. `Pedestrian check` stays off the dashboard; it
   is a worksheet, not a dashboard tile.

### Publish and file the artifacts

Tableau Public Desktop has no local Save to disk. `File > Save` and `File > Save As`
both redirect to `Save to Tableau Public As...`, which uploads to the Tableau Public
cloud. Getting the committable `.twb` therefore runs through the cloud and a `.twbx`
unzip.

1. **File > Save to Tableau Public As...**, sign in, and name it
   `HRM Traffic Collision Safety`. That name plus the `Collision safety` dashboard tab
   produces the live link at the top of this file.
2. On the viz page, click **Download Workbook**. It always downloads as a `.twbx`
   (packaged), never a bare `.twb`.
3. A `.twbx` is a zip. Copy it, rename the copy to `.zip`, unzip, and pull the `.twb`
   from the archive root. Commit that file as `bi/tableau/collision_safety_map.twb`.
   Never commit the `.twbx`: the packaged extract duplicates the data, bloats the repo,
   and does not diff. The committed workbook points its text connection at directory
   `../exports`, file `mart_collisions.csv`, so it reopens against the live mart from
   `bi/tableau/`.
4. Take screenshots into `bi/tableau/screenshots/`. The committed one is
   `dashboard-full.png`.

---

## Power BI guide: shares and matrix

### What this report shows

The factor flags read as percentages. Five cards carry the collision count, the
pedestrian count, the pedestrian share, the impaired share, and a share that follows a
factor slicer. A matrix breaks collision counts down by movement configuration and year
with a colour scale on the count. A year slicer drives the page.

### Import and type the data

1. **Get Data > Text/CSV**, choose this repo's `bi/exports/mart_collisions.csv`, then
   **Transform Data** to open Power Query.
2. Set the column types:
   - `collision_id` = Text
   - `accident_date` = Date
   - `year`, `month`, `hour`, `weekday` = Whole Number
   - `lat`, `lon` = Decimal Number
   - `road_location_1`, `road_location_2`, `collision_configuration`,
     `light_condition`, `weather_condition` = Text
   - `PEDESTRIAN_COLLISIONS`, `BICYCLE_COLLISIONS`, `IMPAIRED_DRIVING`,
     `DISTRACTED_DRIVING`, `AGRESSIVE_DRIVING`, `INTERSECTION_RELATED`,
     `FATAL_INJURY`, `NON_FATAL_INJURY` = Whole Number
3. **Close & Apply**. The table lands as `mart_collisions`.
4. Add the slicer's lookup list: **Home > Enter data**, one text column named `Factor`,
   five rows in this order: `Pedestrian`, `Bicycle`, `Impaired`, `Distracted`,
   `Intersection`. Name the table `Factor` and load it.
5. Leave `Factor` disconnected. It has no relationship to `mart_collisions`; the
   `Selected Factor %` measure reads it with `SELECTEDVALUE` instead. The model carries
   no date table, and the only relationship in it is the automatic date hierarchy Power
   BI attaches to `accident_date`.

### Measures (enter each verbatim)

    Collisions = COUNTROWS ( mart_collisions )

    Pedestrian % = DIVIDE ( CALCULATE ( [Collisions], mart_collisions[PEDESTRIAN_COLLISIONS] = 1 ), [Collisions] )

    Bicycle % = DIVIDE ( CALCULATE ( [Collisions], mart_collisions[BICYCLE_COLLISIONS] = 1 ), [Collisions] )

    Distracted % = DIVIDE ( CALCULATE ( [Collisions], mart_collisions[DISTRACTED_DRIVING] = 1 ), [Collisions] )

    Impaired % = DIVIDE ( CALCULATE ( [Collisions], mart_collisions[IMPAIRED_DRIVING] = 1 ), [Collisions] )

    Pedestrian Collisions = CALCULATE ( [Collisions], mart_collisions[PEDESTRIAN_COLLISIONS] = 1 )

    Collisions Prev Year = VAR y = MAX ( mart_collisions[year] ) RETURN CALCULATE ( [Collisions], REMOVEFILTERS ( mart_collisions[year] ), mart_collisions[year] = y - 1 )

    Collisions YoY = VAR p = [Collisions Prev Year] RETURN IF ( ISBLANK ( p ), BLANK (), [Collisions] - p )

    Selected Factor % = SWITCH ( SELECTEDVALUE ( 'Factor'[Factor] ), "Pedestrian", [Pedestrian %], "Bicycle", [Bicycle %], "Impaired", [Impaired %], "Distracted", [Distracted %], "Intersection", DIVIDE ( CALCULATE ( [Collisions], mart_collisions[INTERSECTION_RELATED] = 1 ), [Collisions] ), [Pedestrian %] )

Formatting in the committed model: `Collisions`, `Pedestrian Collisions`,
`Collisions Prev Year`, and `Collisions YoY` use the whole-number format string `0`.
`Pedestrian %`, `Impaired %`, and `Selected Factor %` are Percentage with 1 decimal
place. `Bicycle %` and `Distracted %` stay on general number, because nothing puts them
on the canvas directly; `Selected Factor %` is the only thing that reads them.

`Collisions Prev Year` and `Collisions YoY` sit in the model without a visual on the
page. Both work as written and can be dropped onto a card or the matrix.

### Visuals

The page is 1280 by 720, Fit to Page, and holds eight visuals.

- **Card**, `[Collisions]`, top left, with display units set to None so it reads the raw
  count rather than a rounded thousands figure.
- **Card**, `[Pedestrian %]`, next along the top row.
- **Card**, `[Impaired %]`, next along the top row.
- **Card**, `[Pedestrian Collisions]`, at the right end of the top row.
- **Card**, `[Selected Factor %]`, on the left below the year slicer. It follows whatever
  the factor slicer has selected.
- **Slicer**, `mart_collisions[year]`, Dropdown mode, single select on. The committed
  report has it set to 2025.
- **Slicer**, `Factor[Factor]`, list mode, single select on. The committed report has it
  set to `Impaired`.
- **Matrix**, Rows = `collision_configuration`, Columns = `year`, Values =
  `[Collisions]`, filling the lower right. Turn on **Conditional formatting > Background
  color** on `[Collisions]`, gradient minimum `#DEEFFF` to maximum `#118DFF`, with blanks
  coloured as zero.

### Save and file the artifacts

1. Turn on the project save format: **File > Options and settings > Options > Preview
   features > Power BI Project (.pbip) save option**, then restart if prompted.
2. **File > Save As**, choose **Power BI project files (.pbip)**, and save into
   `bi/powerbi/` as `collision_safety_map`. Commit the `.pbip` file together with its
   `.Report/` and `.SemanticModel/` text folders. Never commit a `.pbix`; the binary
   duplicates the data and does not diff.
3. Free Power BI Desktop has no public publish link, so the deliverable is the committed
   project plus an exported PNG or **File > Export > PDF** of the cards, the slicers, and
   the matrix. The committed screenshot is `bi/powerbi/screenshots/report.png`.

---

## Numbers must match

**In 2025, 169 of Halifax's collisions were pedestrian-involved, against 5,734
collisions for the year.** All three read that same pair:

- **SQL golden** (`expected/collisions_by_year.csv`): on the `year = 2025` row, the
  `pedestrian` column is 169 and the `collisions` column is 5,734, with
  `pct_pedestrian` at 2.9.
- **Tableau**: set the `year` filter to 2025 alone. The `Pedestrian check` sheet reads
  169, because it filters `PEDESTRIAN_COLLISIONS = 1` and counts rows.
- **Power BI**: with the year slicer on 2025, the `[Pedestrian Collisions]` card reads
  169, the `[Collisions]` card reads 5,734, and the `[Pedestrian %]` card reads 2.9%.

If any of those figures differs, the CSV loaded is stale: re-run `python run.py` from the
project folder, then reconnect or refresh the extract.
