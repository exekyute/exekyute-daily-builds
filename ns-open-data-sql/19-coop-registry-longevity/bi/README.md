# BI layer: co-op registry longevity

A step-by-step manual build. The SQL pipeline in this project is complete and
verified on its own; this guide adds a report over the exported mart. Follow it
top to bottom in Power BI Desktop, then commit the .pbip project and an exported
image per the last two sections.

## Why Power BI for this data shape

The result here is a cohort matrix (incorporation decades down the side, the
organizational-form split across it) sitting next to a time series of
incorporations by year. That is the shape Power BI's matrix visual and DAX
measures handle natively: the mart stays row-level (one row per co-op), the
measures compute counts and shares in the filter context of each matrix cell
without any precomputed pivot. A spreadsheet would need the pivot baked in; here
the same few measures drive every visual on the page. Power BI is the only BI
tool in this project, and this guide can be followed any time after the fact.

## Prerequisites

1. **Power BI Desktop**, free from the Microsoft Store. No licence, tenant, or
   sign-in is needed to author and save locally.
2. **Enable the .pbip save format:** File > Options and settings > Options >
   Preview features > check **Power BI Project (.pbip) save option**, then
   restart Power BI Desktop.
3. Run `python run.py` in the project folder first so
   `bi/exports/mart_coop_longevity.csv` is freshly generated and verified.
4. The deliverable is the committed .pbip project plus an exported PNG or PDF in
   `bi/powerbi/screenshots/`. Publish to web is not available on the free tier,
   so the exported image is the shareable artifact.

## Connect the data

1. Open Power BI Desktop, **Get Data > Text/CSV**.
2. Pick `bi/exports/mart_coop_longevity.csv` from this project folder.
3. In the preview dialog choose **Transform Data** (not Load), because two
   column types need pinning.
4. In Power Query, set the types exactly:

   | Column | Type |
   |---|---|
   | `registry_id` | Text (Power Query auto-detects Whole Number; change it, these are identifiers) |
   | `co_op_name` | Text |
   | `town` | Text |
   | `incorporation_date` | Date |
   | `incorporation_year` | Whole Number |
   | `decade` | Text |
   | `org_form` | Text |
   | `is_nonprofit` | Whole Number |
   | `coop_type` | Text |
   | `age_years` | Decimal Number |

5. **Close & Apply.** The model now has one table, `mart_coop_longevity`,
   369 rows, Import mode.
6. One model tweak: select `incorporation_year` in the Data pane and set
   **Summarization: Don't summarize**, so charts treat it as an axis, not a sum.

## Measures

Home > New measure, once per measure, verbatim:

    Total Registered = COUNTROWS(mart_coop_longevity)

    Non-profit Count =
    CALCULATE(
        COUNTROWS(mart_coop_longevity),
        mart_coop_longevity[is_nonprofit] = 1
    ) + 0

    For-profit Count =
    CALCULATE(
        COUNTROWS(mart_coop_longevity),
        mart_coop_longevity[is_nonprofit] = 0
    ) + 0

    Non-profit Share =
    DIVIDE([Non-profit Count], COUNTROWS(mart_coop_longevity))

    Registry Share =
    DIVIDE(
        COUNTROWS(mart_coop_longevity),
        CALCULATE(COUNTROWS(mart_coop_longevity), ALL(mart_coop_longevity))
    )

    Oldest Age Years = MAX(mart_coop_longevity[age_years])

Format `Non-profit Share` and `Registry Share` as **Percentage, 1 decimal
place** (Measure tools ribbon). Format `Oldest Age Years` as **Decimal number,
1 decimal place**.

The `+ 0` on the two count measures is deliberate. `CALCULATE` returns blank
when no row matches, and the 1930s through 1950s cohorts hold no non-profits at
all. Without the `+ 0` those cells render empty instead of 0, which reads as
missing data rather than a real zero.

This registry carries no status column (every row is a registered, surviving
co-op), so the share measures have no active/inactive filter to divide by.
`Registry Share` is each cohort's slice of today's registry and
`Non-profit Share` is the mix inside a cohort; both use the same
DIVIDE-over-CALCULATE pattern a percent-still-active measure would.

## Build the report page

Work on one page. The grid below assumes the default 16:9 canvas; snap edges to
match.

### 1. Column chart: incorporations by year

- Insert a **Clustered column chart**, top band of the canvas, full width (about
  the top 30 percent).
- X-axis: `incorporation_year`. Y-axis: `Total Registered`.
- X-axis type: **Categorical** is fine (years with zero incorporations simply
  do not appear; the mart only carries surviving co-ops).
- Title: `Incorporations by year, co-ops still registered`.
- Expect a long thin left tail from 1936 and a heavy right side; the tallest
  column is 2011 at 16.

### 2. Cohort matrix: the survivorship table

- Insert a **Matrix**, bottom left quarter.
- Rows: `decade`. Leave **Columns empty**. Values, in this order:
  `Total Registered`, `Non-profit Count`, `For-profit Count`,
  `Non-profit Share`. That mirrors the golden CSV column for column.
- Do not put `org_form` on Columns. `Non-profit Share` would then be evaluated
  inside each org_form column, where it reads 100 percent on every non-profit
  cell and blank on every for-profit cell. The split already lives in the two
  count measures.
- Matrix style: default is fine; turn **Row subtotals on** (the Total row is
  the whole registry, 369).
- Optional, and not in the committed report: conditional formatting on the share
  column. Select the matrix, Format pane > **Cell elements**, choose
  `Non-profit Share` in the "Apply settings to" series dropdown, switch
  **Background color** on, then set an Fx gradient from white at the minimum to a
  solid theme colour at the maximum. It paints the mix flip, since the pre-1960
  cohorts sit at 0.0 percent and the 1980s at 82.3.
- Title: `Cohort survivorship and non-profit mix`.

### 3. Line chart: each cohort's share of the registry

- Insert a **Line chart**, middle band, full width.
- X-axis: `decade`. Y-axis: `Registry Share`.
- Sort the axis chronologically: the visual's **...** menu > **Sort axis** >
  `decade` > **Sort ascending**. Power BI defaults to sorting by the measure,
  which turns the series into a downhill slope that is an artifact of sorting
  and not a trend. Decade labels are four digits plus `s`, so alphabetical
  ascending is chronological.
- Title: `Share of today's registry by incorporation decade`.
- Expect a low start (2.7% for the 1930s, under 1% for the 1950s) climbing to a
  23.8% peak at the 2010s.

### 4. KPI cards

- Insert three **Card** visuals across the bottom right, stacked or side by side:
  1. `Total Registered`, label it `Co-ops registered`. Reads **369**.
  2. `Non-profit Share`, label it `Non-profit share`. Reads **65.3%**.
  3. `Oldest Age Years`, label it `Oldest co-op (years)`. Reads **90.3**.

### 5. Slicer

- Insert a **Slicer**, right edge, set to `org_form` (the closest thing this
  registry has to a status field). Style: **Vertical list**.
- Optional second slicer on `coop_type` to cut every visual by sector.

## Numbers match

With no slicer selection, the finished report must read identically to the
golden output in `expected/coop_longevity.csv`:

- `Co-ops registered` card: **369**
- `Non-profit share` card: **65.3%**
- `Oldest co-op (years)` card: **90.3**
- Matrix row `1930s`: 10 total, 0 non-profit, 10 for-profit, share 0.0%
- Matrix row `1980s`: 62 total, 51 non-profit, 11 for-profit, share 82.3%
- Matrix Total row: 369 total, 241 non-profit, 128 for-profit, share 65.3%
- Line chart `2010s` point: 23.8%
- Column chart tallest bar: 2011 at 16

If any figure differs, re-run `python run.py` (it must print PASS), refresh the
data in Power BI (Home > Refresh), and re-check the column types from the
Connect step before touching any visual.

## Save as .pbip and commit

1. **File > Save as**, navigate into `bi/powerbi/` in this project, name it
   `coop_longevity`, and pick **Power BI Project files (*.pbip)** as the type.
2. That writes `coop_longevity.pbip` plus the `coop_longevity.Report/` and
   `coop_longevity.SemanticModel/` folders. All three are text and get
   committed.
3. A `.pbix` (if one was saved earlier during the build) does not get committed.
4. Before committing, open
   `coop_longevity.SemanticModel/definition/tables/mart_coop_longevity.tmdl` and
   find the `Source = Csv.Document(File.Contents("..."))` line. Power BI bakes
   in the full absolute path you browsed to, including your user folder. Replace
   it with the repo-relative path `bi\exports\mart_coop_longevity.csv`. The
   project still opens; only a live data refresh needs the path repointed.
5. The `.pbi/` folders inside both project folders hold machine-local state
   (encrypted settings and a binary cache). They are gitignored, not committed.

## Export the image

1. **File > Export > Export to PDF**, or take a full-window screenshot of the
   finished page.
2. Save it into `bi/powerbi/screenshots/` as `coop_longevity.png` and commit it
   alongside the .pbip project.
