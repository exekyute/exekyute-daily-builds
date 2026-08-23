# BI build guides: fish landings value by port

Both faces read the same frozen file, `bi/exports/mart_fish_landings.csv`, and neither one recomputes a number. The SQL pipeline is the single brain: it applies the grain rule, the wharf roll-in, the port identity rule, and the per-measure suppression rule, then exports one mart at port-record grain. Tableau and Power BI re-derive shares, running totals, price per kg, and year-over-year change from that mart, but no cleaning rule is repeated in either tool. When both are built, their headline figures must match the golden output and each other, to the cent.

Blank kilograms and blank dollars in the mart are suppressed measures, not zeros, and this matters in both tools. Both ignore blanks in `SUM`, which is the behaviour the SQL relies on, so a straight sum in either tool agrees with the golden file. Price per kg is the one figure that needs both measures on the same row, which is why the mart carries `measure_class` and why both price measures below filter to `both_present` first.

---

# Tableau

## Prerequisites

Tableau Public Desktop Edition, free for Windows, plus a free public.tableau.com account. Everything published is public, there are no private workbooks, and the data connection is extract-only from the CSV. Publish to public.tableau.com and keep the live link for the README. Commit the .twb XML into bi/tableau/ alongside the CSV. Never commit a .twbx.

## Step 1: connect and set field types

1. Open Tableau Public Desktop, **Connect > To a File > Text file**, and choose `bi/exports/mart_fish_landings.csv`.
2. On the data source tab, set each field's type from the icon above the column name:

   | Field | Type | Role |
   | --- | --- | --- |
   | Year | Number (whole) | Dimension |
   | County | String | Dimension |
   | Port | String | Dimension |
   | Port Label | String | Dimension |
   | Is Named Port | Number (whole) | Dimension |
   | Kgs | Number (decimal) | Measure |
   | Dollars | Number (decimal) | Measure |
   | Measure Class | String | Dimension |

   Year imports as a measure by default. Drag it into the Dimensions area, or right-click it and choose **Convert to Dimension**, before building anything.
3. Right-click **Dollars** > **Default Properties > Number Format > Currency (Custom)**, 2 decimal places, with thousands separators. Do the same for **Kgs** as a plain number with 2 decimals. The dashboard reads to the cent or it is not finished.

## Step 2: give County a geographic role, with the country context set

1. Right-click **County** > **Geographic Role > County**.
2. Tableau needs to know which country's counties these are. Build any sheet with County on Detail, then use **Map > Edit Locations** and set **Country/Region** to a fixed value of **Canada** and **State/Province** to a fixed value of **Nova Scotia**. Without that context, county names like Kings, Queens, Digby, and Halifax resolve against the wrong country and land in the United States.
3. Check the "unknown" indicator in the bottom right of the map. With the context set, all 18 counties should resolve.

## Step 3: the map of landed value by port

Try the port-level map first, then fall back in the order below. Read all three variants before you start, because the first one usually does not survive contact with the data.

1. **Ports.** Right-click **Port Label** > **Geographic Role > City**. Drag it to Detail, drag **Dollars** to Size, and set the mark type to Circle. Then look at the unknown-locations count in the bottom right.
2. **Fallback to county.** Most of these are wharf names rather than towns, so expect a large unknown count. If ports do not geocode, remove Port Label from the view and use **County** instead: County on Detail, **Dollars** on Color and on Size, mark type Map for a filled county map or Circle for proportional circles. That gives an honest coastal picture of where landed value arrives, one step coarser than the port.
3. **Fallback to a ranked bar.** If county geocoding also fails, or if the map adds nothing over the ranking, switch to the bar layout: **Port Label** on Rows, **SUM(Dollars)** on Columns, sorted descending by SUM(Dollars), with the Filters shelf carrying **Port Label** filtered to **Top 25 by SUM(Dollars)**. This is the same shape as Step 5's Pareto without the cumulative line, and it is the layout the golden `top_ports` section prints.

Whichever variant survives, name the sheet `Map of landed value` and keep it. Do not leave unknown locations hidden: click the indicator and choose **Filter data** so the sheet states what it is excluding, or drop back a level.

## Step 4: each port's share of provincial landed value (FIXED LOD)

Analysis > Create Calculated Field, name it `Port Share of Province`, and enter exactly:

```
{ FIXED [Port Label] : SUM([Dollars]) } / { FIXED : SUM([Dollars]) }
```

Format it as a percentage with 2 decimal places.

The empty `FIXED` on the right is the whole provincial total, so this reads as one port's dollars over every port's dollars. `FIXED` is computed before dimension filters, which catches people out here: add the year filter from Step 6 as an ordinary filter and the bars move while this share quietly keeps using all eight years. Right-click the Year filter and choose **Add to Context** so the numerator and the denominator follow the selected years together.

## Step 5: the Pareto

1. New sheet. **Port Label** on Rows, **SUM(Dollars)** on Columns. Sort Port Label descending by field SUM(Dollars).
2. Create a calculated field named `Cumulative Share of Landed Value`:

```
RUNNING_SUM( SUM([Dollars]) ) / TOTAL( SUM([Dollars]) )
```

3. Drag `Cumulative Share of Landed Value` to Columns beside SUM(Dollars), then right-click that pill > **Compute Using > Port Label**. Format it as a percentage with 2 decimal places.
4. Right-click the second axis > **Dual Axis**, then set the SUM(Dollars) mark type to Bar and the cumulative mark type to Line.
5. All 271 ports will not fit on one axis and do not need to. Filters shelf: **Port Label**, tab **Top**, By field, **Top 25** by **SUM(Dollars)**. That mirrors the golden `top_ports` section.

`RUNNING_SUM` and `TOTAL` are table calculations, so they run over what the view returns after filtering. With the Top 25 filter on, the cumulative line reaches 40.99 percent at rank 10 and 66.95 percent at rank 25 only if the filter is applied as a context filter or the totals are computed across the full data; if you filter to the top 25 as a plain dimension filter, `TOTAL` sees only those 25 ports and the line ends at 100 percent. Decide which you want and say so on the sheet title. The golden file's `cumulative_share_pct` uses the provincial denominator, so match that if you want the numbers to line up.

## Step 6: the dashboard with a year filter

1. New dashboard, name it `NS fish landings by port`. Drop in the map sheet, the Pareto, and a small text or bar sheet showing dollars by year.
2. On any sheet, drag **Year** to Filters, select all eight years, then on the dashboard use the filter card's dropdown > **Apply to Worksheets > All Using This Data Source**.
3. Right-click the Year filter card > **Add to Context**, for the reason in Step 4.
4. Title the dashboard with the window it covers, 2017 to 2024, so nobody reads a single-year figure as the whole picture.
5. Publish to public.tableau.com, then save the workbook locally as **.twb** into `bi/tableau/`. Screenshots into `bi/tableau/screenshots/`.

Optional, if you want price per kg on the dashboard, create `Price per Kilogram` and put **Measure Class** on the Filters shelf set to `both_present` for that sheet only:

```
SUM([Dollars]) / SUM([Kgs])
```

---

# Power BI

## Prerequisites

Power BI Desktop, free from the Microsoft Store. Enable File > Options > Preview features > "Power BI Project (.pbip) save option". No service account and no tenant is needed. The free deliverable is the committed .pbip plus exported PNG or PDF, because Publish to web is not available on the free tier. Commit the .pbip .Report and .SemanticModel text folders. Never commit a .pbix.

## Step 1: connect to the same mart

1. Home > **Get Data** > **Text/CSV**, and browse to `bi/exports/mart_fish_landings.csv`.
2. In the preview dialog choose **Transform Data**, not Load, so the types get set explicitly rather than sniffed.
3. In Power Query set each column type by clicking its type icon:

   | Column | Type |
   | --- | --- |
   | year | Whole Number |
   | county | Text |
   | port | Text |
   | port_label | Text |
   | is_named_port | Whole Number |
   | kgs | **Fixed decimal number** |
   | dollars | **Fixed decimal number** |
   | measure_class | Text |

   Fixed decimal number is the type that keeps money exact to the cent. Do not leave `dollars` as plain Decimal Number, and check that Power Query has not guessed Text for `kgs` or `dollars`: both columns are blank on 1,463 of 2,156 rows, which is enough to make the sniffer hesitate.
4. **Close & Apply**. Connection mode is Import, the default for CSV. Nothing here needs DirectQuery.

## Step 2: base measures

Modeling > New measure, once each. Everything below builds on these two.

```DAX
Total Dollars = SUM ( mart_fish_landings[dollars] )
```

```DAX
Total Kilograms = SUM ( mart_fish_landings[kgs] )
```

Format `Total Dollars` as Currency with 2 decimal places and `Total Kilograms` as a whole-number-separated decimal with 2 places.

## Step 3: share of total, with DIVIDE over ALL

```DAX
Share of Total Dollars =
DIVIDE (
    [Total Dollars],
    CALCULATE ( [Total Dollars], ALL ( mart_fish_landings[port_label] ) )
)
```

Format as Percentage, 2 decimals. `ALL` on the `port_label` column alone drops the port grouping while leaving every other filter in place, so the denominator follows the year slicer from Step 7 instead of ignoring it. `DIVIDE` returns blank rather than an error if the denominator is ever empty.

## Step 4: the Pareto running total

```DAX
Cumulative Dollars by Port =
VAR CurrentDollars = [Total Dollars]
RETURN
    CALCULATE (
        [Total Dollars],
        FILTER (
            ALL ( mart_fish_landings[port_label] ),
            [Total Dollars] >= CurrentDollars
        )
    )
```

```DAX
Cumulative Share of Dollars =
DIVIDE (
    [Cumulative Dollars by Port],
    CALCULATE ( [Total Dollars], ALL ( mart_fish_landings[port_label] ) )
)
```

Format `Cumulative Share of Dollars` as Percentage, 2 decimals.

Build the visual: insert a **Line and clustered column chart**, X-axis `port_label`, column Y-axis `Total Dollars`, line Y-axis `Cumulative Share of Dollars`. Sort by dollars from the visual's **More options (...) > Sort axis > Total Dollars > Sort descending**. Then open the Filters pane, drop `port_label` on the visual, filter type **Top N**, Show items Top 25 By value `Total Dollars`, Apply.

This running total ranks by measure value rather than by an index, so any two ports on exactly equal dollars would share a cumulative point. No two ports tie in this mart, so the line steps once per bar.

## Step 5: price per kilogram, guarded

```DAX
Price per Kilogram =
VAR PricedDollars =
    CALCULATE ( [Total Dollars], mart_fish_landings[measure_class] = "both_present" )
VAR PricedKilograms =
    CALCULATE ( [Total Kilograms], mart_fish_landings[measure_class] = "both_present" )
RETURN
    DIVIDE ( PricedDollars, PricedKilograms )
```

Format as Currency, 4 decimal places. Two guards are doing work here. The `measure_class` filter keeps the numerator and denominator on the same rows, which is what the SQL does and what makes the figure mean anything. `DIVIDE` returns blank instead of an error when a port reports dollars but no kilograms, so a suppressed port shows an empty cell rather than infinity.

## Step 6: year-over-year landed value

This mart has no contiguous date column, only an integer `year`. Time-intelligence functions such as `SAMEPERIODLASTYEAR`, `DATEADD`, and `PREVIOUSYEAR` need a marked date table, and without one they return blanks silently rather than failing, so a report built on them looks finished and is wrong. Use the year-index pattern instead:

```DAX
Dollars Previous Year =
VAR CurrentYear = MAX ( mart_fish_landings[year] )
RETURN
    CALCULATE (
        [Total Dollars],
        REMOVEFILTERS ( mart_fish_landings[year] ),
        mart_fish_landings[year] = CurrentYear - 1
    )
```

```DAX
YoY Dollars =
VAR Previous = [Dollars Previous Year]
RETURN
    IF ( NOT ISBLANK ( Previous ), [Total Dollars] - Previous )
```

```DAX
YoY Dollars % =
DIVIDE ( [YoY Dollars], [Dollars Previous Year] )
```

Format `YoY Dollars` as Currency 2 decimals and `YoY Dollars %` as Percentage 2 decimals. `REMOVEFILTERS` on the year column and then re-filtering to `CurrentYear - 1` is the whole pattern: it steps back one calendar year regardless of what else is on the page. 2017 shows blank, matching the golden file.

Build a **Matrix**: Rows `year`, Values `Total Dollars`, `Total Kilograms`, `Price per Kilogram`, `YoY Dollars`, `YoY Dollars %`.

## Step 7: slicer, layout, formatting

- Add a **Slicer** with `year` and a second with `county`.
- Add a **Card** for `Total Dollars` and one for `Price per Kilogram`.
- Suggested layout: cards top-left, slicers above them, Pareto across the top-right, the year matrix bottom-left, a `port_label` table bottom-right with `Total Dollars`, `Share of Total Dollars`, and `Price per Kilogram`.
- If you want the named ports and the residual buckets shown apart, drop `is_named_port` on a visual filter. 1 is a real port, 0 is the province's `Other` bucket for that county and year, which holds 14.06 percent of all dollars.
- Sweep the formatting: every dollar field Currency with 2 decimals, price per kg 4 decimals, every percent 2 decimals, thousands separators on.
- Page title: "NS fish landings value by port, 2017 to 2024".

## Step 8: save and export

1. **File > Save as**, into `bi/powerbi/`, named `fish-landings-value-by-port`, save type **Power BI project files (\*.pbip)**. Desktop writes the `.pbip` plus the `.Report` and `.SemanticModel` folders; all of that is text and gets committed.
2. **File > Export > Export to PDF** into `bi/powerbi/screenshots/`, or take PNG screenshots of the report page into the same folder.
3. Do not commit any `.pbix`.

---

# Numbers match

With no slicer or filter applied, one figure has to read identically in all three faces, the SQL output, the Tableau viz, and the Power BI report:

**Digby, in Digby County, $533,530,107.96 in landed value across 2017 to 2024.**

That is the top port in the golden `top_ports` section, the top bar of both Paretos, and the largest mark on the Tableau map. Two supporting figures should agree alongside it: the provincial total of **$8,716,996,237.83** and Digby's **6.12 percent** share of it. If any of them differs, the mart import or a measure is wrong, and the SQL golden is the arbiter.

Digby's lead is thin. Lower Woods Harbour finishes $3,375,514.28 behind it, and it only finishes behind because the wharf roll-in rule in `spec.md` puts the 2019 and 2020 Falls Point rows back with the rest of the port. A face that groups on the raw published port name instead of `port_label` will drop Lower Woods Harbour to $475,001,999.03 and change the ranking. That is the one place where reading the mart wrongly produces a plausible number rather than an obviously broken one.
