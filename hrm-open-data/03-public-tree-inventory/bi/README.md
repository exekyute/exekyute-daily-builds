# BI build guides: public tree inventory

Both dashboards read one frozen file, `bi/exports/mart_trees.csv`, written by
`sql/99_export.sql` and ordered by `tree_id`. One row is one tree: 78,896 rows carrying
species, DBH size class, setting, overhead wires, planting year, owner, status, and a
WGS84 coordinate. Neither tool recomputes any of the analysis. Both aggregate that one
file as written, so a figure read on the Tableau dashboard equals the same figure on the
Power BI report and in the SQL golden under `expected/`. Column meanings, and which
columns do not sum to anything meaningful, are in `bi/exports/data_dictionary.md`.

Tableau covers the geography and the two distributions: a point map of every tree
coloured by species and sized by DBH code, a DBH size-class bar chart, and a ranked
species bar. Power BI covers the diversity headline and the cross-tab: three DAX cards, a
species-by-wires matrix with a colour scale, a planting-year column chart, and a ranked
species bar with a year slicer.

Tableau live link: https://public.tableau.com/views/HRMPublicTreeInventory/Urbanforest

- [Tableau guide](#tableau-guide-map-and-bars)
- [Power BI guide](#power-bi-guide-cards-and-matrix)
- [Numbers must match](#numbers-must-match)

---

## Tableau guide: map and bars

### What this dashboard shows

Three worksheets on one 1000 by 800 dashboard called `Urban forest`, titled
"Halifax public tree inventory". `Tree map` plots one circle per tree across HRM,
coloured by a top-15 species grouping and sized by the DBH code. `DBH distribution` bars
the tree count by size tier. `Top species` bars the 15 most common species by tree count.
A filter action on the species bar drives the other two sheets.

### Prerequisites

- Tableau Public Desktop Edition, free from https://public.tableau.com (Download on the
  top nav). Install with defaults.
- A free public.tableau.com account (Sign Up on the same page). Vizzes published from
  Tableau Public are public, which is fine here because the source is open data.
- Tableau Public works extract-only from files. It loads the CSV into an extract when you
  publish, and needs no database connection.

### Connect the data

1. Open Tableau Public. Under **Connect > To a File**, click **Text file**.
2. Browse to this repo's `bi/exports/mart_trees.csv` and open it.
3. Check the field types on the data source page:
   - `tree_id`, `species_common`, `species_scientific`, `dbh_class`, `setting`, `wires`,
     `owner`, `status` are strings (Abc icon).
   - `dbh` is a whole number (#). It stays a measure.
   - `install_year` is a whole number. Convert it to a dimension; it is a calendar year,
     not a quantity.
   - `lat` and `lon` are decimal numbers. Confirm Tableau assigned the geographic roles
     **Latitude** to `lat` and **Longitude** to `lon`; if it did not, set them by hand
     (right-click the field > Geographic Role). Then right-click each and choose
     **Convert to Dimension**. The geographic role keeps both continuous, so they stay
     green and still draw a map, and the committed workbook stores each as a continuous
     dimension.
4. Leave the connection on **Extract**, then click **Sheet 1**.

Halifax communities and districts are not built-in Tableau geographic roles, so the map
binds to `lat` and `lon` rather than to a named role. Every row in this snapshot carries
a coordinate, so no tree drops off the map.

### Sheet 1: Tree map

1. New worksheet, rename it `Tree map`.
2. Build the set the colour field needs. Right-click `Species Common` in the data pane,
   **Create > Set**, name it `Top species`. On the **Top** tab choose **By field**, and
   set **Top 15** by `Tree Id`, **Count**, descending. Nothing is excluded on the General
   tab, so `Unidentified` (4,763 trees) sits inside the 15 and appears in the map legend.
3. Add the calculated field. **Analysis > Create Calculated Field**, type `Species group`
   in the name box at the top of the editor, and enter only the expression below it, using
   the field names exactly as the data pane shows them after Tableau's text-file name
   cleanup:

       IF [Top species] THEN [Species Common] ELSE "Other" END

   `[Top species]` is the set from step 2, so the field returns the species name for a tree
   inside the top 15 and `Other` for every other tree.
4. Drag `lon` to **Columns** and `lat` to **Rows**. Both were converted to dimensions on
   the data source page, so each pill arrives un-aggregated and reads `lon` and `lat`
   rather than `AVG(lon)` and `AVG(lat)`, which is what plots the raw coordinates instead
   of one averaged point. If a pill does read `AVG(...)`, open its dropdown and pick
   **Dimension**.
5. Drag `Tree Id` to **Detail** on the Marks card. That gives one mark per tree.
6. Set the Marks type to **Circle**.
7. Drag `Species group` to **Color**. The legend then reads the 15 grouped species plus
   `Other`.
8. Drag `dbh` to **Size**. The pill reads `SUM(dbh)`, which at one-tree granularity is
   that tree's size code, 1 to 9.
9. Drag `species_common`, `dbh_class`, and `wires` to **Tooltip**. Each lands as an
   `ATTR(...)` pill.
10. Open **Color > Opacity** and drop it to roughly 70 percent so overlapping trees stay
    readable; the committed workbook stores mark transparency at 180 of 255. Under
    **Map > Map Layers**, set **Washout** to 0 so the base map renders at full strength.

### Sheet 2: DBH distribution

1. New worksheet, rename it `DBH distribution`.
2. Drag `Dbh Class` to **Columns** as a discrete (blue) pill.
3. Drag `Tree Id` to **Rows** and set the pill to **Count**, so it reads `CNT(Tree Id)`.
4. Leave the Marks type on **Automatic**, which draws bars.
5. On the Label card, tick **Show mark labels** and leave the overlap culling on.

Left to right the bars read 41,855 (Class 1-2), 25,452 (Class 3-4), 9,011 (Class 5-6),
2,003 (Class 7-9), and 575 (Unknown), which is `expected/dbh_class_distribution.csv` in
its default alphabetical order. They sum to 78,896.

### Sheet 3: Top species

1. New worksheet, rename it `Top species`.
2. Drag `Species Common` to **Rows** and `Tree Id` to **Columns**, set to **Count**.
3. Drag `Species Common` to **Filters**. On the **General** tab untick `Unidentified` so
   it is excluded, then on the **Top** tab set **Top 15** by `Tree Id`, **Count**,
   descending. This filter is separate from the `Top species` set built for the map, and
   unlike the set it drops `Unidentified`.
4. Sort the `Species Common` pill descending by `CNT(Tree Id)`.
5. Turn mark labels on, as on Sheet 2.

The bars reproduce ranks 1 to 15 of `expected/species_ranking.csv`: Norway Maple 10,276
at the top, down to White Spruce 1,519.

### Dashboard

1. **New Dashboard**. Set Size to **Fixed size**, 1000 by 800.
2. Tick **Show dashboard title** and set the title to `Halifax public tree inventory`.
3. Drag `Tree map` in first and let it take the top half. Drag `DBH distribution` into the
   bottom left and `Top species` into the bottom right.
4. Keep the `Species group` colour legend and the `Dbh` size legend stacked in a fixed
   160 pixel column down the right side.
5. **Dashboard > Actions > Add Action > Filter**. Source sheet `Top species`, run action
   on **Select**, clear the selection on deselect, target the `Urban forest` dashboard on
   all fields. Clicking a species bar then filters the map and the DBH bars to that
   species.
6. Rename the dashboard tab `Urban forest`.

### Publish and file the artifacts

Tableau Public Desktop has no local Save to disk. `File > Save` and `File > Save As` both
redirect to `Save to Tableau Public As...`, which uploads to the Tableau Public cloud, so
getting the committable `.twb` runs through the cloud and a `.twbx` unzip.

1. **File > Save to Tableau Public As...**, sign in, and name the workbook
   `HRM Public Tree Inventory`. Publishing uploads the extract and opens the viz in a
   browser. The dashboard lands at the live link above.
2. On the viz page, click **Download Workbook**. It always downloads as a `.twbx`
   (packaged), never a bare `.twb`.
3. A `.twbx` is a zip. Copy it, rename the copy to `.zip`, unzip it, and pull the `.twb`
   from the archive root. Commit that file as `bi/tableau/public_tree_inventory.twb`.
   Never commit the `.twbx`: the packaged extract duplicates the data, bloats the repo, and
   does not diff. The repo `.gitignore` already excludes `*.twbx`.
4. Put screenshots in `bi/tableau/screenshots/`. The committed one is
   `dashboard-full.png`, the whole `Urban forest` dashboard.

---

## Power BI guide: cards and matrix

### What this report shows

One 1280 by 720 page holding seven visuals: three cards for tree count, distinct species,
and top-species share; a species-by-wires matrix with a background colour scale; a
planting-year column chart; a ranked species bar carrying the rank in its tooltip; and a
year slicer.

### Import and type the data

1. **Get Data > Text/CSV**, choose this repo's `bi/exports/mart_trees.csv`, then
   **Transform Data** to open Power Query.
2. Set the 12 column types:
   - `tree_id`, `species_common`, `species_scientific` = Text
   - `dbh` = Whole Number
   - `dbh_class`, `setting`, `wires` = Text
   - `install_year` = Whole Number
   - `owner`, `status` = Text
   - `lat`, `lon` = Decimal Number
3. **Close & Apply**. The table lands as `mart_trees`. The committed partition points at
   the relative path `..\exports\mart_trees.csv`, so the project resolves the mart from
   inside `bi/powerbi/`.

`install_year` is a whole number, not a date, and the mart is the only table in the model,
so this semantic model carries no date table and no relationships.

### Measures (enter each verbatim)

    Tree Count = COUNTROWS ( mart_trees )

    Distinct Species =
    CALCULATE (
        DISTINCTCOUNT ( mart_trees[species_common] ),
        mart_trees[species_common] <> "Unidentified"
    )

    Top Species Share = DIVIDE ( MAXX ( VALUES ( mart_trees[species_common] ), [Tree Count] ), [Tree Count] )

    Species Rank = RANKX ( ALLSELECTED ( mart_trees[species_common] ), [Tree Count], , DESC, Skip )

    Avg DBH = AVERAGE ( mart_trees[dbh] )

Format `Tree Count`, `Distinct Species`, and `Species Rank` as whole numbers (format
string `0`). Format `Top Species Share` as a percentage with 2 decimal places (the model
stores `0.00%;-0.00%;0.00%`). `Avg DBH` stays on the general number format; it is in the
model and no visual on the committed page places it.

### Visuals

- **Card**, `[Tree Count]`, top left. Set display units to None so it reads 78896 rather
  than 79K.
- **Card**, `[Distinct Species]`, top centre. Reads 250.
- **Card**, `[Top Species Share]`, top right. Reads 13.02%.
- **Matrix**, Rows = `species_common`, Columns = `wires`, Values = `[Tree Count]`. Add a
  visual-level **Top N** filter on `species_common`: Top 15 by `[Tree Count]`. Turn on
  **Conditional formatting > Background color** on the measure, a two-colour gradient from
  minimum to maximum with nulls coloured as zero. Rows come out alphabetical, so the
  colour, not the order, carries the ranking. The grid total reads 49,982 because only 15
  species are in view.
- **Clustered column chart**, X axis = `install_year`, Y = `[Tree Count]`. Only the 9,997
  trees carrying a recorded year contribute, and the axis runs 2013 to 2025.
- **Clustered bar chart**, Y axis = `species_common`, X = `[Tree Count]`, and
  `[Species Rank]` on Tooltips. Add the same visual-level **Top N** filter, Top 15 by
  `[Tree Count]`. Nothing is excluded here, so `Unidentified` sits third at 4,763.
- **Slicer** on `install_year`, set to **Dropdown** mode.

### Save and file the artifacts

1. Turn on the project save format: **File > Options and settings > Options > Preview
   features > Power BI Project (.pbip) save option**, then restart if prompted.
2. **File > Save As**, choose **Power BI project files (.pbip)**, and save into
   `bi/powerbi/` as `public_tree_inventory`. Commit the `.pbip` file together with its
   `.Report/` and `.SemanticModel/` text folders. Never commit a `.pbix`; the binary
   duplicates the data and does not diff.
3. Free Power BI Desktop has no public publish link, so the deliverable is the committed
   project plus an exported PNG or a **File > Export > PDF**. The committed image is
   `bi/powerbi/screenshots/report.png`.

---

## Numbers must match

With no filters applied, Norway Maple is the leading species at **10,276 trees, 13.02
percent** of the 78,896-tree inventory. All three read it the same way by construction:

- **SQL golden**: `expected/species_ranking.csv`, rank 1, `tree_count` = 10276 and
  `share_of_all_pct` = 13.02. `expected/summary.csv` repeats it as `top_species_count`
  and `top_species_share_pct`, against `total_trees` = 78896.
- **Tableau**: on the `Top species` sheet, the Norway Maple bar is the longest and its
  `CNT(Tree Id)` label reads 10,276. The `DBH distribution` bars sum to 78,896, so the
  share is 10,276 / 78,896 = 13.02 percent.
- **Power BI**: the `[Top Species Share]` card reads 13.02%, the Norway Maple row of the
  matrix totals 10276, and the `[Tree Count]` card reads 78896.

If any of those figures differs, the loaded CSV is stale. Re-run `python run.py` from the
project folder, then reconnect or refresh the extract.
