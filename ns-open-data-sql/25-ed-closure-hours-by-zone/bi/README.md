# Power BI build guide: emergency department closure hours

This folder holds the BI face of the project. The SQL pipeline is the single
brain: it computes every number and exports one mart,
`bi/exports/mart_ed_closures.csv`. Power BI reads that mart and re-derives the
same figures; it never recomputes a cleaning rule. When the report is built, its
headline numbers must match the golden output exactly.

## Why Power BI for this data

The two questions left for the BI layer are year-over-year movement and a
zone-by-type matrix, and both are measure work rather than chart work. There is
no date column here, only an integer fiscal year, so the previous-year figure
has to be written as a measure with an explicit year offset, and the matrix
needs the total and the temporary share to hold their meaning in every cell
including the empty ones. That is the DAX face of the dataset, which is what
Power BI is best at. This is a single-tool build by deliberate selection: the
SQL base build is complete and verified on its own, and this guide can be
followed any time after the fact.

## Prerequisites

Power BI Desktop, free from the Microsoft Store. Enable File > Options > Preview
features > "Power BI Project (.pbip) save option". No service account and no
tenant is needed. The free deliverable is the committed .pbip plus exported PNG
or PDF, because Publish to web is not available on the free tier. Commit the
.pbip .Report and .SemanticModel text folders. Never commit a .pbix.

## Step 1: connect to the mart

1. Home > **Get Data** > **Text/CSV**.
2. Browse to `bi/exports/mart_ed_closures.csv` inside this project folder.
3. In the preview dialog choose **Transform Data** (not Load) so you can set
   types explicitly.
4. In Power Query, set each column type by clicking its type icon:

   | Column | Type |
   | --- | --- |
   | fiscal_year | Text |
   | fiscal_year_start | Whole Number |
   | zone | **Text** |
   | facility_type | Text |
   | site | Text |
   | temporary_hours | **Fixed decimal number** |
   | scheduled_hours | **Fixed decimal number** |
   | total_hours | **Fixed decimal number** |
   | is_zero_closure | Whole Number |

   Two of those matter more than the rest. `zone` must stay Text, because `IWK`
   is one of the five zone values and a Whole Number guess turns it into an
   error row. The three hours columns must be Fixed decimal number; plain
   Decimal Number is floating point and drifts by the time it has added half a
   million hours reported to one decimal place.
5. **Close & Apply**. Connection mode is Import, the default for CSV; nothing
   here needs DirectQuery.

## Step 2: sort the fiscal year label

`fiscal_year` is text, so Power BI sorts it alphabetically. That happens to be
right for this window, but it stops being right the moment a label changes
shape, and the whole point of carrying `fiscal_year_start` is that nothing
downstream has to derive a year.

1. Select the `fiscal_year` column in the Data view.
2. Column tools > **Sort by column** > `fiscal_year_start`.

Do not add a calculated year column in Power Query. The mart already carries the
integer, and deriving it a second time is a second place for it to go wrong.

## Step 3: base measures and the KPI cards

Modeling > New measure, once per measure.

```DAX
Total Closure Hours = SUM ( mart_ed_closures[total_hours] )
```

```DAX
Temporary Hours = SUM ( mart_ed_closures[temporary_hours] )
```

```DAX
Scheduled Hours = SUM ( mart_ed_closures[scheduled_hours] )
```

```DAX
Temporary Share % =
DIVIDE ( [Temporary Hours], [Total Closure Hours] )
```

Format the three hour measures as Decimal number with 1 decimal place and the
thousands separator on (Measure tools > Format). Format `Temporary Share %` as
Percentage with 2 decimals.

`DIVIDE` returns blank rather than an error when the denominator is zero, which
is the same guard the SQL applies. That matters here: 238 of the 456 site-years
report no closures, and the share for those is undefined rather than zero.

Insert two **Card** visuals, one for `Total Closure Hours` and one for
`Temporary Share %`. With no slicer applied they must read **520,811.3** and
**41.72%**.

## Step 4: closure hours by zone across years

1. Insert a **Clustered column chart**.
2. X-axis: `fiscal_year`. Legend: `zone`. Values: `Total Closure Hours`.
3. Visual header **More options (...)** > Sort axis > `fiscal_year` >
   **Sort ascending**. Because of Step 2 that sorts on `fiscal_year_start`, so
   the axis runs 2012-13 through 2023-24 in real order.

Five zones times twelve years is sixty columns, which is readable but busy. A
**Matrix** with Rows `fiscal_year`, Columns `zone`, Values `Total Closure Hours`
shows the same numbers exactly and is the one to read figures off.

The IWK column is 0.0 in all twelve years. That is a real reading, not a gap, so
leave it in.

## Step 5: year over year

**This mart has no contiguous date column, only the integer
`fiscal_year_start`.** Time-intelligence functions such as
`SAMEPERIODLASTYEAR`, `DATEADD`, and `PREVIOUSYEAR` need a marked date table.
Without one they do not error, they return blank, and a page of blanks looks
like a data problem rather than a modelling mistake. Use the year-index pattern
instead:

```DAX
Closure Hours Previous Year =
VAR CurrentYear = MAX ( mart_ed_closures[fiscal_year_start] )
RETURN
    CALCULATE (
        [Total Closure Hours],
        REMOVEFILTERS (
            mart_ed_closures[fiscal_year],
            mart_ed_closures[fiscal_year_start]
        ),
        mart_ed_closures[fiscal_year_start] = CurrentYear - 1
    )
```

```DAX
YoY Change Hours =
VAR Prev = [Closure Hours Previous Year]
RETURN
    IF ( NOT ISBLANK ( Prev ), [Total Closure Hours] - Prev )
```

```DAX
YoY Change % =
DIVIDE ( [YoY Change Hours], [Closure Hours Previous Year] )
```

Format `YoY Change Hours` as Decimal number with 1 decimal, `YoY Change %` as
Percentage with 2 decimals.

Only the two year columns are removed from filter context, so `zone` stays put
and each zone compares against its own previous year. That is exactly what the
SQL `LAG (total_hours) OVER (PARTITION BY zone ORDER BY fiscal_year_start)`
does. Every zone reports in all twelve years, so the offset year always exists
except at 2012-13, where the measure is blank and the golden file is blank too.

Add `YoY Change Hours` and `YoY Change %` to the Step 4 matrix as extra values.

## Step 6: the zone by type matrix

1. Insert a **Matrix**. Rows: `zone`. Columns: `facility_type`. Values:
   `Total Closure Hours` and `Temporary Share %`.
2. Format > Row headers > turn **Stepped layout** off so each zone reads on its
   own line.

Three of the five facility types report 0.0 hours in every site-year they
appear, so the Regional, Tertiary, and UTC columns are all zeros and their share
cells are blank. Both are correct. Cells with no site-year at all, for example
zone 2 and Community, are empty rather than zero, which is a different statement
again.

## Step 7: the ranked site table

```DAX
Site Rank =
RANKX (
    ALLSELECTED ( mart_ed_closures[site] ),
    [Total Closure Hours],
    ,
    DESC,
    Dense
)
```

1. Insert a **Table** visual with columns `Site Rank`, `site`, `zone`,
   `facility_type`, `Total Closure Hours`, `Temporary Hours`,
   `Scheduled Hours`, `Temporary Share %`.
2. Set `Site Rank` to **Don't summarize**.
3. Sort by `Total Closure Hours` descending.
4. Add a **Slicer** with `zone`, dropdown style.

Two notes on this table. `facility_type` is a site-year attribute, so a site
that was reclassified shows both of its types unless a year is filtered; the
golden `site_totals` section instead states one type per site, the one reported
in that site's most recent year. And thirteen sites tie at 0.0 hours, so dense
ranking gives all thirteen rank 26 while the golden file breaks the tie
alphabetically into ranks 26 through 38. Compare ranks 1 through 25, which match
exactly.

## Numbers-match check

With the zone slicer cleared, the finished report must read identically to the
golden output:

- Total Closure Hours card: **520,811.3**
- Temporary Share % card: **41.72%**
- Step 4 matrix, zone 3 column, 2023-24 row: **20,134.0** with YoY Change Hours
  **-10,225.6** and YoY Change % **-33.68%**
- Step 6 matrix, zone 3 and Community: **158,575.4**
- Step 7 table, top row: **New Waterford Consolidated Hospital**, zone 3,
  **65,073.5** hours, **11.51%** temporary
- Step 7 table row count: **38**

If any figure differs, the mart import or a measure is wrong; the SQL golden is
the arbiter. The most likely cause is a column typed as Decimal Number instead
of Fixed decimal number in Step 1.

## Step 8: save and export

1. **File > Save as**, navigate into `bi/powerbi/`, and save as
   `ed-closure-hours-by-zone` with save type **Power BI project files (*.pbip)**.
   Desktop writes `ed-closure-hours-by-zone.pbip` plus the
   `ed-closure-hours-by-zone.Report/` and
   `ed-closure-hours-by-zone.SemanticModel/` folders; all of that is text and
   gets committed.
2. Export the visuals: **File > Export > Export to PDF** into
   `bi/powerbi/screenshots/`, or take PNG screenshots of the report page into
   the same folder.
3. Do not commit any `.pbix`. The project `.gitignore` already excludes it and
   `.gitattributes` marks the `bi/powerbi/` tree vendored.
