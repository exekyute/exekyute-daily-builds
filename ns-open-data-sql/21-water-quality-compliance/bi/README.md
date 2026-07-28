# Power BI build guide: water-quality guideline compliance

This folder holds the BI face of the build. The SQL pipeline is the single brain: it applies every threshold, converts every unit, and exports one mart, `bi/exports/mart_water.csv`, with the pass and non-detect flags already decided. Power BI aggregates those flags and never re-applies a rule, which is exactly why a floating-point import cannot move a rate away from the golden.

## Why Power BI for this data

The deliverable this data wants is an analyte-by-location compliance matrix with KPI cards over it, and that is a matrix visual and four measures rather than a chart type: a pass rate is a ratio of two filtered counts, so it has to be a DAX measure to stay correct at every level of the grid, and conditional formatting on the matrix is what turns 65 cells into a picture of which river fails which analyte. This is a single-tool build by deliberate selection. The SQL base build is complete and verified on its own, and the mart is frozen against a pinned snapshot, so this guide can be followed any time after the fact and will still produce the same numbers.

## Prerequisites

Power BI Desktop, free from the Microsoft Store. Enable File > Options > Preview features > "Power BI Project (.pbip) save option". No service account and no tenant is needed. The free deliverable is the committed .pbip plus exported PNG or PDF, because Publish to web is not available on the free tier. Commit the .pbip .Report and .SemanticModel text folders. Never commit a .pbix.

## Step 1: connect to the mart

1. Home > **Get Data** > **Text/CSV**.
2. Browse to `bi/exports/mart_water.csv` inside this project folder.
3. In the preview dialog choose **Transform Data** (not Load) so you can set types explicitly.
4. In Power Query, set each column type by clicking its type icon:

   | Column | Type |
   | --- | --- |
   | sample_date | Date |
   | sample_time | Text |
   | sample_year | Whole Number |
   | location_id | Text |
   | location | Text |
   | analyte | Text |
   | sample_fraction | Text |
   | result_unit | Text |
   | result_value | Decimal Number |
   | guideline_unit | Text |
   | guideline_threshold | Decimal Number |
   | guideline_direction | Text |
   | row_class | Text |
   | is_evaluated | Whole Number |
   | is_pass | Whole Number |
   | is_non_detect | Whole Number |
   | is_censored_above | Whole Number |

   Two notes on that table. `result_value` is a concentration, not money, so it takes Decimal Number and not Fixed decimal number; nothing downstream compares it against a threshold, so its precision cannot change a rate. And `is_pass` and `is_censored_above` arrive with blanks in them on purpose, marking rows that were never evaluated. Leave the blanks alone. Do not use Replace Values to turn them into zeroes, because a zero in `is_pass` means "breached the guideline" and 556 rows that were never tested would start reading as failures.

5. **Close & Apply**. Connection mode is Import (the default for CSV); nothing here needs DirectQuery.

## Step 2: base measures

Modeling > New measure, once per measure. These four carry everything else.

```DAX
Evaluated Samples =
CALCULATE (
    COUNTROWS ( mart_water ),
    mart_water[row_class] = "evaluated"
)
```

```DAX
Passing Samples =
CALCULATE (
    SUM ( mart_water[is_pass] ),
    mart_water[row_class] = "evaluated"
)
```

```DAX
Pass Rate =
DIVIDE ( [Passing Samples], [Evaluated Samples] )
```

```DAX
Breaching Samples =
[Evaluated Samples] - [Passing Samples]
```

Format `Pass Rate` as Percentage with 2 decimal places (Measure tools > Format > Percentage, 2), and the three counts as Whole Number with a thousands separator.

`DIVIDE` is doing the work in that third measure, not the `/` operator: an analyte-and-location cell with no evaluated samples returns blank and leaves the matrix cell empty, instead of throwing a divide-by-zero across the grid. The explicit `row_class = "evaluated"` filter on both halves is what keeps the numerator and denominator built from the same set of rows even when a slicer is cutting the page.

## Step 3: the KPI cards

```DAX
Non-Detect Samples =
CALCULATE (
    SUM ( mart_water[is_non_detect] ),
    mart_water[row_class] = "evaluated"
)
```

```DAX
Non-Detect Share =
DIVIDE ( [Non-Detect Samples], [Evaluated Samples] )
```

```DAX
Unconfirmable Passes =
CALCULATE (
    SUM ( mart_water[is_censored_above] ),
    mart_water[row_class] = "evaluated"
)
```

```DAX
Quality Control Rows Excluded =
COALESCE (
    CALCULATE (
        COUNTROWS ( mart_water ),
        mart_water[row_class] = "quality_control"
    ),
    0
)
```

Format `Non-Detect Share` as Percentage, 2 decimals; the other two as Whole Number.

That `COALESCE` on the last measure matters. This snapshot contains no quality-control rows at all, so `COUNTROWS` over an empty filter returns BLANK and the card renders as an empty box, which reads like a broken visual, not a true zero. Wrapping it makes the card say **0**, which is the finding.

Insert four **Card** visuals and give them `Pass Rate`, `Evaluated Samples`, `Non-Detect Share`, and `Quality Control Rows Excluded`. A fifth card with `Unconfirmable Passes` is worth the space: it is the number that qualifies the headline, because 621 of the passes are non-detects reported at a limit above their own guideline and cannot be confirmed from this data.

## Step 4: the analyte-by-location matrix

1. Insert a **Matrix** visual.
2. Rows: `analyte`. Columns: `location`. Values: `Pass Rate`.
3. Add `Evaluated Samples` as a second value so a cell built on 23 samples is not read the same way as one built on 83.
4. Conditional formatting: with the visual selected, Format > Cell elements > Series `Pass Rate` > **Background color** > On > Format style **Rules**, and set:

   | If value | Colour |
   | --- | --- |
   | is greater than or equal to 0.99 and less than or equal to 1 | green |
   | is greater than or equal to 0.9 and less than 0.99 | amber |
   | is greater than or equal to 0 and less than 0.9 | red |

   Rules rather than a gradient, because a gradient across 65 cells that are nearly all at 100 percent flattens the six that are not.
5. Turn on Format > Grid > Options > Row subtotals if you want the per-analyte total column; the matrix grand total reads the network-wide pass rate either way.

The grid is 10 analytes by 8 stations, and 65 of those 80 pairs have data. The empty cells are real: five analytes only enter the sampling programme in 2019 and three stations stopped reporting in 2018.

## Step 5: the worst-locations bar

1. Insert a **Clustered bar chart**.
2. Y-axis: `location`. X-axis: `Pass Rate`.
3. Sort ascending by pass rate: visual header **More options (...)** > Sort axis > `Pass Rate` > Sort ascending. The worst station lands at the top.
4. Add a data label so the exact figure reads off the bar, and set the X-axis to start at 0 rather than the auto minimum, which otherwise stretches an 11-point spread across the whole plot and makes a 96 percent station look like a failure.

## Step 6: the analyte slicer

Add a **Slicer** with `analyte`, dropdown style, multi-select on. Every measure above is written as a plain filtered CALCULATE rather than an `ALL` variant, so all of them follow the slicer together and the cards recompute for whichever analytes are selected. Slicing to Iron on its own is the fastest way to see the story in this data.

## DAX rule for this mart: no time intelligence

This mart has no contiguous date column and no marked date table, and its sampling calendar has real gaps: several stations stop in 2018 and several analytes start in 2019. Do not use `SAMEPERIODLASTYEAR`, `DATEADD`, `PREVIOUSYEAR`, or any other time-intelligence function here. They do not error on a gap; they return blank, silently, and a year-over-year visual built on them will look finished while showing nothing. Use the year-index pattern over `sample_year` instead:

```DAX
Pass Rate Previous Year =
VAR CurrentYear = MAX ( mart_water[sample_year] )
RETURN
    CALCULATE (
        [Pass Rate],
        REMOVEFILTERS ( mart_water[sample_year] ),
        mart_water[sample_year] = CurrentYear - 1
    )
```

```DAX
Pass Rate YoY Change =
VAR Prev = [Pass Rate Previous Year]
RETURN
    IF ( NOT ISBLANK ( Prev ), [Pass Rate] - Prev )
```

Format `Pass Rate YoY Change` as Percentage, 2 decimals. `REMOVEFILTERS` on the year column only means every other filter, station and analyte and the slicer, stays in context, so each series compares against its own previous year. A year with no prior year of sampling returns blank, which is the honest answer, not a zero.

## Numbers-match check

With the analyte slicer cleared, the finished report must read identically to the golden output:

- Pass Rate card: **96.19%**
- Evaluated Samples card: **2,496** (of which 2,401 pass)
- Non-Detect Share card: **54.65%** (1,364 samples)
- Unconfirmable Passes card: **621**
- Quality Control Rows Excluded card: **0**
- Matrix row total, Iron: **76.04%** over 384 samples
- Matrix worst cell, Iron at Kelley River at Eight Mile Ford: **29.49%** over 78 samples
- Worst-locations bar, top bar: **Kelley River at Eight Mile Ford, 89.09%**

If any figure differs, the mart import or a measure is wrong; the SQL golden is the arbiter.

## Step 7: save and export

1. **File > Save as**, navigate into `bi/powerbi/`, and save as `water_compliance` with save type **Power BI project files (*.pbip)**. Desktop writes `water_compliance.pbip` plus `water_compliance.Report/` and `water_compliance.SemanticModel/` folders; all of that is text and gets committed. The name matches the golden output rather than the folder slug, which is how the rest of the series names its projects.
2. Export the page as a PNG into `bi/powerbi/screenshots/water_compliance.png`, or use **File > Export > Export to PDF** into the same folder.
3. Two things stay out of the commit. Do not commit any `.pbix`. And Desktop writes a `.pbi/` folder inside both the .Report and .SemanticModel folders holding `localSettings.json`, which carries a DPAPI blob tied to your Windows account, and `cache.abf`, a binary copy of the imported data. The `.gitignore` already refuses all of it.
4. The committed `mart_water.tmdl` carries the mart path as the relative `bi\exports\mart_water.csv`, not the absolute path Desktop writes on save. If you re-save from Desktop, re-scrub that one line before committing, or the commit leaks your home directory.
