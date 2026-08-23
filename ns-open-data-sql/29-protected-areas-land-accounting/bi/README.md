# Power BI build guide: protected-areas land accounting

This folder holds the BI face of the land accounting. The SQL pipeline is the
single brain: it computes every number and exports one mart,
`bi/exports/mart_protected.csv`. Power BI reads that mart and re-derives the
same figures; it never recomputes a cleaning rule. When the report is built, its
headline numbers must match the golden output to the hundredth of a hectare.

## Why Power BI for this data

Two of the questions here are measure patterns rather than chart options. A
cumulative hectare curve needs a running total that walks an ordered index and
re-evaluates its own filter context at every point, and a
designation-by-authority breakdown needs one measure to hold across a
two-dimensional matrix without being rewritten per cell. That is the DAX
running-total face, and Power BI is where it is cheapest to build. This is a
single-tool build by deliberate selection: the SQL base build is complete and
verified on its own, and because the mart is frozen alongside the golden output,
you can backfill this report any time after the fact and get the same numbers.

## Prerequisites

Power BI Desktop, free from the Microsoft Store. Enable File > Options > Preview
features > "Power BI Project (.pbip) save option". No service account and no
tenant is needed. The free deliverable is the committed .pbip plus exported PNG
or PDF, because Publish to web is not available on the free tier. Commit the
.pbip .Report and .SemanticModel text folders. Never commit a .pbix.

## Read this before you build the cumulative line

The mart deliberately carries an integer `designation_year` and **no date
column of any kind**. So the running total below uses the year-index pattern:
grab the current index with `MAX`, then filter the column to everything at or
below it. Do not reach for time-intelligence functions such as `DATESYTD`,
`TOTALYTD`, `DATEADD`, or `SAMEPERIODLASTYEAR`. They need a table marked as a
date table, and without one they return blank silently rather than erroring, so
the chart looks built and reads wrong.

There is a second thing to know, and it is a property of the province's data
rather than of this build. `stat_date`, the source's designation year, is empty
in **all 1,161 records** of the current publication, so `designation_year` is
empty in every row of the mart. A cumulative line drawn over `designation_year`
ends below the total-hectares KPI by exactly the hectares with no designation
year, and here that shortfall is **743,084.11 ha, the entire total**. The line
would be blank. That is a coverage fact, not a defect in the model, and spec.md
records it in both records and hectares.

So the cumulative line this guide builds runs over `record_rank` instead, the
integer index that ranks records largest hectares first. It answers a real
question about protected land, which is how few parcels hold most of it, and it
ends exactly on the KPI. Step 3 also gives the same measure written over
`designation_year`, so the day the province refills `stat_date` you re-pull,
re-baseline, and swap one measure.

## Step 1: connect to the mart

1. Home > **Get Data** > **Text/CSV**.
2. Browse to `bi/exports/mart_protected.csv` inside this project folder.
3. In the preview dialog choose **Transform Data** (not Load) so you can set
   types explicitly.
4. In Power Query, set each column type by clicking its type icon:

   | Column | Type |
   | --- | --- |
   | objectid | Whole Number |
   | area_name | Text |
   | designation | Text |
   | authority | Text |
   | owner | Text |
   | status | Text |
   | hectares | **Fixed decimal number** |
   | designation_year | Whole Number |
   | record_rank | Whole Number |

   Fixed decimal number is the one that keeps hectares exact to two decimals; do
   not leave `hectares` as plain Decimal Number. Power Query will type
   `designation_year` as Text or Any because every value is blank. Set it to
   Whole Number by hand so the column is ready when the source refills.
5. **Close & Apply**. Connection mode is Import, the default for CSV; nothing
   here needs DirectQuery.

## Step 2: KPI cards

Modeling > New measure, once per measure.

```DAX
Total Hectares = SUM ( mart_protected[hectares] )
```

```DAX
Protected Records = COUNTROWS ( mart_protected )
```

```DAX
All Selected Hectares =
CALCULATE ( [Total Hectares], ALLSELECTED ( mart_protected ) )
```

Format `Total Hectares` and `All Selected Hectares` as Decimal number with 2
decimal places and the thousands separator on. Format `Protected Records` as
Whole number with the thousands separator on.

Insert two **Card** visuals: one for `Total Hectares`, one for
`Protected Records`. With the slicer cleared they must read **743,084.11** and
**1,161**.

`All Selected Hectares` is the denominator for the cumulative share. It follows
the designation slicer you add in Step 6 but ignores the visual's own row
grouping, so the running share still reaches 100 percent at the last record of
whatever the slicer selected.

## Step 3: the cumulative hectares line

```DAX
Cumulative Hectares =
VAR CurrentIndex = MAX ( mart_protected[record_rank] )
RETURN
    CALCULATE (
        [Total Hectares],
        REMOVEFILTERS ( mart_protected[record_rank] ),
        mart_protected[record_rank] <= CurrentIndex
    )
```

```DAX
Cumulative Share % =
DIVIDE ( [Cumulative Hectares], [All Selected Hectares] )
```

Format `Cumulative Hectares` as Decimal number, 2 decimals. Format
`Cumulative Share %` as Percentage, 2 decimals.

Build the visual:

1. Insert a **Line chart**.
2. X-axis: `record_rank`. Y-axis: `Cumulative Hectares`. Add
   `Cumulative Share %` as a secondary line if you want both scales.
3. X-axis type must be **Categorical**, not Continuous, or Power BI will bin the
   ranks and the curve will step. Format pane > X axis > Type > Categorical.
4. Sort ascending by `record_rank`: visual header **More options (...)** > Sort
   axis > `record_rank` > Sort ascending.
5. All 1,161 ranks on one axis is a dense but honest curve. To match the golden
   `concentration` section instead, open the Filters pane, drop `record_rank` on
   the visual, filter type **Advanced filtering**, `is less than or equal to`
   25, Apply.

The curve rises steeply and then flattens: rank 1 alone is 103,645.77 ha, rank
11 crosses half the total, and rank 103 crosses ninety percent. At rank 1,161 it
reads **743,084.11**, the same number as the KPI card. That equality is the
check that the running total is filtering correctly.

Here is the same measure over the year axis, unchanged in shape. Keep it in the
model as a comment or a hidden measure; it returns blank against this snapshot
because `designation_year` has no values, and it becomes correct the moment the
province republishes `stat_date`:

```DAX
Cumulative Hectares by Year =
VAR CurrentYear = MAX ( mart_protected[designation_year] )
RETURN
    CALCULATE (
        [Total Hectares],
        REMOVEFILTERS ( mart_protected[designation_year] ),
        mart_protected[designation_year] <= CurrentYear
    )
```

## Step 4: hectares by designation type

1. Insert a **Treemap**. Category: `designation`. Values: `Total Hectares`.
2. A bar chart works too and is easier to read exactly: **Clustered bar chart**,
   Y-axis `designation`, X-axis `Total Hectares`, sorted by `Total Hectares`
   descending. Use the treemap when the point is proportion, the bar when the
   point is the numbers.
3. Add a share measure so the tooltip carries proportion:

```DAX
Share of Protected Hectares % =
DIVIDE ( [Total Hectares], [All Selected Hectares] )
```

Format as Percentage, 2 decimals, and drop it into the visual's Tooltips well.

Thirteen designation labels come through, compound ones included. The largest
tile is **Wilderness Area at 528,920.74 ha, 71.18 percent**. Compound labels such
as `Wilderness Area, Conservation Easement` are their own tiles on purpose, so no
hectare is counted under two designations. Do not split them in Power Query.

## Step 5: the authority by designation matrix

1. Insert a **Matrix**. Rows: `authority`. Columns: `designation`. Values:
   `Total Hectares`.
2. Format pane > Row headers > Word wrap **On**. Some authority labels are
   compound and long.
3. Format pane > Subtotals: leave row and column grand totals **On**. The
   bottom-right grand total is the third place the report has to read
   743,084.11.
4. 25 authorities by 13 designations gives 325 cells and only 35 of them carry
   land, so most of the matrix is blank. That is the finding, not a rendering
   problem: authorities specialize, and one authority holds most of one
   designation.

Spot check: **NS Environment and Climate Change** crossed with **Wilderness
Area** must read **526,417.12**.

## Step 6: slicer, layout, formatting

- Add a **Slicer** with `designation`, dropdown style. Every measure routes
  through `All Selected Hectares`, so the whole page follows the slicer
  together.
- Suggested layout: the two cards top-left, the treemap top-right, the
  cumulative line across the middle, the matrix along the bottom, slicer above
  the cards.
- Sweep the formatting: every hectare field Decimal number with 2 decimals and
  thousands separators, every percent 2 decimals. The report reads to the
  hundredth of a hectare or it is not done.
- Page title: "NS Protected Areas, land accounting at 2026-07-25".
- Optional third card, share of provincial land. It needs the provincial land
  area, which is a named constant living in `sql/02_transform.sql` and cited in
  spec.md. Putting it in DAX gives that constant a second home, so if you add
  the card, copy the value and the citation together:

```DAX
Share of Provincial Land % =
VAR NSLandAreaHa = 5333800    -- Statistics Canada, land area only; see spec.md
RETURN
    DIVIDE ( [Total Hectares], NSLandAreaHa )
```

  Formatted as Percentage with 2 decimals it reads **13.93%**.

## Numbers-match check

With the designation slicer cleared, the finished report must read identically
to the golden output:

- Total Hectares card: **743,084.11**
- Protected Records card: **1,161**
- Cumulative line at record_rank 1,161: **743,084.11**
- Largest treemap tile: **Wilderness Area, 528,920.74**
- Matrix grand total: **743,084.11**
- Matrix spot check: NS Environment and Climate Change crossed with Wilderness
  Area = **526,417.12**

If any figure differs, the mart import or a measure is wrong; the SQL golden is
the arbiter.

## Step 7: save and export

1. **File > Save as**, navigate into `bi/powerbi/`, and save as
   `protected-areas-land-accounting` with save type **Power BI project files
   (*.pbip)**. Desktop writes `protected-areas-land-accounting.pbip` plus
   `protected-areas-land-accounting.Report/` and
   `protected-areas-land-accounting.SemanticModel/` folders; all of that is text
   and gets committed.
2. Export visuals: **File > Export > Export to PDF** into
   `bi/powerbi/screenshots/`, or take PNG screenshots of the report page into
   the same folder.
3. Do not commit any `.pbix`. The repo's `.gitignore` already excludes it and
   `.gitattributes` marks the folder vendored if one appears by accident.
