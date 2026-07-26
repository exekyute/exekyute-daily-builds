# Power BI build guide: agriculture funding audit

This folder holds the BI face of the audit. The SQL pipeline is the single brain: it computes every number and exports one mart, `bi/exports/mart_funding_audit.csv`. Power BI reads that mart and re-derives the same figures; it never recomputes a cleaning rule. When the report is built, its headline numbers must match the golden output to the cent.

## Why Power BI for this data

This dataset is shaped like a DAX exercise: a Pareto needs a ranked bar with a running cumulative share, the concentration KPI is a TOPN set measured against the whole, and the year-over-year view needs a previous-year measure over a fiscal-year column with no real dates. All three are measure patterns rather than chart options, which is where Power BI is strongest. This is a single-tool build by deliberate selection: the SQL base build is complete and verified on its own, and you can follow this guide any time after the fact.

## Prerequisites

- **Power BI Desktop**, free from the Microsoft Store. No sign-in, licence, or tenant is needed to build and save locally.
- **Enable .pbip saving** if your version still lists it as preview: File > Options and settings > Options > Preview features > check **Power BI Project (.pbip) save option**, then restart Desktop. If the option is not listed, it is already generally available in your version and nothing needs enabling.
- Know the free-tier boundary: Publish to web is not available on a free account, so the shipped deliverable is the committed `.pbip` project plus exported PNG or PDF in `bi/powerbi/screenshots/`. The `.pbix` binary never gets committed.

## Step 1: connect to the mart

1. Home > **Get Data** > **Text/CSV**.
2. Browse to `bi/exports/mart_funding_audit.csv` inside this project folder.
3. In the preview dialog choose **Transform Data** (not Load) so you can set types explicitly.
4. In Power Query, set each column type by clicking its type icon:

   | Column | Type |
   | --- | --- |
   | fiscal_year | Text |
   | fiscal_year_start | Whole Number |
   | division | Text |
   | program_name | Text |
   | recipient | Text |
   | payment_amount | **Fixed decimal number** |
   | is_duplicate_candidate | Whole Number |
   | dup_occurrences | Whole Number |

   Fixed decimal number is the one that keeps money exact to the cent; do not leave payment_amount as plain Decimal Number.
5. **Close & Apply**. Connection mode is Import (the default for CSV); nothing here needs DirectQuery.

## Step 2: base measures

Modeling > New measure, once per measure. Create these two first; everything else builds on them.

```DAX
Total Dollars = SUM ( mart_funding_audit[payment_amount] )
```

```DAX
Base Dollars =
CALCULATE ( [Total Dollars], ALL ( mart_funding_audit[recipient] ) )
```

Format both as currency with 2 decimal places (Measure tools > Format > Currency, 2).

`Base Dollars` is the denominator for every share in this report, and the choice of `ALL` over `ALLSELECTED` matters. `ALL ( mart_funding_audit[recipient] )` clears filters on the recipient column only, so the division slicer from Step 7 still applies but the Pareto's own axis and its Top N filter do not. `ALLSELECTED` would honour that Top N filter, quietly turning the denominator into the top-25 subtotal and sending the cumulative line to 100 percent at rank 25 instead of 15.77 percent. With the slicer cleared, `Base Dollars` reads the grand total $75,357,902.03.

## Step 3: the recipient Pareto

Measures:

```DAX
Cumulative Dollars =
VAR CurrentDollars = [Total Dollars]
RETURN
    CALCULATE (
        [Total Dollars],
        FILTER (
            ALL ( mart_funding_audit[recipient] ),
            [Total Dollars] >= CurrentDollars
        )
    )
```

```DAX
Cumulative Share % =
DIVIDE ( [Cumulative Dollars], [Base Dollars] )
```

Format `Cumulative Share %` as Percentage, 2 decimals.

`Cumulative Dollars` sums every recipient at or above the current bar's dollar figure. That is the running total a Pareto needs, and it costs one pass over the recipient list. The nested `RANKX`-inside-`FILTER` version of this pattern returns the same numbers but evaluates the rank of all 2,343 recipients once per visible bar, which is slow enough to notice.

One optional extra, useful only for checking a rank against the golden file:

```DAX
Recipient Rank =
RANKX ( ALL ( mart_funding_audit[recipient] ), [Total Dollars], , DESC, Dense )
```

Build the visual:

1. Insert a **Line and clustered column chart**.
2. X-axis: `recipient`. Column y-axis: `Total Dollars`. Line y-axis: `Cumulative Share %`.
3. Sort by dollars: visual header **More options (...)** > Sort axis > `Total Dollars` > Sort descending.
4. 2,343 recipients will not all fit on one axis, and they do not need to: open the Filters pane, drop `recipient` on the visual, filter type **Top N**, Show items Top 25, By value `Total Dollars`, Apply. That mirrors the golden top_recipients section. Because both measures clear the recipient column with `ALL`, the cumulative line keeps measuring against all 2,343 recipients rather than the visible 25.

Tie note: two recipients share $300,375.00 at ranks 23 and 24. Both are included the moment either bar is reached, so the cumulative line steps by both at once, while the CSV breaks the tie alphabetically and steps twice. Compare cumulative values on untied bars; everything through rank 22 matches the golden exactly, and the pair lands back on 15.38 percent by rank 24.

## Step 4: the top-10 concentration KPI card

```DAX
Top 10 Dollars =
CALCULATE (
    [Total Dollars],
    TOPN (
        10,
        ALL ( mart_funding_audit[recipient] ),
        [Total Dollars],
        DESC
    )
)
```

```DAX
Top 10 Concentration % =
DIVIDE ( [Top 10 Dollars], [Base Dollars] )
```

Format `Top 10 Concentration %` as Percentage, 2 decimals. Insert a **Card** visual and give it `Top 10 Concentration %`. Add a second Card for `Total Dollars` so the grand total reads on the page too; a card carries no recipient filter, so it shows the full $75,357,902.03.

`TOPN` would return more than 10 rows on a tie at the boundary; in this mart rank 10 ($421,685.97) and rank 11 ($393,793.15) are not tied, so the set is exactly 10 recipients and the card must read **9.07%**.

## Step 5: year-over-year dollars by division

The mart has no date column, so do not reach for time-intelligence functions (`SAMEPERIODLASTYEAR`, `DATEADD`); they need a date table and will error or mislead here. Use the year-index pattern over `fiscal_year_start` instead:

```DAX
Dollars Previous Year =
VAR CurrentYear = MAX ( mart_funding_audit[fiscal_year_start] )
RETURN
    CALCULATE (
        [Total Dollars],
        REMOVEFILTERS (
            mart_funding_audit[fiscal_year],
            mart_funding_audit[fiscal_year_start]
        ),
        mart_funding_audit[fiscal_year_start] = CurrentYear - 1
    )
```

```DAX
YoY Change $ =
VAR Prev = [Dollars Previous Year]
RETURN
    IF (
        HASONEVALUE ( mart_funding_audit[fiscal_year] ) && NOT ISBLANK ( Prev ),
        [Total Dollars] - Prev
    )
```

```DAX
YoY Change % =
VAR Prev = [Dollars Previous Year]
RETURN
    IF (
        HASONEVALUE ( mart_funding_audit[fiscal_year] ) && NOT ISBLANK ( Prev ),
        DIVIDE ( [Total Dollars] - Prev, Prev )
    )
```

Format `YoY Change $` as currency 2 decimals, `YoY Change %` as percentage 2 decimals. Division stays in filter context (only the year columns are removed), so each division compares against its own previous year, which is exactly what the SQL `LAG` does. Divisions here are continuous across their active years, so calendar-previous and observed-previous agree; a division's first active year shows blank, matching the golden.

The `HASONEVALUE` guard is what keeps the matrix honest at the Total row. Without it, `MAX ( fiscal_year_start )` on a subtotal returns the division's last year, so the measure subtracts one year from the sum of all eleven and reports a change of $67,063,403.43 at 808.53 percent. Those are arithmetic on mismatched scopes, not a real figure. Blanking them leaves the Total row showing what it should: dollars only, tying to $75,357,902.03.

The Total column (the all-division rollup) does keep a year-over-year figure, and it will not appear anywhere in the golden. It is a legitimate cross-division change the SQL never computes, since `LAG` there partitions by division. Do not try to reconcile that column against expected/funding_audit.csv.

Build a **Matrix**: Rows `fiscal_year`, Columns `division`, Values `Total Dollars`, `YoY Change $`, `YoY Change %`. A clustered column chart of `Total Dollars` by `fiscal_year` with `division` as legend makes a good companion, but the matrix is the one that shows exact dollars.

## Step 6: the duplicate-candidates table

1. Insert a **Table** visual with columns: `recipient`, `program_name`, `fiscal_year`, `payment_amount`, `dup_occurrences`.
2. Set `payment_amount` and `dup_occurrences` to **Don't summarize** (dropdown on each field in the Values well). Identical rows then collapse, giving one line per candidate group.
3. Filters pane: drag `is_duplicate_candidate` onto the visual, Basic filtering, tick **1**.

The table must show 9 rows. The largest group: Dalhousie Agricultural Campus, Research Acceleration Program, 2015-2016, $30,000.00, 4 occurrences.

## Step 7: layout, slicer, formatting

- Add a **Slicer** with `division` (dropdown style) so every visual can be cut by division. The measures only ever clear the recipient column, so the slicer reaches all of them and the shares recompute against the selected division.
- Suggested layout: both cards top-left, the Pareto across the top-right, the YoY matrix bottom-left, the duplicates table bottom-right, slicer above the cards.
- Sweep the formatting: every dollar field currency with 2 decimals, every percent 2 decimals, thousands separators on. The report reads to the cent or it is not done.
- Page title: "NS Agriculture Funding Audit, 2014-2015 to 2024-2025".

## Numbers-match check

With the division slicer cleared, the finished report must read identically to the golden output, to the cent:

- Grand total card: **$75,357,902.03**
- Top Pareto bar: **Millen Farms Ltd, $983,581.28**
- Top 10 Concentration % card: **9.07%**
- Matrix spot check: Programs, 2022-2023 = $16,320,887.65 with YoY Change $11,989,118.49 (276.77%)
- Duplicates table: 9 rows

If any figure differs, the mart import or a measure is wrong; the SQL golden is the arbiter.

## Step 8: save and export

1. **File > Save as**, navigate into `bi/powerbi/`, and save as `funding_audit` with save type **Power BI project files (*.pbip)**. Desktop writes `funding_audit.pbip` plus `funding_audit.Report/` and `funding_audit.SemanticModel/` folders. Those definition folders are text and get committed.
2. Export the page as a PNG into `bi/powerbi/screenshots/funding_audit.png`, or use **File > Export > Export to PDF** into the same folder.
3. Scrub the source path before committing. Power Query bakes the absolute path you browsed to into `funding_audit.SemanticModel/definition/tables/mart_funding_audit.tmdl`, so the `Csv.Document(File.Contents(...))` line arrives carrying a full `C:\Users\...` string. Rewrite it to the repo-relative `bi\exports\mart_funding_audit.csv`. The project still opens; only a live data refresh would need the path pointed back at a real location. Any later re-save from Desktop reintroduces the absolute path, so this check repeats every time.
4. Two things stay out of the repo. `.gitignore` excludes the `bi/powerbi/**/.pbi/` directories, which hold machine-local editor state and a DPAPI-encrypted credential signature, and excludes `*.abf` cache files. Never commit a `.pbix`; `.gitattributes` marks it binary and generated if one ever appears.
