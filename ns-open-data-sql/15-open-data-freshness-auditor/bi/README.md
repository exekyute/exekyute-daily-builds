# Power BI build guide: Open Data freshness report

This guide turns `bi/exports/mart_freshness.csv` into a one-page Power BI report: KPI cards for the portal-wide staleness rate, a stacked bar of freshness buckets by category, a category-by-owner matrix with a conditional format on the stale share, and a worst-offenders table. Every step is written out, including the DAX, so the report can be rebuilt from scratch without guessing.

## Why Power BI for this data

The mart is one flat table with one row per catalogued asset, and the report this data wants is aggregation-shaped: a headline percentage, bucket counts split by category, and a category-by-owner grid where each cell carries its own stale share. That grid is Power BI's matrix visual with a DAX measure evaluated per cell, and the KPI cards reuse the same measures. One tool covers the whole report, and nothing depends on when it gets built: the SQL pipeline is complete and verified on its own, so the visual layer can be added later by following this guide.

## Prerequisites

- **Power BI Desktop**, free from the Microsoft Store. No sign-in, service account, or tenant is needed to build, save, and export locally.
- Enable the project save format: File > Options and settings > Options > Preview features > check **Power BI Project (.pbip) save option**, then restart Power BI Desktop. This makes the report saveable as text-based folders that belong in git.
- The free deliverable is the committed `.pbip` project plus exported PNG or PDF screenshots. Publish to web is not available on the free tier, so the screenshots are the shareable output.
- Run `python run.py` in the project folder first so `bi/exports/mart_freshness.csv` exists and is current.

## Step 1: Connect to the mart

1. Open Power BI Desktop > **Get Data** > **Text/CSV**.
2. Browse to this project's `bi/exports/mart_freshness.csv` and select it.
3. In the preview dialog, click **Transform Data** (not Load) to set the column types explicitly in Power Query.
4. Set each column's type from the header row:

   | Column | Type |
   | --- | --- |
   | `uid` | Text |
   | `name` | Text |
   | `type` | Text |
   | `category` | Text |
   | `owner` | Text |
   | `last_updated` | Date |
   | `age_months` | Whole Number |
   | `bucket` | Text |
   | `bucket_order` | Whole Number |
   | `stale_or_dormant` | Whole Number |

5. Confirm the query name is `mart_freshness`, then **Close & Apply**.

## Step 2: Model settings

1. In Report view, select the `bucket` column in the Data pane, then **Column tools > Sort by column > bucket_order**. This makes every visual show buckets in age order (Fresh, Aging, Stale, Dormant, No date) instead of alphabetical.
2. Optional tidy-up: right-click `bucket_order` and `stale_or_dormant` and choose **Hide in report view**. The measures still read them.

## Step 3: Measures

Create each measure on the `mart_freshness` table (Modeling > New measure), pasted verbatim:

```
Total Assets = COUNTROWS ( mart_freshness )
```

```
Stale or Dormant Assets =
CALCULATE (
    COUNTROWS ( mart_freshness ),
    mart_freshness[stale_or_dormant] = 1
)
```

```
Pct Stale or Dormant =
DIVIDE ( [Stale or Dormant Assets], [Total Assets] )
```

```
Avg Age Months = AVERAGE ( mart_freshness[age_months] )
```

Format `Pct Stale or Dormant` as a percentage with one decimal (Measure tools > Format > Percentage). Format `Avg Age Months` as a decimal number with one decimal.

## Step 4: Visuals

**(1) KPI cards.** Insert three Card visuals across the top of the page:

- Card 1: `Pct Stale or Dormant`
- Card 2: `Total Assets`
- Card 3: `Avg Age Months`

**(2) Stacked bar of buckets by category.** Insert a **Stacked bar chart**:

- Y-axis: `category`
- X-axis: Count of `uid`
- Legend: `bucket`

Because of the sort-by column from Step 2, the legend runs Fresh through No date. Sort the bars by total count descending (visual header > More options > Sort axis).

**(3) Category-by-owner matrix.** Insert a **Matrix**:

- Rows: `category`
- Columns: `owner`
- Values: `Pct Stale or Dormant`

Add the conditional format: with the matrix selected, Format pane > **Cell elements** > Series `Pct Stale or Dormant` > turn **Background color** on > **fx** > Format style **Gradient**, based on field `Pct Stale or Dormant`, lowest value white, highest value a red. Cells where every asset is stale or dormant read 100.0% on solid red; healthy cells stay near white.

**(4) Worst-offenders table.** Insert a **Table** with `name`, `owner`, `category`, `last_updated`, `age_months`, `bucket`. Then:

- Sort by `age_months` descending (click the column header).
- In the Filters pane, filter this visual to `type` **is** `dataset`, so the list matches the audit's worst-offenders rule (public datasets only, not charts or views built on them).

**(5) Bucket slicer.** Insert a **Slicer** with `bucket`. The Step 2 sort order applies here too. Clicking Dormant filters the whole page to the worst assets.

**Layout.** Cards in a row across the top, stacked bar on the left half, matrix on the right half, worst-offenders table across the bottom, slicer in the top-right corner beside the cards. Leave breathing room between visuals rather than packing them edge to edge.

## The numbers must match

The verified SQL run is the reference. Per `expected/freshness_audit.csv`, the portal has **1,269** audited assets and **51.6 percent** of them are stale or dormant (655 assets with no data update in 12 months or more, measured against the pinned pull date 2026-07-06). The finished report must read identically: the `Pct Stale or Dormant` card shows 51.6% and the `Total Assets` card shows 1,269 (set the card's display units to None if it abbreviates to 1.27K). If either differs, re-check the Step 1 column types and confirm no report-level filter is active.

## Save, commit, screenshot

1. **File > Save As**, choose the `.pbip` format, and save as `freshness_report` into `bi/powerbi/`. Power BI writes a `freshness_report.pbip` pointer plus `freshness_report.Report/` and `freshness_report.SemanticModel/` folders.
2. Commit the `.pbip` file and both folders. A `.pbix` binary does not get committed (the repo's `.gitattributes` already treats it as binary if one ever appears). The machine-local editor state under each `.pbi/` folder (`localSettings.json`, `editorSettings.json`, `cache.abf`) is gitignored, since it holds encrypted per-user bindings rather than the report itself.
3. Export the finished page for the repo: **File > Export > Export to PDF**, or screenshot the page as PNG. Save the exports into `bi/powerbi/screenshots/`.

The committed semantic model stores the source as a repo-relative path (`bi\exports\mart_freshness.csv`) rather than an absolute one. Power BI saves the absolute path you browsed to, so after saving, open `freshness_report.SemanticModel/definition/tables/mart_freshness.tmdl` and shorten that `File.Contents(...)` path back to the relative form. To refresh the data on another machine, repoint it at your local copy of the CSV.
