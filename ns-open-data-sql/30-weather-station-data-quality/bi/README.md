# BI build guides: weather-station data-quality audit

This is a twin build, so both faces are here. Tableau and Power BI read the same frozen file, `bi/exports/mart_station_quality.csv`, and neither one recomputes a number. The SQL pipeline is the single brain: it derives each station's cadence, scores every station-day, and exports one mart at one grain. Both tools re-aggregate that mart and must land on the same figures the golden output already proves. When the two reports disagree with `expected/station_quality.csv`, the SQL is the arbiter and the report is wrong.

## The mart

One row per station per day. 46 road weather stations by 14 UTC days, 644 rows, no holes: a station that reported nothing on a day still has a row and still scores zero. Every column is defined in `../data_dictionary.md`.

Two things drive most of the build:

- `slots_covered` and `readings_expected` are the numerator and denominator of completeness. Build the percentage as a ratio of sums, never as an average of `uptime_pct`. Stations run at different cadences, so their daily denominators differ (360 slots a day at 240 seconds, 720 at 120, 144 at 600) and averaging the per-day percentage across the network gives 97.79 percent instead of the correct 97.83.
- The `station_`-prefixed columns repeat each station's window-level scorecard on all fourteen of its rows, so the flagged-station matrix needs no second table.

---

# Tableau

## Prerequisites

Tableau Public Desktop Edition, free for Windows, plus a free public.tableau.com account. Everything published is public, there are no private workbooks, and the data connection is extract-only from the CSV. Publish to public.tableau.com and keep the live link for the README. Commit the .twb XML into bi/tableau/ alongside the CSV. Never commit a .twbx.

## Step 1: connect and set types

1. Open Tableau Public Desktop. Connect > To a File > **Text file**.
2. Choose `bi/exports/mart_station_quality.csv`.
3. On the Data Source tab, set each field's type from the icon above its column header. Tableau guesses most of these right, but check all five of these:

   | Field | Type |
   | --- | --- |
   | Site Id | String |
   | Reading Date | **Date** |
   | Uptime Pct | Number (decimal) |
   | Station Uptime Pct | Number (decimal) |
   | Station Flag | String |

   Everything ending in `_count`, `_actual`, `_expected`, `_covered`, `_seconds`, or `_rank` should be Number (whole). If Reading Date comes in as String, click the icon and pick Date; the source format is ISO so no parsing dialog appears.
4. Leave the connection on **Extract** (the default for Tableau Public). The mart is 644 rows, so the extract builds instantly.
5. Drag every measure Tableau auto-aggregated into the Dimensions pane if it belongs there: `Cadence Seconds`, `Station Completeness Rank`, and `Reading Date` are dimensions, not measures.

## Step 2: calculated fields

Create these from Analysis > Create Calculated Field, one at a time.

**Completeness** is the ratio of sums and the field everything else leans on:

```
// Completeness
SUM([Slots Covered]) / SUM([Readings Expected])
```

Set its default format to Percentage with 2 decimal places (right-click the field > Default Properties > Number Format > Percentage, 2).

**Day Coverage vs Station Norm** is the table calculation the heatmap colours on. It compares each day against the station's own fourteen-day normal, so a station that always runs a little short does not light up the whole row:

```
// Day Coverage vs Station Norm
ZN( SUM([Slots Covered]) / SUM([Readings Expected]) )
- WINDOW_AVG( ZN( SUM([Slots Covered]) / SUM([Readings Expected]) ) )
```

**Share of Expected Readings** is the FIXED level-of-detail expression. It answers how much of the network's total expected reporting load each station carries, which is not uniform: the two 120-second stations each expect twice what a 240-second station does, and the 600-second station expects a sixth:

```
// Share of Expected Readings
{ FIXED [Site Id] : SUM([Readings Expected]) }
/ { FIXED : SUM([Readings Expected]) }
```

Format it as Percentage with 2 decimal places.

One gotcha worth knowing before you wire the filter in Step 5: a FIXED expression is computed before dimension filters apply, so filtering to one station leaves `Share of Expected Readings` reading that station's share of the *whole* network, which is usually what you want here. If you would rather it re-base against the visible stations, right-click the station filter on the Filters shelf and choose **Add to Context**.

## Step 3: the calendar heatmap

Readings per day per station, coloured by how each day compares to its station's own norm.

1. New worksheet, name it `Coverage Heatmap`.
2. Columns: drag `Reading Date` and set it to **Day** as a discrete blue pill (right-click the pill > Day, the one under the "More" list that reads `January 1, 2024`, then right-click again > Discrete).
3. Rows: `Site Id`.
4. Marks card: change the mark type to **Square**.
5. Colour: drag `Day Coverage vs Station Norm` onto Colour.
6. Right-click the Colour pill > **Compute Using** > `Reading Date`. This is the step that makes the table calculation partition per station rather than across the whole grid. If the whole map turns one shade, Compute Using is set wrong.
7. Colour legend: edit it, choose a diverging palette, tick **Use Full Colour Range**, and set the centre to 0. Days at the station's norm sit in the middle; outage days run to one end.
8. Label: drag `Readings Actual` onto Label so the raw count is readable inside each square.
9. Tooltip: add `Uptime Pct`, `Gap Count`, and `Surplus Readings`.

`RNSKM` is the row to look at. Two squares in it are blank-zero days, 2024-01-05 and 2024-01-09.

## Step 4: the ranked completeness bar

The mart carries no station coordinates, so there is no map to build here. A ranked bar is the honest alternative and reads better for an audit anyway, because the question is which stations are worst, not where they are.

1. New worksheet, name it `Completeness Ranking`.
2. Rows: `Site Id`. Columns: `Completeness`.
3. Sort ascending so the worst station is on top: click the sort icon on the Site Id header, or use the pill's Sort dialog with Field, Ascending, `Completeness`.
4. Colour: `Station Flag`. Two colours, `flagged` and `ok`.
5. Label: `Completeness`.
6. Add a reference line at the flag threshold: right-click the Completeness axis > Add Reference Line > Constant, Value `0.99`, Label Custom, `flag threshold`.
7. Tooltip: add `Station Flag Reasons`, `Station Gap Count`, `Station Frozen Run Count`, `Station Out Of Range Count`, and `Station Days With No Readings`.

The top bar is `RNSKM` at **59.78%**.

## Step 5: the dashboard and its station filter

1. New dashboard, name it `Road Weather Station Data Quality`.
2. Size: Automatic. Drag `Completeness Ranking` in on the left and `Coverage Heatmap` on the right.
3. Add a text object across the top: `NS road weather stations, data quality audit, 2024-01-01 to 2024-01-14 UTC`.
4. Station filter: on the `Completeness Ranking` sheet, drag `Site Id` to the Filters shelf, tick All, OK. Then on the dashboard, select that worksheet, open its More options caret > **Filters** > `Site Id`. Set the filter card to Multiple Values (dropdown).
5. Make the filter drive both sheets: select the filter card, caret > **Apply to Worksheets** > **Selected Worksheets**, tick both.
6. A second useful filter card is `Station Flag`, so you can pull the dashboard down to the 21 flagged stations in one click.
7. Optional third sheet for the share-of-load view: a bar of `Share of Expected Readings` by `Site Id`, sorted descending. It puts the two 120-second stations at the top and makes the point that the network's expected load is not evenly spread.

## Step 6: publish and commit

1. **Server > Tableau Public > Save to Tableau Public As**, sign in, name it `NS Road Weather Station Data Quality`. Keep the resulting public.tableau.com link for the project README.
2. **File > Save As** into `bi/tableau/` with save type **Tableau Workbook (\*.twb)**. The .twb is XML and gets committed. A .twbx packages the extract as a binary and does not.
3. Screenshots of the dashboard and both worksheets go into `bi/tableau/screenshots/`.

---

# Power BI

## Prerequisites

Power BI Desktop, free from the Microsoft Store. Enable File > Options > Preview features > "Power BI Project (.pbip) save option". No service account and no tenant is needed. The free deliverable is the committed .pbip plus exported PNG or PDF, because Publish to web is not available on the free tier. Commit the .pbip .Report and .SemanticModel text folders. Never commit a .pbix.

## Step 1: connect to the mart

1. Home > **Get Data** > **Text/CSV**.
2. Browse to `bi/exports/mart_station_quality.csv` inside this project folder.
3. In the preview dialog choose **Transform Data**, not Load, so you can set types explicitly.
4. In Power Query, set each column type by clicking its type icon:

   | Column | Type |
   | --- | --- |
   | site_id | Text |
   | reading_date | **Date** |
   | uptime_pct, station_uptime_pct | Decimal Number |
   | station_flag, station_flag_reasons | Text |
   | everything else | Whole Number |

   `reading_date` must be **Date**, not Date/Time. A Date/Time column will still relate to the date table but drags a time component into every slicer and axis.
5. Do not Close & Apply yet. The date table gets built in the same Power Query session, next.

## Step 2: build the date table

This mart does carry a real contiguous date column, so the report gets a proper date table and real time intelligence rather than the year-index workaround.

1. In Power Query: Home > New Source > **Blank Query**.
2. Home > **Advanced Editor**, replace everything in the window with this, and click Done:

```M
let
    Source    = List.Dates(
                    #date(2024, 1, 1),
                    Duration.Days(#date(2024, 1, 15) - #date(2024, 1, 1)),
                    #duration(1, 0, 0, 0)
                ),
    ToTable   = Table.FromList(Source, Splitter.SplitByNothing(), {"Date"}),
    Typed     = Table.TransformColumnTypes(ToTable, {{"Date", type date}}),
    AddYear   = Table.AddColumn(Typed,   "Year",      each Date.Year([Date]),      Int64.Type),
    AddMonth  = Table.AddColumn(AddYear, "Month",     each Date.MonthName([Date]), type text),
    AddDay    = Table.AddColumn(AddMonth,"Day",       each Date.Day([Date]),       Int64.Type),
    AddDow    = Table.AddColumn(AddDay,  "Weekday",   each Date.DayOfWeekName([Date]), type text),
    AddDowNum = Table.AddColumn(AddDow,  "Weekday No",each Date.DayOfWeek([Date], Day.Monday), Int64.Type)
in
    AddDowNum
```

   The two `#date` literals are the audit's declared window bounds, start inclusive and end exclusive, the same pair that sits in `sql/00_schema.sql`. The table comes out at exactly 14 rows, one per audited day, with no dates the mart cannot fill.
3. Rename the query to `Date` in the right-hand Properties pane.
4. **Close & Apply**. Connection mode is Import, the default for CSV; nothing here needs DirectQuery.
5. Model view: drag `Date[Date]` onto `mart_station_quality[reading_date]`. Confirm the relationship reads **One to many**, `Date` on the one side, and **Single** cross-filter direction. Double-click the line if you need to change it.
6. Select the `Date` table in the Data pane, then **Table tools > Mark as date table > Mark as date table**. Set Date column to `Date` and click OK. A green tick means the validation passed. Time intelligence will silently return wrong answers without this step, so do not skip it.

## Step 3: base measures

Modeling > New measure, once each. Everything below builds on these three.

```DAX
Slots Covered = SUM ( mart_station_quality[slots_covered] )
```

```DAX
Slots Expected = SUM ( mart_station_quality[readings_expected] )
```

```DAX
Percent Complete = DIVIDE ( [Slots Covered], [Slots Expected] )
```

Format `Percent Complete` as Percentage with 2 decimal places (Measure tools > Format > Percentage, 2).

`DIVIDE` rather than `/` is deliberate: a station filtered down to a day it did not exist would give a zero denominator, and `DIVIDE` returns blank there instead of an error that blanks the whole visual.

## Step 4: the percent-complete KPI card

1. Insert a **Card** visual and give it `Percent Complete`.
2. Add a second Card with `Slots Covered` and a third with `Slots Expected`, both formatted Whole Number with a thousands separator.
3. Add a fourth Card for the flagged count:

```DAX
Stations Flagged =
CALCULATE (
    DISTINCTCOUNT ( mart_station_quality[site_id] ),
    mart_station_quality[station_flag] = "flagged"
)
```

With no slicer applied the cards must read **97.83%**, **233,712**, **238,896**, and **21**.

## Step 5: the flagged-station matrix

```DAX
Flag Reasons = MAX ( mart_station_quality[station_flag_reasons] )
```

```DAX
Silent Days = MAX ( mart_station_quality[station_days_with_no_readings] )
```

1. Insert a **Matrix**. Rows: `site_id`. Values, in order: `Percent Complete`, `station_gap_count` (set to **Maximum**, not Sum, since the value repeats on all fourteen rows), `station_frozen_run_count` (Maximum), `station_out_of_range_count` (Maximum), `Silent Days`, `Flag Reasons`.
2. Sort ascending on `Percent Complete`: click the column header once, twice if it lands descending. Worst station on top.
3. Conditional formatting on uptime: hover `Percent Complete` in the Values well > dropdown > **Conditional formatting** > **Background colour**. Switch Format style to **Rules** and enter three:

   | If value | Colour |
   | --- | --- |
   | is greater than or equal to 0.99 and is less than or equal to 1 | green |
   | is greater than or equal to 0.95 and is less than 0.99 | amber |
   | is greater than or equal to 0 and is less than 0.95 | red |

   Rules take percentages as decimals when the measure is formatted as a percentage, so `0.99` is the 99 percent threshold, not `99`. The threshold matches `UPTIME_FLAG_PCT` in the SQL.
4. Top row must be `RNSKM` at **59.78%**, red, 4 gaps, 2 silent days.

## Step 6: the rolling reading count

`DATESINPERIOD` only works because Step 2 marked the date table. Without that mark it returns a number, just the wrong one.

```DAX
Readings Rolling 3 Days =
CALCULATE (
    SUM ( mart_station_quality[readings_actual] ),
    DATESINPERIOD ( 'Date'[Date], MAX ( 'Date'[Date] ), -3, DAY )
)
```

1. Insert a **Line chart**. X-axis: `Date[Date]` (drag from the date table, not from the mart, or the time intelligence has nothing to walk). Y-axis: `Readings Rolling 3 Days` and `readings_actual` as a second line.
2. Set the X-axis type to **Continuous** in the Format pane so the fourteen days space evenly.
3. The first two days of the window return a partial window by design; the measure is a trailing three-day total, and there is no fifteenth day of history behind 2024-01-01 to borrow from.

## Step 7: the incident table

```DAX
Incidents = SUM ( mart_station_quality[frozen_run_count] ) + SUM ( mart_station_quality[out_of_range_count] )
```

1. Insert a **Table** visual with columns `reading_date`, `site_id`, `frozen_run_count`, `out_of_range_count`.
2. Set `frozen_run_count` and `out_of_range_count` to **Sum** so days aggregate correctly.
3. Filters pane: drag `Incidents` onto the visual, filter type **Advanced filtering**, show items when the value **is greater than** `0`, Apply.
4. The table lands on 16 station-days: 12 carrying a frozen run and 4 carrying out-of-range values, with no day carrying both. Totals across the table must be 12 frozen runs and 6 out-of-range values; the counts differ because `RNSMW` on 2024-01-14 has three out-of-range values on one day.
5. The narrative behind those rows is in the golden output's `frozen_detail` and `out_of_range_detail` sections, including the held temperature and the exact timestamps. The mart carries the counts, not the timestamps, so the table shows which day and which station, not which second.

## Step 8: the station slicer, layout, formatting

- Add a **Slicer** with `site_id`, style Dropdown, Multi-select on.
- A second slicer on `station_flag` cuts the page to the 21 flagged stations in one click.
- Suggested layout: the four cards across the top, the flagged-station matrix down the left, the rolling line top-right, the incident table bottom-right, slicers above the cards.
- Sweep the formatting: every percentage 2 decimals, every count Whole Number with a thousands separator, no default "Sum of" prefixes left in column headers.
- Page title: `NS Road Weather Station Data Quality, 2024-01-01 to 2024-01-14 UTC`.

## Step 9: save and export

1. **File > Save as**, navigate into `bi/powerbi/`, and save as `weather-station-data-quality` with save type **Power BI project files (\*.pbip)**. Desktop writes `weather-station-data-quality.pbip` plus `weather-station-data-quality.Report/` and `weather-station-data-quality.SemanticModel/` folders; all of that is text and gets committed.
2. Export the page: **File > Export > Export to PDF** into `bi/powerbi/screenshots/`, or take PNG screenshots into the same folder.
3. Do not commit any `.pbix`. The project's `.gitignore` already blocks it and `.gitattributes` marks it if one appears anyway.

---

# Numbers-match check

One assertion, three faces. With no filter or slicer applied, the worst station by completeness is **RNSKM at 59.78 percent**, and that figure must read identically in all three:

| Face | Where it reads |
| --- | --- |
| SQL | `expected/station_quality.csv`, the `headline` section, `worst_station_by_completeness`, and rank 1 of `completeness_ranking`. Also the first line of `python run.py show`. |
| Tableau | The top bar of the `Completeness Ranking` worksheet. |
| Power BI | The top row of the flagged-station matrix, `Percent Complete`. |

If a face disagrees, the usual cause is an average of `uptime_pct` where a ratio of sums belongs. Rebuild the percentage as `slots_covered` summed over `readings_expected` summed and it will land.
