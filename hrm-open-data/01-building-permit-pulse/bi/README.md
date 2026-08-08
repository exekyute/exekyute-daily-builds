# BI build guides: building permit pulse

Both dashboards read one frozen file, `bi/exports/mart_permits.csv`, written by
`sql/99_export.sql` and copied here by `python run.py`. One row is one building
permit, 18,316 rows, ordered by the source record id. Neither tool recomputes any
of the analysis: they aggregate the columns as exported, so a figure read off the
Tableau dashboard equals the same figure in Power BI and in the SQL golden.
Column meanings, blank counts, and the reconciliation totals are in
`bi/exports/data_dictionary.md`.

Tableau live link: https://public.tableau.com/views/HalifaxBuildingPermitPulse/Permits

- [Tableau guide](#tableau-guide-map-and-running-total)
- [Power BI guide](#power-bi-guide-decomposition-and-ranking)
- [Numbers must match](#numbers-must-match)

---

## Tableau guide: map and running total

### What this dashboard shows

Where permits land and how residential supply accumulates. The top sheet is a point
map of individual permits, each circle sized by declared project value and coloured
by work type. The bottom sheet is a running total of net new residential units by
council district across the issue years. One Issue Year filter drives both.

### Prerequisites

- Tableau Public Desktop, free from https://public.tableau.com. Install with defaults.
- A free public.tableau.com account. Vizzes published with Tableau Public are public,
  which is fine here because the source is open data.
- Tableau Public works extract-only from files, so no database connection is needed.

### Connect the data

1. **Connect > To a File > Text file**, and open `bi/exports/mart_permits.csv`.
2. Check the types Tableau inferred on the data source page:
   - `permit_number`, `community`, `district`, `work_type`, `primary_work_scope`,
     `permit_status` as strings (Abc).
   - `issue_year`, `issue_month`, `net_new_units`, `storeys` as whole numbers (#).
   - `project_value`, `lat`, `lon` as numbers (#), decimals.
3. Leave the connection on **Extract**.
4. In the data pane, right-click `Issue Year` and choose **Convert to Dimension**, then
   do the same for `Issue Month`. Both move above the divider in the field list. Tableau
   imports integers as measures, and the committed workbook uses both as dimensions.
5. Right-click `Lat` > **Geographic Role > Latitude**, and `Lon` >
   **Geographic Role > Longitude**. Halifax communities and districts are not
   built-in geographic roles, so the map binds to these two columns, not to a name.

### Sheet 1: Permit Map

1. Rename the sheet `Permit Map`.
2. Double-click `Lon`, then `Lat`. They land as `AVG(Lon)` on **Columns** and
   `AVG(Lat)` on **Rows**, both continuous.
3. Set the Marks type to **Circle**.
4. Drag `Permit Number` to **Detail**. That splits the single averaged point into one
   mark per permit.
5. Drag `Work Type` to **Color**. Three values: New Building, Renovation, Addition.
6. Drag `Project Value` to **Size**. Confirm the pill reads `SUM(Project Value)`.
7. Drag `Issue Year` to **Filters** and tick 2020 through 2026, then right-click the
   pill and choose **Apply to Worksheets > All Using This Data Source**. That one
   filter is what drives both sheets on the dashboard.

Permits with no geolocated match (92 across the whole mart) keep every attribute but
cannot be placed, so they are dropped from this view only.

### Sheet 2: Net new units by district

1. New worksheet, rename it `Net new units by district`.
2. Drag `Issue Year` to **Columns**. It stays discrete (blue).
3. Drag `Net New Units` to **Rows**, confirming `SUM(Net New Units)`.
4. Drag `District` to **Color**. Sixteen districts plus Unidentified.
5. Right-click the `SUM(Net New Units)` pill > **Quick Table Calculation >
   Running Total**, then open **Edit Table Calculation** and choose **Compute Using >
   Specific Dimensions**. Tick `Issue Year` and leave `District` unticked. `District`
   then partitions the calculation, so each district accumulates along the years
   instead of the total running across districts.
6. Set the Marks type to **Area**, which stacks the per-district running totals.
7. The Issue Year filter from Sheet 1 already applies here, because it was set to all
   worksheets using this data source. Do not add a second copy.

The committed workbook has no calculated fields. The running total is the built-in
table calculation, nothing else.

### Dashboard

1. **New Dashboard**, named `Permits`. Size: **Automatic**.
2. Drag `Permit Map` into the top half and `Net new units by district` below it.
3. Move the cards into a fixed strip on the right of the map, 160 pixels wide, in this
   order: the `Issue Year` filter, the `Project Value` size legend, the `Work Type`
   colour legend, and the `District` colour legend.
4. Tableau auto-generates a Phone layout that stacks the filter, the map, the two map
   legends, the area chart, and the district legend in one vertical flow. The committed
   workbook keeps it.

### Publish and file the artifacts

Tableau Public Desktop has no local save. **File > Save** and **File > Save As** both
redirect to **Save to Tableau Public As**, which uploads to the Tableau Public cloud,
so getting a committable `.twb` runs through the cloud and a `.twbx` unzip.

1. **File > Save to Tableau Public As**, sign in, and name it
   `Halifax Building Permit Pulse`. Publishing uploads the extract and opens the viz
   in a browser at the live link above.
2. On the viz page, click **Download Workbook**. It always downloads as a `.twbx`
   (packaged), never a bare `.twb`.
3. A `.twbx` is a zip. Copy it, rename the copy to `.zip`, unzip it, and take the
   `.twb` from the archive root. Commit that file as
   `bi/tableau/building_permit_pulse.twb`. Never commit the `.twbx`: the packaged
   extract duplicates the data, bloats the repo, and does not diff.
4. Screenshots go in `bi/tableau/screenshots/`. The committed capture is
   `dashboard-full.png`.

---

## Power BI guide: decomposition and ranking

### What this report shows

Where declared value concentrates. Three cards carry the filtered totals, a slicer
picks the issue year, a decomposition tree breaks total declared value down by work
type, then community, then year, and a bar chart ranks the top 15 communities by
declared value with the rank and the year-over-year change in the tooltip.

### Import and type the data

1. **Get Data > Text/CSV**, choose `bi/exports/mart_permits.csv`, then
   **Transform Data**.
2. Set the column types:
   - `permit_number`, `community`, `district`, `work_type`, `primary_work_scope`,
     `permit_status` = Text
   - `issue_year`, `issue_month`, `net_new_units`, `storeys` = Whole Number
   - `project_value`, `lat`, `lon` = Decimal Number
3. **Close & Apply**. The table lands as `mart_permits`.
4. Add a page-level filter on `issue_year`, **Advanced filtering > is not blank**. That
   drops the records with no issuance date, which is what the golden rollups do.

There is no date table in this model. The mart carries `issue_year` and `issue_month`
as integers, not a date column, so the year measures index the year directly.

### Measures (enter each verbatim)

    Total Value = SUM ( mart_permits[project_value] )

    Permit Count = COUNTROWS ( mart_permits )

    Net New Units = SUM ( mart_permits[net_new_units] )

    Latest Year = CALCULATE ( MAX ( mart_permits[issue_year] ), ALL ( mart_permits ) )

    Value Prev Year = VAR y = MAX ( mart_permits[issue_year] ) RETURN CALCULATE ( [Total Value], REMOVEFILTERS ( mart_permits[issue_year] ), mart_permits[issue_year] = y - 1 )

    Value YoY = VAR p = [Value Prev Year] RETURN IF ( ISBLANK ( p ), BLANK ( ), [Total Value] - p )

    Community Rank = RANKX ( ALLSELECTED ( mart_permits[community] ), [Total Value], , DESC, Skip )

Set `Permit Count`, `Net New Units`, `Latest Year`, and `Community Rank` to whole
number with 0 decimal places. `Total Value`, `Value Prev Year`, and `Value YoY` stay
general number. `Latest Year` is in the model and is not placed on the page; it reads
the highest issue year in the mart regardless of the slicer.

### Visuals

- **Card**, `[Total Value]`. Set **Callout value > Display units** to None and decimal
  places to 2, otherwise the card abbreviates and the cents are lost.
- **Card**, `[Permit Count]`.
- **Card**, `[Net New Units]`.
- **Slicer** on `issue_year`, set to **Dropdown** mode, with 2025 selected.
- **Decomposition tree**. Analyze = `[Total Value]`. Explain by, in order, `work_type`,
  `community`, `issue_year`. Sort by `[Total Value]` descending, 3 bars per level. The
  committed report saves it expanded into New Building, then HALIFAX.
- **Clustered bar chart** titled `Top 15 communities by declared value`. Category =
  `community`, Values = `[Total Value]`, Tooltips = `[Community Rank]` and
  `[Value YoY]`. Add a **Top N** filter on `community`: Top 15 by `[Total Value]`, and
  sort descending.

### Save and file the artifacts

1. Turn on the project save format: **File > Options and settings > Options > Preview
   features > Power BI Project (.pbip) save option**, then restart if prompted.
2. **File > Save As**, pick **Power BI project files (.pbip)**, and save into
   `bi/powerbi/` as `building_permit_pulse.pbip`. Commit that file together with its
   `building_permit_pulse.Report/` and `building_permit_pulse.SemanticModel/` text
   folders. Never commit a `.pbix`: the binary duplicates the data and does not diff.
3. Free Power BI Desktop has no public link, so the deliverable is the committed
   project plus an exported PNG or **File > Export > PDF**. The committed capture is
   `bi/powerbi/screenshots/report.png`.

---

## Numbers must match

Total declared project value for issue year 2025 is **3,856,416,602.50**. It reads the
same three ways.

- **SQL golden.** In `expected/permits_by_year_worktype.csv`, the `total_project_value`
  column on the three 2025 rows: Addition 148,071,169.70, New Building
  3,403,082,233.80, Renovation 305,263,199.00. They sum to 3,856,416,602.50. The same
  file's `permit_count` for 2025 sums to 3,100 and `total_net_new_units` to 11,793.
- **Tableau.** On the `Permits` dashboard, set the Issue Year filter to 2025 only. The
  `Permit Map` plots 3,089 of the 3,100 permits and its `SUM(Project Value)` totals
  3,845,716,602.50, because 11 of the 2025 permits carry no coordinates and cannot be
  placed. Those 11 are the 10,700,000.00 difference. To read the full
  3,856,416,602.50 in Tableau, put `Project Value` on **Text** in a view that carries
  no `Lat` or `Lon`.
- **Power BI.** With the `issue_year` slicer on 2025, the `[Total Value]` card reads
  3,856,416,602.50, the `[Permit Count]` card 3,100, and the `[Net New Units]` card
  11,793. No visual on the page uses `lat` or `lon`, so nothing is dropped.

If any of these figures differs, the loaded CSV is stale. Re-run `python run.py` from
the project folder, then refresh the Tableau extract and reload the Power BI table.
