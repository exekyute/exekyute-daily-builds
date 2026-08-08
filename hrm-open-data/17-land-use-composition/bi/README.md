# BI build guides: land use composition by community

Both dashboards read the same frozen output the SQL export step wrote. The
per-community-and-class mart is `bi/exports/mart_landuse.csv`, 580 rows of
`community, zone_class, polygons, area, area_share`, and the Tableau map adds the
tagged polygon layer `bi/exports/zoning_tagged.geojson`, 11,076 features carrying
`zone_class, community, zone, description, area_km2`. Neither tool recomputes the
analysis. Both aggregate the mart as written, so a figure read off one dashboard
equals the same figure on the other and in the SQL golden. `area` is geodesic
ground area in square kilometres, and the column meanings are in
`bi/exports/data_dictionary.md`.

Tableau covers the geography and the within-community split: a filled zoning
choropleth plus a stacked bar whose shares come from a FIXED LOD. Power BI covers
the ranking and the grid: area-share DAX measures, a RANKX ranking of the most
mixed communities, and a conditional-format matrix of class by community.

Tableau live link: https://public.tableau.com/views/Halifaxlandusecomposition/Landusecomposition

- [Tableau guide](#tableau-guide-choropleth-and-ranking)
- [Power BI guide](#power-bi-guide-ranking-and-matrix)
- [Numbers must match](#numbers-must-match)

---

## Tableau guide: choropleth and ranking

### What this dashboard shows

Two panels stacked on one fixed 1000 by 800 dashboard. The top panel is the zoning
choropleth: all 11,076 polygons drawn from the tagged GeoJSON geometry, each filled
by its broad land use class. The bottom panel is a stacked bar of the fifteen most
mixed communities, each bar the community's zoned area split by class and labelled
with the share held by its largest class. A `Zone Class` filter card and one colour
legend sit in a column down the right side, and the filter drives both panels.

### Prerequisites

- Tableau Public Desktop Edition, free from https://public.tableau.com (Download on
  the top nav). Install with defaults.
- A free public.tableau.com account (Sign Up on the same page). Anything published
  with Tableau Public is public, which is fine here because the source is open data.
- Tableau Public works extract-only from files. Both connections in this build, the
  CSV and the GeoJSON, land as extracts, and the committed workbook carries one
  extract per data source.

Halifax communities are not a built-in Tableau geographic role, so nothing here
binds to a named role. The choropleth reads the polygon geometry the tagged GeoJSON
carries directly, and the stacked bar uses `community` as a plain discrete
dimension.

### Connect the data

1. Open Tableau Public. Under **Connect > To a File**, click **Spatial file** and
   open this repo's `bi/exports/zoning_tagged.geojson`. Tableau exposes a `Geometry`
   field plus the tagged attributes, which the data pane shows as `Area Km2`,
   `Community`, `Description`, `Zone`, and `Zone Class`.
2. Add the mart as a second, independent data source: **Data > New Data Source >
   Text file**, and open `bi/exports/mart_landuse.csv`. Do not use the **Add** link
   beside Connections on the data source page: that attaches the file to
   `zoning_tagged` and drops it on the relationship canvas. The committed workbook
   keeps the two sources apart, which is what the blend in the Dashboard step needs.
3. Check the types Tableau inferred on the mart. `community` and `zone_class` are
   strings and land as dimensions (`Community`, `Zone Class`); `polygons` is a whole
   number; `area` and `area_share` are decimals and land as measures (`Area`,
   `Area Share`). Leave both connections on **Extract**.
4. The source list at the top of the Data pane should now read `zoning_tagged` and
   `mart_landuse`. Click a name to choose which source a sheet builds from.

### Sheet 1: Land use map

The zoning choropleth, built on `zoning_tagged`.

1. Rename the sheet `Land use map` and select `zoning_tagged` in the Data pane.
2. Double-click `Geometry` so the polygons plot. Tableau puts generated Longitude on
   **Columns** and generated Latitude on **Rows** and hangs the geometry off the
   Marks card.
3. Drag `Zone Class` to **Color**. Every polygon is now filled by its broad land use
   class, which is the choropleth.
4. Drag `Community` and `Description` to **Tooltip**. Both land as `ATTR(...)` pills.
5. Keep the polygon borders thin so the fills read at municipal zoom.

### Sheet 2: Composition by community

The stacked bar, built on `mart_landuse`.

1. New worksheet, rename it `Composition by community`, and switch the Data pane to
   `mart_landuse`.
2. Drag `Community` to **Columns** and `Area` to **Rows**. Confirm the pill reads
   `SUM(Area)`.
3. Drag `Zone Class` to **Color**. With one measure and a colour dimension the bars
   stack, so each bar is a community's zoned area split by class.
4. Add the two share calculations. **Analysis > Create Calculated Field**, once per
   field, with the name typed in the box at the top of the editor and only the
   expression in the formula body below it.

   `Community Area`:

       { FIXED [Community] : SUM([Area]) }

   `Class Share of Community`:

       SUM([Area]) / MIN([Community Area])

   The FIXED LOD holds the denominator at the community's whole zoned area, so the
   share stays correct even when a class filter is applied: tick a single class and
   the bars shorten while the labels still read the share of the whole community.
5. Rank the communities by mix. All 182 communities will not fit one bar, and sorting
   by area surfaces only the large rural single-zone communities, whose bars are one
   solid colour. Rank by mix instead, with two more calculated fields (the first
   nests one LOD inside another):

   `Largest Class Area`:

       { FIXED [Community] : MAX({ FIXED [Community], [Zone Class] : SUM([Area]) }) }

   `Mix Index`:

       1 - ([Largest Class Area] / [Community Area])

   Drag `Community` to the **Filters** shelf, and on the **Top** tab choose **By
   field**, **Top**, `15`, by `Mix Index`, aggregation **Maximum**. Then sort the
   `Community` pill by **Field**, **Descending**, field `Mix Index`, aggregation
   `Maximum`. Use Maximum, not Sum: `Mix Index` is an LOD that repeats on every class
   row of a community, so Sum would scale it by the class count and misorder the
   communities.
6. Label only the dominant class. Labelling every segment makes the thin ones
   collide. Add one more calculated field, `Dominant Class Share`:

       IF ABS(SUM([Area]) - MIN([Largest Class Area])) < 0.0001
       THEN SUM([Area]) / MIN([Community Area])
       END

   Drag it to **Label**. The committed workbook formats it as a percentage
   (`p0.00%`). That yields exactly one label per bar, on the largest class, which is
   the figure the ranking is built on. On the Label card, tick **Allow labels to
   overlap other marks** so all fifteen render. `Class Share of Community` stays
   defined in the workbook as the per-segment version of the same ratio; drop it on
   **Tooltip** if you want every segment's share readable on hover.

### Dashboard

1. Click **New Dashboard** and rename it `Land use composition`. Switch Size from
   Range to the fixed **Desktop Browser (1000 x 800)** preset so the bars have room.
2. Drag `Land use map` in first, then drag `Composition by community` below it.
3. The two sheets sit on different data sources, so one filter card does not drive
   both by default. Define the blend first, from a worksheet tab rather than the
   dashboard, where the menu item is disabled: **Data > Edit Blend Relationships**,
   set `zoning_tagged` primary and `mart_landuse` secondary, choose **Custom**, and
   map `Community` to `Community` and `Zone Class` to `Zone Class`. Those two
   mappings are what the committed workbook stores.
4. Back on the dashboard, right-click the `Zone Class` filter card and choose
   **Apply to Worksheets > All Using Related Data Sources**. The committed card is a
   multiple-values dropdown.
5. Remove the duplicate filter and legend cards the second sheet brings in, and keep
   one `Zone Class` filter card above one colour legend in the column down the right
   side.

### Publish and file the artifacts

Tableau Public Desktop has no local save to disk. **File > Save** and **File > Save
As** both redirect to **Save to Tableau Public As...**, which uploads to the Tableau
Public cloud, so getting a committable `.twb` runs through the cloud and a `.twbx`
unzip.

1. **File > Save to Tableau Public As...**, sign in, and name it `Halifax land use
   composition`. Publishing uploads both extracts and opens the viz in a browser at
   the live link above.
2. On the viz page, click **Download Workbook**. It always downloads as a `.twbx`
   (packaged), never a bare `.twb`.
3. A `.twbx` is a zip. Copy it, rename the copy to `.zip`, unzip it, and pull the
   `.twb` from the archive root. Commit that file as
   `bi/tableau/land_use_composition.twb`. Never commit the `.twbx`: the packaged
   extract duplicates the data, bloats the repo, and does not diff.
4. The unzipped `.twb` points its two connections at the packaged copies of the
   files. The committed workbook is repointed at the repo exports,
   `bi/exports/mart_landuse.csv` and `bi/exports/zoning_tagged.geojson`. Repoint both
   the same way before committing.
5. Screenshots go in `bi/tableau/screenshots/`. The committed one is
   `dashboard-full.png`.

---

## Power BI guide: ranking and matrix

### What this report shows

One page, `Land use composition`, 1280 by 720. Three cards read the most mixed
community: its name, its `[Mix Index]`, and its `[Largest Class Share]`. A matrix
grids land use class against community with the share conditionally formatted, a bar
chart ranks the fifteen most mixed communities, and a slicer cuts everything by class.

### Import and type the data

1. **Home > Get Data > Text/CSV**, choose this repo's `bi/exports/mart_landuse.csv`,
   then **Transform Data** to open Power Query.
2. Set the column types:
   - `community` = Text
   - `zone_class` = Text
   - `polygons` = Whole Number
   - `area` = Decimal Number
   - `area_share` = Decimal Number
3. **Close & Apply**. The table lands as `mart_landuse`.

The model is this one table. The mart has no date column, so the committed semantic
model carries no date table, no calendar, and no relationships.

### Measures (enter each verbatim)

Six clicks of **Modeling > New measure**, one per block, exactly as written:

    Total Area = SUM ( mart_landuse[area] )

    Community Area = CALCULATE ( [Total Area], ALLEXCEPT ( mart_landuse, mart_landuse[community] ) )

    Area Share = DIVIDE ( [Total Area], [Community Area] )

    Largest Class Share = MAXX ( VALUES ( mart_landuse[zone_class] ), [Area Share] )

    Mix Index = 1 - [Largest Class Share]

    Community Mix Rank = RANKX ( ALLSELECTED ( mart_landuse[community] ), [Mix Index], , DESC, Skip )

Formats, set on each measure under **Measure tools > Format**:

- `Total Area` and `Community Area`: Decimal, 2 decimal places (`#,0.00`).
- `Area Share`, `Largest Class Share`, and `Mix Index`: Percentage, 2 decimal places
  (`0.00%`).
- `Community Mix Rank`: Whole number (`0`).

`Community Area` uses `ALLEXCEPT` so the denominator is the community's total zoned
area regardless of the current `zone_class` row context, and `Area Share` is then
each class's share of its own community. `Mix Index` is one minus the largest class
share, and `Community Mix Rank` ranks the communities by it over
`ALLSELECTED ( mart_landuse[community] )`, so rank 1 is the most mixed and the rank
respects the slicer but not the row context.

### Visuals

Add the page-level filter first: `community is not Unassigned`. The mart keeps the
`Unassigned` edge bucket (zero rounded area) for completeness, but with zero area its
`[Area Share]` is blank and its `[Mix Index]` computes to 100%, which would otherwise
top every ranking. Excluding it matches the SQL golden, which ranks real communities
only.

- **Matrix**: `Rows` = `zone_class`, `Columns` = `community`, `Values` =
  `[Area Share]`, with conditional formatting on the share (background colour,
  gradient scale, nulls coloured as zero). Add a **Top N** filter on `community`, Top
  `15` by `[Mix Index]`, so the grid holds the same fifteen communities the bar chart
  ranks rather than all 182. This is the composition grid.
- **Clustered bar chart**: `Y axis` = `[Mix Index]`, `Y axis category` = `community`,
  `Tooltips` = `[Community Mix Rank]`, sorted by `[Mix Index]` descending, with the
  same **Top N** filter on `community`, Top `15` by `[Mix Index]`. This surfaces the
  most mixed communities.
- **Cards**, three of them, each carrying a **Top N** filter on `community`, Top `1`
  by `[Mix Index]`, so all three read the single most mixed community: one on
  `community` for the name, one on `[Mix Index]`, one on `[Largest Class Share]`.
- **Slicer** on `mart_landuse[zone_class]`, set to **Dropdown** mode.

### Save and file the artifacts

1. Turn on the project save format: **File > Options and settings > Options > Preview
   features > Power BI Project (.pbip) save option**, then restart if prompted.
2. **File > Save As**, choose **Power BI project files (.pbip)**, and save into
   `bi/powerbi/` as `land_use_composition`. Commit the `.pbip` file together with its
   `.Report/` and `.SemanticModel/` text folders, which is where the measures above
   live as TMDL and the visuals as JSON. Never commit a `.pbix`; the binary
   duplicates the data and does not diff.
3. Free Power BI Desktop has no public publish link, so the deliverable is the
   committed project plus an exported PNG or a **File > Export > PDF**. The committed
   screenshot is `bi/powerbi/screenshots/report.png`.

---

## Numbers must match

**Bedford is the most mixed community, and its largest zone class reads 30.59
percent**, identical in all three places by construction:

- **SQL golden**: rank 1 in `expected/community_mix_ranking.csv` is BEDFORD, across 8
  classes, `largest_class_share` 30.59 and `mix_index` 69.41.
- **Tableau**: Bedford leads the ranking on `Composition by community`, and its
  `Dominant Class Share` label reads 30.59%, computed from the FIXED LOD
  `Community Area`.
- **Power BI**: Bedford's column in the matrix tops out at `[Area Share]` 30.59%, the
  `[Largest Class Share]` card reads the same figure, and `[Community Mix Rank]` is 1.

The rest of the ranking ties the same way. Halifax is next at 32.40% and Lower
Sackville at 33.21%, which is the order the Tableau bars and the Power BI bar chart
both draw. One level up, the municipal composition sits in
`expected/class_area_overall.csv`: Mixed Use leads at 40.20% of HRM zoned land
(1,057 polygons, 1,461.9596 km2), ahead of Rural and Resource at 36.82% and Park and
Open Space at 14.84%. The choropleth is that same composition drawn geographically.

If any tied figure differs, the CSV loaded is stale. Re-run `python run.py` from the
project folder, then refresh the Tableau extracts and the Power BI import.
