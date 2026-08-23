# BI build guides: surgical wait-time SLA tracker

This project ships two BI faces, and both read the same frozen file:
`bi/exports/mart_wait_times.csv`, 2,853 facility-procedure-quarter lines written
by the SQL pipeline. Neither face recomputes a number. Nova Scotia published the
medians and 90th percentiles in that mart; the breach flags, tail gaps, and
year-quarter index were computed once in `sql/` and frozen into the file; the
two targets ride along as columns so nothing on either side has to hardcode a
threshold. Tableau and Power BI aggregate those frozen columns and display them.
When both are built, their headline figures must match the golden output and
each other, exactly.

The mart carries facility rows only. The province's own `Total` / `Provincial`
rollup rows and the rolling-window rows are not in the file, so no aggregate on
either side can double count them by accident.

---

# Tableau

## Prerequisites

Tableau Public Desktop Edition, free for Windows, plus a free public.tableau.com
account. Everything published is public, there are no private workbooks, and the
data connection is extract-only from the CSV. Publish to public.tableau.com and
keep the live link for the README. Commit the .twb XML into bi/tableau/
alongside the CSV. Never commit a .twbx.

## Connect and set types

1. Open Tableau Public. Under **Connect > To a File**, click **Text file**.
2. Browse to `bi/exports/mart_wait_times.csv` inside this project folder.
3. On the data source page, set each field's type from the icon above its column
   header. Tableau guesses most of these correctly; check all of them anyway:

   | Field | Type | Role |
   | --- | --- | --- |
   | period | String | Dimension |
   | year | Number (whole) | Dimension, convert to Discrete |
   | quarter | Number (whole) | Dimension, convert to Discrete |
   | year_quarter_index | Number (whole) | Dimension, convert to Discrete |
   | zone | String | Dimension |
   | facility | String | Dimension |
   | procedure | String | Dimension |
   | consult_median, consult_90th, consult_tail_gap | Number (whole) | Measure |
   | surgery_median, surgery_90th, surgery_tail_gap | Number (whole) | Measure |
   | surgery_target_days, consult_target_days | Number (whole) | Measure |
   | surgery_measured, surgery_breach | Number (whole) | Measure |
   | consult_measured, consult_breach | Number (whole) | Measure |

   `year`, `quarter`, and `year_quarter_index` land as measures because they are
   numbers. Drag each into the Dimensions section of the data pane and
   right-click it > **Convert to Discrete**. They are labels here, not
   quantities, and nothing should ever sum them.
4. Leave every blank as blank. A missing `surgery_median` means the source
   published no median for that line. Do not fill it with zero; Tableau's
   aggregates skip nulls, which is the behaviour the golden output expects.
5. Click **Sheet 1** to start building.

## Sheet 1: quarter-by-year heatmap of surgery_median (table calculation)

1. New worksheet, rename it `Median by Quarter`.
2. Drag `year` to **Columns** and `quarter` to **Rows**. Both should be blue
   (discrete) pills.
3. Drag `surgery_median` to **Color** on the Marks card. Set the mark type
   dropdown to **Square**. You now have a 3-by-4 grid with three empty cells:
   the window starts at 2023 Q2 and ends at 2025 Q2, so 2023 Q1, 2025 Q3, and
   2025 Q4 have no data.
4. Change the aggregation on the Color pill to **Average**: click the pill,
   **Measure > Average**.
5. Replace the plain average with the table calculation. Create a calculated
   field (**Analysis > Create Calculated Field**), name it
   `Median vs Window Average`, and enter exactly:

       AVG([surgery_median]) - WINDOW_AVG(AVG([surgery_median]))

   Drag it onto **Color**, replacing `AVG(surgery_median)`.
6. Set what the calculation runs across: right-click the pill on Color,
   **Edit Table Calculation**, **Compute Using > Table (across then down)**.
   `WINDOW_AVG` then averages all nine populated cells, and each cell shows its
   own distance from that window average in days.
7. Colour it as a diverging palette centred on zero: click the Color legend's
   dropdown, **Edit Colors**, choose **Orange-Blue Diverging**, tick
   **Center** and set it to 0. Cells above the window average and below it now
   read apart at a glance.
8. Drag `surgery_median` to **Label** and set that pill to **Average**, then
   drag `surgery_median` to **Tooltip** a second time and set that pill to
   **Maximum**. The label carries the cell's average and the tooltip carries the
   single longest published median in that quarter, which is the figure the
   numbers-match check at the bottom of this file uses.

   Read the averages for what they are. Averaging published medians across
   facility lines is a display aggregate for shading the grid, not a recomputed
   percentile and not a provincial median. Every exact figure in the golden
   output is a count, a rate, or one published line.

## Sheet 2: breach percentage as a FIXED LOD (filter-independent)

Two fields, built together, because the contrast between them is the point.

1. New worksheet, rename it `Breach Rate`.
2. Create a calculated field named `Surgery Breach Pct` and enter exactly:

       SUM([surgery_breach]) / SUM([surgery_measured])

   This one follows the view: whatever dimensions and filters are applied, it
   divides the breaching lines by the measured lines inside that context.
3. Create a second calculated field named `Surgery Breach Pct (All Data)` and
   enter exactly:

       MIN({ FIXED : SUM([surgery_breach]) }) / MIN({ FIXED : SUM([surgery_measured]) })

   The empty `{ FIXED : ... }` declaration computes each total once over the
   whole extract, ignoring every dimension in the view and every dimension
   filter on it. That is what makes this a fixed benchmark rather than a
   recalculated rate.

   Two details worth getting right. First, the outer `MIN` is not decoration: a
   FIXED expression coarser than the view is replicated onto every underlying
   row, so wrapping it in `SUM` would multiply the total by the row count.
   `MIN`, `MAX`, or `AVG` all collapse the replicated constant back to itself;
   `SUM` does not. Second, FIXED expressions ignore dimension filters but obey
   context filters, so leave the zone and quarter filters as ordinary filters.
   The moment you right-click one and choose **Add to Context**, this field
   stops being filter-independent.
4. Format both fields as percentages: right-click each in the data pane,
   **Default Properties > Number Format > Percentage**, 2 decimal places.
5. Build the view: `facility` on **Rows**, `Surgery Breach Pct` on **Columns**,
   sorted descending by the measure.
6. Add the benchmark: drag `Surgery Breach Pct (All Data)` to **Detail**, then
   right-click the axis and choose **Add Reference Line**. Set Value to
   `Surgery Breach Pct (All Data)` with aggregation **Minimum**, Line only, and
   label it Value. The reference line sits at 10.11 percent and stays at 10.11
   percent when the dashboard is filtered to one zone, while the bars move.
7. Drag `surgery_measured` to **Tooltip** and set that pill to **Sum**, so every
   bar shows the denominator behind its rate. Glace Bay's 25.00 percent is 2
   lines out of 8; QE2's 9.88 percent is 76 out of 769. The golden output flags
   the same distinction with its `meets_min_rows` column.

## Sheet 3: median against 90th percentile per procedure (dumbbell)

This is the tail-gap view. Each procedure gets two dots, the median and the 90th
percentile, joined by a line whose length is the gap.

1. New worksheet, rename it `Median vs 90th`.
2. Drag `procedure` to **Rows**.
3. Drag **Measure Values** to **Columns**. In the Measure Values shelf that
   appears in the lower left, remove everything except `AVG(surgery_median)` and
   `AVG(surgery_90th)`. Change each remaining pill's aggregation to **Average**
   if it defaulted to Sum.
4. On the Marks card, set the mark type to **Circle**. Drag **Measure Names**
   to **Color**, and drag `surgery_tail_gap` to **Tooltip** with aggregation
   **Average**. You now have two dots per procedure and no connector.
5. Add the connector. Hold Ctrl and drag the **Measure Values** pill on Columns
   to the right, dropping it beside itself. You now have two identical pills and
   two Marks cards, one per pill.
6. On the **second** Marks card only: set the mark type to **Line**, drag
   **Measure Names** from Color to **Path**, and set the Color to a single mid
   grey. The line now runs from the median dot to the 90th dot.
7. Right-click the second Columns pill and choose **Dual Axis**.
8. Right-click the top axis and choose **Synchronize Axis**. Both series must
   share one scale or the dots and the line will not line up.
9. Right-click the top axis again and untick **Show Header**, so only one axis
   shows.
10. Sort the rows by gap: **Analysis > Create Calculated Field**, name it
    `Sort by Tail Gap`, enter exactly:

        AVG([surgery_90th]) - AVG([surgery_median])

    then click the `procedure` pill on Rows, **Sort**, Sort By **Field**,
    Descending, Field Name `Sort by Tail Gap`, Aggregation **Average**.
11. Keep it readable: drop `procedure` on the Filters shelf, choose the
    **Top** tab, **By Field**, Top 20 by `Sort by Tail Gap`, Average.

Same caution as Sheet 1. With no filters, each dot is an average across the
facility lines for that procedure, which is a display aggregate. Filter the
dashboard down to one zone and one quarter and each procedure has exactly one
line, so the dots read that line's published numbers exactly. The numbers-match
check below uses that fact.

The consult pair builds identically from `consult_median` and `consult_90th`.
Fewer procedures carry one: 669 of the 2,853 lines publish no consult median, so
expect gaps in that version of the chart.

## Sheet 4: dashboard with zone and quarter filters

1. Click **New Dashboard**. Size: Automatic.
2. Drag `Median by Quarter` to the top left, `Breach Rate` to the top right, and
   `Median vs 90th` across the bottom.
3. Add the zone filter: open the `Breach Rate` sheet, drag `zone` to the
   **Filters** shelf, tick all five values, and click OK. Back on the dashboard,
   click the `Breach Rate` object's dropdown arrow > **Filters > Zone**. Set the
   control to **Multiple Values (dropdown)**.
4. Add the quarter filter the same way with `period`, which is the quarter label
   (`2023_q2` through `2025_q2`). Set that control to **Multiple Values (list)**
   so several quarters can be selected at once.
5. Make both filters reach every sheet: on each filter control's dropdown,
   choose **Apply to Worksheets > All Using This Data Source**.
6. Give the dashboard a title: "NS Surgical Wait Times against a 182-day median
   target, 2023 Q2 to 2025 Q2".
7. Add a caption text object stating the target and its status, because a
   dashboard that shows breaches without naming the line it drew invites the
   wrong reading: "Breach means a published surgery median above 182 days. That
   target is an assumption of this build, not an official standard."

## Publish and file the artifacts

1. **File > Save to Tableau Public As...**, sign in, name it
   `NS Surgical Wait Time SLA`. Publishing uploads the extract and opens the viz
   in a browser; copy the live link from the address bar and paste it at the top
   of this file.
2. Download the workbook: on the viz page, **Download > Tableau Workbook**, or
   in the desktop app **File > Export As** where offered. Save the `.twb` into
   `bi/tableau/` and commit it alongside the CSV. Do not commit `.twbx`; the
   packaged extract duplicates the data.
3. Screenshots into `bi/tableau/screenshots/`: the full dashboard unfiltered,
   and one filtered to zone IWK and period 2024_q2.

---

# Power BI

## Prerequisites

Power BI Desktop, free from the Microsoft Store. Enable File > Options >
Preview features > "Power BI Project (.pbip) save option". No service account
and no tenant is needed. The free deliverable is the committed .pbip plus
exported PNG or PDF, because Publish to web is not available on the free tier.
Commit the .pbip .Report and .SemanticModel text folders. Never commit a .pbix.

## Connect to the same mart in Import mode

1. Home > **Get Data** > **Text/CSV**.
2. Browse to `bi/exports/mart_wait_times.csv`, the same file Tableau connects to.
3. In the preview dialog choose **Transform Data**, not Load, so the types get
   set explicitly.
4. In Power Query, set each column type from its type icon:

   | Column | Type |
   | --- | --- |
   | period | Text |
   | year, quarter, year_quarter_index | Whole Number |
   | zone, facility, procedure | Text |
   | consult_median, consult_90th, consult_tail_gap | Whole Number |
   | surgery_median, surgery_90th, surgery_tail_gap | Whole Number |
   | surgery_target_days, consult_target_days | Whole Number |
   | surgery_measured, surgery_breach | Whole Number |
   | consult_measured, consult_breach | Whole Number |

5. Leave blanks as null. Do not use **Replace Values** to turn them into 0. A
   null median means the source published none, and a 0 would silently become a
   line that passed the target.
6. **Close & Apply**. Connection mode is Import, the default for CSV. Nothing
   here needs DirectQuery.
7. Turn off implicit summarization on the label columns so nothing ever sums
   them: select `year`, `quarter`, and `year_quarter_index` in the Data pane and
   set **Column tools > Summarization > Don't summarize**. Do the same for
   `surgery_target_days` and `consult_target_days`.

## A note on dates before any DAX gets written

This mart has no date column at all, and it is not going to get one. Do not use
`SAMEPERIODLASTYEAR`, `DATEADD`, `PREVIOUSQUARTER`, `PARALLELPERIOD`, or any
other time-intelligence function anywhere in this report. They will either error
or return silently wrong answers.

Adding a bare date column would not fix it either. DAX time intelligence needs a
proper date table, contiguous with no gaps, marked with **Mark as date table**,
and related to the fact table. This data is quarterly with a nine-quarter window
that does not start in Q1, so a date table would be scaffolding built to make a
function work rather than because the data has dates in it.

The mart carries `year_quarter_index` instead: `year * 4 + quarter`, running
8094 to 8102, one step per quarter, previous quarter always at index minus one
including across a year boundary. Every period-over-period measure below indexes
on that integer. It is the correct approach for this shape of data.

## Step 1: the SLA KPI card

Modeling > **New measure**, once per measure.

```DAX
Surgery Breach % =
DIVIDE (
    CALCULATE ( SUM ( mart_wait_times[surgery_breach] ) ),
    CALCULATE ( SUM ( mart_wait_times[surgery_measured] ) )
)
```

```DAX
Consult Breach % =
DIVIDE (
    CALCULATE ( SUM ( mart_wait_times[consult_breach] ) ),
    CALCULATE ( SUM ( mart_wait_times[consult_measured] ) )
)
```

`DIVIDE` rather than `/` because a slicer combination can leave a visual with no
measured lines at all; `DIVIDE` returns blank there instead of an infinity
error. `CALCULATE` wraps each `SUM` so both halves evaluate in the same filter
context the visual hands them, which keeps the ratio right when the measure is
nested inside the prior-quarter measure in Step 2.

Format both as Percentage with 2 decimal places (Measure tools > Format).

Insert two **Card** visuals, one per measure. With no slicers applied, the
surgery card must read **10.11%** and the consult card **30.72%**.

Add a third card for the raw denominator so the card row is honest about its
base:

```DAX
Surgery Lines Measured = SUM ( mart_wait_times[surgery_measured] )
```

It reads 2,729 unfiltered, out of 2,853 published lines. The 124-line difference
is lines where the source published no surgery median.

## Step 2: the prior-quarter comparison

```DAX
Surgery Breach % Prior Quarter =
VAR CurrentQuarterIndex = MAX ( mart_wait_times[year_quarter_index] )
RETURN
    CALCULATE (
        [Surgery Breach %],
        REMOVEFILTERS (
            mart_wait_times[year_quarter_index],
            mart_wait_times[period],
            mart_wait_times[year],
            mart_wait_times[quarter]
        ),
        mart_wait_times[year_quarter_index] = CurrentQuarterIndex - 1
    )
```

```DAX
Surgery Breach % vs Prior Quarter =
VAR Prior = [Surgery Breach % Prior Quarter]
RETURN
    IF ( NOT ISBLANK ( Prior ), [Surgery Breach %] - Prior )
```

Format `Surgery Breach % vs Prior Quarter` as Percentage, 2 decimals.

All four period columns get removed together, not just the index. `period`,
`year`, and `quarter` describe the same quarter as `year_quarter_index` does, so
leaving any of them in filter context would fight the index predicate and return
blank. Everything else stays: `zone`, `facility`, and `procedure` keep their
filters, so a facility row compares against its own previous quarter.

`IF ( NOT ISBLANK ( Prior ) ... )` keeps the first quarter in the window blank
rather than showing its own rate as if the previous quarter had been zero. That
matches the golden output, where `2023_q2` has no quarter-over-quarter value.

Insert a **Line chart**: X-axis `period`, Y-axis `Surgery Breach %`. Add
`Surgery Breach % Prior Quarter` as a second line to see the one-quarter lag
directly. Sort the X-axis by `year_quarter_index` ascending, not by the `period`
text: click the visual's **More options (...)** > **Sort axis** >
`year_quarter_index` > Sort ascending.

## Step 3: facility by quarter matrix with conditional formatting

1. Insert a **Matrix** visual.
2. Rows: `facility`. Columns: `period`. Values: `Surgery Breach %`.
3. Sort the columns chronologically: with `period` as text the sort is already
   correct here, because `YYYY_qN` sorts the same way as time. Confirm it reads
   `2023_q2` on the left and `2025_q2` on the right.
4. Add the conditional formatting: in the Values well, click the dropdown on
   `Surgery Breach %` > **Conditional formatting** > **Background color**.
   - Format style: **Rules**.
   - Format by: **Field value** is not what you want here; leave it on
     **Rules** and set the rules against `Surgery Breach %`.
   - Rule 1: if value **is greater than or equal to** 0 and **is less than**
     0.05, background light green.
   - Rule 2: if value is greater than or equal to 0.05 and is less than 0.15,
     background light amber.
   - Rule 3: if value is greater than or equal to 0.15 and is less than or equal
     to 1, background light red.

   The values are decimals, not percentages: 0.15 means 15 percent. Set the
   number field beside each rule to **Number**, not Percent, or the thresholds
   will be off by a factor of one hundred.
5. Add a second value, `Surgery Lines Measured`, so a red cell built on three
   lines is not read like one built on ninety. Small facilities publish few
   lines per quarter and their rates swing hard.
6. Blank cells are correct and should stay blank. A facility that published no
   measured surgery line for a procedure in a quarter has nothing to rate.

## Step 4: the tail-gap measure

```DAX
Avg Surgery Tail Gap =
CALCULATE (
    AVERAGE ( mart_wait_times[surgery_tail_gap] ),
    mart_wait_times[surgery_measured] = 1
)
```

```DAX
Max Surgery Tail Gap =
CALCULATE (
    MAX ( mart_wait_times[surgery_tail_gap] ),
    mart_wait_times[surgery_measured] = 1
)
```

Format both as Whole Number with a thousands separator, and rename the display
unit in the visual to days.

The `surgery_measured = 1` filter is belt and braces. `surgery_tail_gap` is
already blank on any line with no published median, and `AVERAGE` skips blanks,
but stating the condition means the measure still reads correctly if the mart
ever gains a line where one half of the pair is published and the other is not.

Unfiltered, `Avg Surgery Tail Gap` reads **143.54** days and
`Max Surgery Tail Gap` reads **1,323** days.

Add a **Clustered bar chart**: Y-axis `procedure`, X-axis `Avg Surgery Tail
Gap`, filtered to Top 20 by that measure (Filters pane > `procedure` > Filter
type **Top N** > Show items Top 20 By value `Avg Surgery Tail Gap`).

## Step 5: the zone slicer, layout, formatting

- Insert a **Slicer** with `zone`. Five values: `Zone 1` through `Zone 4` and
  `IWK`. Set it to **Dropdown** with multi-select on. Every measure above
  responds to it, because none of them use `ALL` or `REMOVEFILTERS` on `zone`.
- Suggested layout: slicer and the three cards along the top, the quarter line
  chart below them, the facility-by-quarter matrix bottom left, the tail-gap
  bars bottom right.
- Sweep the formatting: every percentage 2 decimals, every day figure whole
  numbers with separators, matrix text small enough that all nine quarters fit
  without scrolling.
- Page title: "NS Surgical Wait Times against a 182-day median target, 2023 Q2
  to 2025 Q2". Add a text box under it naming the assumption plainly: "Breach
  means a published surgery median above 182 days. That target is an assumption
  of this build, not an official standard."

## Save and export

1. **File > Save as**, navigate into `bi/powerbi/`, and save as
   `surgical-wait-time-sla` with save type **Power BI project files (*.pbip)**.
   Desktop writes `surgical-wait-time-sla.pbip` plus the
   `surgical-wait-time-sla.Report/` and `surgical-wait-time-sla.SemanticModel/`
   folders. All of that is text and gets committed.
2. Export the visuals: **File > Export > Export to PDF** into
   `bi/powerbi/screenshots/`, or take PNG screenshots of the report page into
   the same folder.
3. Do not commit any `.pbix`. The repo's `.gitignore` already blocks it.

---

# Numbers-match check

One line has to read identically in all three faces. The longest published
surgery median anywhere in the mart belongs to the **IWK**, procedure **Dental
Extractions and Restorations (Adult)**, period **2024_q2**: **surgery_median 560
days**, with the 90th percentile at 1,301 days and a tail gap of 741 days.

Where to read it in each face:

- **SQL**: `expected/wait_time_sla.csv`, section `worst_lines`, rank 1. Also
  visible in `python run.py show` as the top facility's worst line, 560.
- **Tableau**: on the dashboard, set the zone filter to `IWK` and the quarter
  filter to `2024_q2`. The IWK zone holds one facility, so every procedure now
  has exactly one line and the averages equal that line. On `Median vs 90th`,
  the `Dental Extractions and Restorations (Adult)` dumbbell reads 560 and 1,301
  with a 741-day connector. The `Median by Quarter` heatmap tooltip for 2024 Q2
  reads a maximum of 560 with no filters applied at all.
- **Power BI**: apply the `zone` slicer to `IWK`, then read the matrix cell for
  IWK at `2024_q2`, which is 40.91 percent on 22 measured lines. Add
  `Longest Surgery Median = MAX ( mart_wait_times[surgery_median] )` as a card:
  it reads 560 filtered to IWK and 560 unfiltered, because that line is the
  longest in the mart.

If any of those differ, the mart loaded is stale or a type got set wrong.
Re-run `python run.py` from the project folder, confirm PASS, and reconnect. The
SQL golden output is the arbiter in every disagreement.
