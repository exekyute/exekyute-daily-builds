# BI build guides: capital investment map

Both dashboards read one frozen file, `bi/exports/mart_capital.csv`. One row is
one capital-project record: one project at one location in one budget year, 2,650
rows covering 2013 to 2021. Neither tool recomputes the analysis; both aggregate
that mart as written, so a figure read off the Tableau dashboard equals the same
figure in Power BI and in the SQL golden. The dataset carries no dollar field, so
every measure below is a count of records, never a sum of money. Column meanings
and BI types are in `bi/exports/data_dictionary.md`.

Tableau live link: https://public.tableau.com/views/HalifaxCapitalInvestmentMap/Capitalinvestment

- [Tableau guide](#tableau-guide-point-map-and-area-chart)
- [Power BI guide](#power-bi-guide-decomposition-tree-and-ranking)
- [Numbers must match](#numbers-must-match)

---

## Tableau guide: point map and area chart

### What this dashboard shows

Where the capital projects are and how their category mix moves through the
budget years. A point map plots every project record at its latitude and
longitude, coloured by normalized category. Below it, a stacked area chart counts
project records by category across the years. One budget-year filter drives both.

### Prerequisites

- Tableau Public Desktop Edition, free from https://public.tableau.com (Download
  on the top nav). Install with defaults.
- A free public.tableau.com account (Sign Up on the same page). Vizzes published
  from Tableau Public are public, which is fine here: the source is open data.
- Tableau Public works extract-only from files. It loads the CSV into an extract
  when you publish, and needs no database connection.

### Connect the data

1. Open Tableau Public. Under **Connect > To a File**, click **Text file**.
2. Browse to this repo's `bi/exports/mart_capital.csv` and open it. The committed
   workbook stores this connection as a relative text-scan directory of
   `../exports`, so it reopens against the repo copy in place.
3. Check the field types Tableau inferred on the data source page:
   - `proj_no`, `proj_name`, `loc_desc`, `work_desc`, `category`,
     `category_norm`, `asset_type` are strings (Abc icon).
   - `year` is a whole number (#), so Tableau imports it as a measure. Right-click
     it in the data pane and choose **Convert to Dimension**. The committed
     workbook stores `year` as a dimension and keeps it continuous, so if the
     field turns blue on conversion, right-click it again and choose
     **Continuous**. Sheet 1 filters on it continuous; Sheet 2 switches the
     Columns pill to discrete.
   - `lat` and `lon` are decimal numbers (#).
4. Give the coordinates their geographic roles: right-click `lat` >
   **Geographic Role > Latitude**, and `lon` > **Geographic Role > Longitude**.
   The committed workbook carries `semantic-role` Latitude on `lat` and Longitude
   on `lon`, and aggregates both as **Avg**.
5. Leave the connection on **Extract**. Click **Sheet 1** to start building.

### Sheet 1: Project map

Every project record as a point, coloured by category.

1. Rename the sheet `Project map`.
2. Drag `lon` to **Columns** and `lat` to **Rows**. Both pills should read
   `AVG(lon)` and `AVG(lat)`. Tableau draws its background map behind them.
3. Set the Marks type to **Circle**.
4. Drag `category_norm` to **Color**. That is the 16-value normalized category, so
   the legend has 16 entries.
5. Drag `proj_name` to **Tooltip**. The committed workbook holds it as
   `ATTR(proj_name)`, which is what Tableau produces when a dimension lands on
   Tooltip in this view.
6. On the Color card, set opacity to about 70 percent and turn on **Border**,
   white. Dense downtown clusters then read as overlapping points rather than one
   solid mass.
7. Under **Map > Map Layers**, set Washout to 0 so the base map stays at full
   contrast under the marks.
8. Drag `year` to the **Filters** shelf. Because it is a continuous dimension the
   dialog opens straight on **Range of Values** with no aggregation prompt. Leave
   the range at the full span, **2013 to 2021**; the workbook stores that as
   `in-range-or-null`. Right-click the pill and choose **Apply to Worksheets >
   All Using This Data Source** so the same filter governs Sheet 2. Right-click
   again and choose **Show Filter**.
9. Pan and zoom to frame the municipality. The committed workbook stores a fixed
   map extent, so the framing is saved with the sheet rather than re-fitting on
   open.

There are no calculated fields in this workbook. Both sheets read the mart's
columns directly.

### Sheet 2: Projects by category over years

The category mix, year by year.

1. New worksheet, rename it `Projects by category over years`.
2. Drag `year` to **Columns**. It arrives as a green continuous pill, so open the
   pill's dropdown and choose **Discrete**. The pill turns blue and reads `year`,
   giving one column per budget year with no interpolation between them.
3. Drag `proj_no` to **Rows** and change the aggregation to **Count**, so the pill
   reads `CNT(proj_no)`. Every mart row carries a project number, so the count of
   `proj_no` is the count of project records, not the count of distinct projects.
4. Drag `category_norm` to **Color**.
5. Set the Marks type to **Area**. The categories stack into each year's total.
6. The `year` range filter from Sheet 1 already applies here through
   **All Using This Data Source**. Do not add a second year pill.

### Dashboard

1. Click **New Dashboard** and rename it `Capital investment`.
2. Set Size to **Fixed size, 1200 by 900**.
3. Turn the dashboard title on (**Dashboard > Show Title**).
4. Drag `Project map` in first, then `Projects by category over years` below it.
   The committed layout gives the map roughly two thirds of the height and the
   area chart the remaining third.
5. Put the right rail at a fixed width of 160 pixels and stack two cards in it:
   the `Year` filter card and the `Category Norm` colour legend, both from the
   `Project map` sheet. Because the filter applies to all worksheets using the
   data source, that one card drives both views.
6. Tableau auto-generates a Phone layout for this dashboard. The committed
   workbook keeps it, ordered title, year filter, map, colour legend, area chart.

### Publish and file the artifacts

Tableau Public Desktop has no local Save to disk. **File > Save** and
**File > Save As** both redirect to **Save to Tableau Public As...**, which uploads
to the Tableau Public cloud. Getting the committable `.twb` therefore runs through
the cloud and a `.twbx` unzip.

1. **File > Save to Tableau Public As...**, sign in, and name it
   `Halifax Capital Investment Map`. Publishing uploads the extract and opens the
   viz in a browser. The dashboard lands at the live link above.
2. On the viz page, click **Download Workbook**. It always downloads as a `.twbx`
   (packaged), never a bare `.twb`.
3. A `.twbx` is a zip. Copy it, rename the copy to `.zip`, unzip it, and pull the
   `.twb` from the archive root. Commit that file as
   `bi/tableau/capital_investment_map.twb`. Never commit the `.twbx`: the packaged
   extract duplicates the data, bloats the repo, and does not diff.
4. If the unzipped `.twb` points its text-scan connection at the packaged copy of
   the CSV, repoint the connection directory to `../exports` before committing, so
   the committed workbook reopens against `bi/exports/mart_capital.csv`.
5. Take screenshots into `bi/tableau/screenshots/`. The one the project README
   embeds is `dashboard-full.png`.

---

## Power BI guide: decomposition tree and ranking

### What this report shows

The same 2,650 records read as counts. Two cards give the project total and the
latest budget year, a decomposition tree breaks the count down by category, then
asset type, then year, and a ranked bar chart puts the categories in order with
their rank on the tooltip. A year dropdown slicer filters the page.

### Import and type the data

1. **Get Data > Text/CSV**, choose this repo's `bi/exports/mart_capital.csv`, then
   **Transform Data** to open Power Query. The committed model reads it with a
   comma delimiter, 10 columns, UTF-8 (encoding 65001).
2. Set the column types:
   - `proj_no`, `proj_name`, `loc_desc`, `work_desc`, `category`, `category_norm`,
     `asset_type` = Text
   - `year` = Whole Number
   - `lat`, `lon` = Decimal Number
3. **Close & Apply**. The table lands as `mart_capital`.
4. Select `year` and set **Column tools > Summarization = Don't summarize**, with
   format `0`. It is a budget-year index, not a quantity to add up. There is no
   date column in this mart, so the model has no date table and no time
   intelligence; the year-over-year measure below does its own year arithmetic.

### Measures (enter each verbatim)

    Projects = COUNTROWS ( mart_capital )

    Category Rank = RANKX ( ALLSELECTED ( mart_capital[category_norm] ), [Projects], , DESC, Skip )

    Latest Year = CALCULATE ( MAX ( mart_capital[year] ), ALL ( mart_capital ) )

    Projects Prev Year =
    VAR y = MAX ( mart_capital[year] )
    RETURN CALCULATE ( [Projects], REMOVEFILTERS ( mart_capital[year] ), mart_capital[year] = y - 1 )

    Projects YoY =
    VAR p = [Projects Prev Year]
    RETURN IF ( ISBLANK ( p ), BLANK (), [Projects] - p )

All five carry format string `0`, so set each to Whole number with 0 decimals
(Measure tools > Format). `Latest Year` uses `ALL` so it ignores the year slicer
and always reads the last year in the mart. `Projects Prev Year` and `Projects
YoY` are in the committed model but are not placed on the page; they read a
change against the prior budget year when one year is in context.

### Visuals

The committed report has one page, `Page 1`, 1280 by 720, display option Fit to
page, holding six visuals:

- **Textbox** across the top reading `Halifax capital investment`, Segoe UI
  Semibold, 28pt.
- **Card**, top left, value `[Projects]`, display units None.
- **Card**, beside it, value `[Latest Year]`, display units None.
- **Slicer**, top right, field `mart_capital[year]`, mode **Dropdown**.
- **Decomposition tree**, lower left: Analyze = `[Projects]`, Explain by =
  `category_norm`, then `asset_type`, then `year`, all three active, sorted by
  `[Projects]` descending, with 7 bars per level.
- **Clustered bar chart**, lower right: Y = `[Projects]`, Category =
  `category_norm`, Tooltips = `[Category Rank]`, sorted by `[Projects]`
  descending.

### Save and file the artifacts

1. Turn on the project save format: **File > Options and settings > Options >
   Preview features > Power BI Project (.pbip) save option**, then restart if
   prompted.
2. **File > Save As**, choose **Power BI project files (.pbip)**, and save into
   `bi/powerbi/` as `capital_investment_map`. Commit the `.pbip` file together
   with its `.Report/` and `.SemanticModel/` text folders. Never commit a `.pbix`:
   the binary duplicates the mart and does not diff.
3. Free Power BI Desktop has no public publish link, so the deliverable is the
   committed project plus an exported PNG or **File > Export > PDF** of the page.
   The committed image is `bi/powerbi/screenshots/report.png`.

---

## Numbers must match

With no filters applied, Roads is the largest category at **1,245 projects, 47.0
percent of the 2,650 total**. All three read it the same way:

- **SQL golden**: `expected/category_ranking.csv`, rank 1 row, `projects` column
  reads `1245` and `pct_of_total` reads `47.0`. The `projects` column sums to
  2,650 across all 16 categories.
- **Tableau**: on `Projects by category over years`, with the year filter at its
  full 2013 to 2021 range, the Roads band totals `CNT(proj_no)` 1,245, and all
  bands together total 2,650. The same 2,650 marks plot on `Project map`.
- **Power BI**: the `[Projects]` card reads 2,650, and on the clustered bar the
  top bar is `category_norm` Roads at `[Projects]` 1,245 with `[Category Rank]` 1.
  The decomposition tree's Roads branch holds the same 1,245.

If any tied figure differs, the loaded CSV is stale: re-run `python run.py` from
the project folder, then reconnect the file or refresh the extract.
