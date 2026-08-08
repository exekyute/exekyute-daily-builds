# BI build guides: 311 call service levels

Both dashboards read one frozen file, `bi/exports/mart_311_monthly.csv`. One row is
one calendar month: 115 rows from 2017-01 through 2026-07, ordered by `month_start`,
carrying that month's offered, handled, abandoned, and IVR-processed calls, its total
talk time, and its three derived rates. The SQL pipeline writes that file; neither
Tableau nor Power BI recomputes any of the analysis, so a figure read off one dashboard
equals the same figure on the other and in the SQL golden. Column meanings, units, and
the ratio-of-sums rule for year-level rates are in `bi/exports/data_dictionary.md`.

Tableau live link: https://public.tableau.com/views/Halifax311CallServiceLevels/311servicelevels

- [Tableau guide](#tableau-guide-heatmap-and-dual-axis)
- [Power BI guide](#power-bi-guide-time-intelligence-cards)
- [Numbers must match](#numbers-must-match)

---

## Tableau guide: heatmap and dual axis

### What this dashboard shows

A year-by-month grid of the abandonment rate, coloured light to dark, with a column
grand total under each year giving that year's own rate. Beneath it, monthly offered
calls and monthly handled calls on a synchronized dual axis across the full 2017 to
2026 span. One year filter drives both.

### Prerequisites

- Tableau Public Desktop Edition, free from https://public.tableau.com (Download on the
  top nav). Install with defaults.
- A free public.tableau.com account (Sign Up on the same page). Anything published from
  Tableau Public is public, which is fine here because the source is open data.
- Tableau Public works extract-only from files. It loads the CSV into an extract on
  publish and needs no database connection.

### Connect the data

1. Open Tableau Public. Under **Connect > To a File**, click **Text file**.
2. Browse to `bi/exports/mart_311_monthly.csv` and open it.
3. On the data source page, check the types Tableau inferred:
   - `month_start` should be a Date.
   - `year`, `month`, `offered`, `handled`, `abandoned`, `processed_in_ivr`,
     `total_talk_time` should be whole numbers (#).
   - `abandonment_rate`, `answer_rate`, `avg_talk_time` should be numbers (#), decimal.
   Leave the connection on **Extract**.
4. Rename the two rate columns so the calculated fields below can take the plain names:
   `abandonment_rate` to `Abandonment Rate (source)` and `answer_rate` to
   `Answer Rate (source)`. Neither is used on a sheet; the dashboard derives both rates
   from the counts instead.
5. Click **Sheet 1** to start building.

### Sheet 1: Abandonment heatmap

1. Rename the sheet `Abandonment heatmap`.
2. Drag `month_start` to **Columns** and set the pill to discrete `YEAR(month_start)`
   (blue). Drag a second `month_start` to **Rows** and set it to discrete
   `MONTH(month_start)` (blue). The grid is now years across, months down.
3. Create the calculated field, named `Abandonment Rate`, formula verbatim:

       SUM([abandoned]) / SUM([offered])

   Format it as Percentage with 2 decimal places (the workbook stores `p0.00%`).
4. Drag `Abandonment Rate` to **Color** and drop a second copy on **Text**. Set the
   Marks type to **Square**. Pick the sequential **Red** ramp so the worst months read
   darkest, and turn on **Show mark labels** with **Allow labels to overlap** left off.
5. Turn off the column field label: right-click the year header area and untick
   **Show Field Labels for Columns**.
6. **Analysis > Totals > Show Column Grand Totals**. That adds the Total row at the
   bottom of the grid, and because the calculated field divides summed abandoned by
   summed offered, each year's total cell is that year's true rate rather than an
   average of its twelve monthly rates.
7. Drag `month_start` to **Filters**, choose **Years**, and tick all ten members, 2017
   through 2026. Right-click the pill and choose **Apply to Worksheets > All Using This
   Data Source** so the same filter reaches sheet 2.

### Sheet 2: Offered vs handled

1. New worksheet, rename it `Offered vs handled`.
2. Drag `month_start` to **Columns**, then open the pill dropdown and pick **Month**
   from the **lower** continuous group (shown as `May 2015`) so the pill turns green.
   Continuous Month truncates to the month but keeps the year, so 2025-01 and 2026-01
   stay separate points across the whole span.
3. Drag `offered` to **Rows**, then drag `handled` to **Rows** beside it. Both pills
   should read `SUM(...)`.
4. Right-click the second axis and choose **Dual Axis**, then right-click either axis
   and choose **Synchronize Axis**. Set the Marks type to **Line** on both panes.
5. `Measure Names` lands on **Color**, which is what separates the offered line from the
   handled line. Leave it there.
6. Create the second calculated field, named `Answer Rate`, formula verbatim:

       SUM([handled]) / SUM([offered])

   Format it as Percentage with 2 decimal places and drag it to **Tooltip**, so hovering
   a month reads its offered count, its handled count, and the share answered.

### Dashboard

1. Click **New Dashboard**. Set Size to **Fixed size**, 1200 by 950.
2. Drag `Abandonment heatmap` into the top of the canvas and `Offered vs handled`
   underneath it, giving the heatmap roughly the top 40 percent of the height.
3. Down the right side, in a fixed 160 pixel column, keep three cards: the
   `YEAR(month_start)` filter, the `Abandonment Rate` colour legend from the heatmap,
   and the `Measure Names` colour legend from the lines. Remove any duplicate cards the
   second sheet adds.
4. Name the dashboard `311 service levels`. Tableau generates a stacked Phone layout
   automatically; leave it as generated.

### Publish and file the artifacts

Tableau Public Desktop has no local save to disk. Both **File > Save** and
**File > Save As** redirect to **Save to Tableau Public As...**, which uploads to the
Tableau Public cloud, so getting the committable `.twb` runs through the cloud and a
`.twbx` unzip.

1. **File > Save to Tableau Public As...**, sign in, and name the workbook
   `Halifax 311 Call Service Levels`. Publishing uploads the extract and opens the viz
   in a browser at the live link above.
2. On the viz page, click **Download Workbook**. It always comes down as a `.twbx`
   (packaged), never a bare `.twb`.
3. A `.twbx` is a zip. Copy it, rename the copy to `.zip`, unzip it, and take the `.twb`
   from the archive root. Commit that file as
   `bi/tableau/311_call_service_levels.twb`. Never commit the `.twbx`: the packaged
   extract duplicates the data, bloats the repo, and does not diff.
4. Put screenshots in `bi/tableau/screenshots/`. The committed one is
   `dashboard-full.png`.

---

## Power BI guide: time intelligence cards

### What this report shows

One page holding a year slicer set to 2025, four cards (abandonment rate, answer rate,
total offered, and a rolling three-month offered total), and a line chart of monthly
offered calls against the same months a year earlier. The prior-year line and the
rolling total both come from a marked date table.

### Import and type the data

1. **Home > Get Data > Text/CSV**, choose `bi/exports/mart_311_monthly.csv`, then
   **Transform Data** to open Power Query.
2. Set the column types:
   - `month_start` = Date
   - `year`, `month`, `offered`, `handled`, `abandoned`, `processed_in_ivr`,
     `total_talk_time` = Whole Number
   - `abandonment_rate`, `answer_rate`, `avg_talk_time` = Decimal Number
3. **Close & Apply**. The table lands as `mart_311_monthly`.

### Add a date table

Modeling > New table:

    Date = CALENDAR ( MIN ( mart_311_monthly[month_start] ), MAX ( mart_311_monthly[month_start] ) )

Add two calculated columns on it:

    Year = YEAR ( 'Date'[Date] )

    Month Start = DATE ( YEAR ( 'Date'[Date] ), MONTH ( 'Date'[Date] ), 1 )

Mark it as a date table (**Table tools > Mark as date table**, on the `[Date]` column).
In Model view, create the relationship from `mart_311_monthly[month_start]` to
`Date[Date]`, many-to-one, single direction. Every time-intelligence measure below reads
`'Date'[Date]`, so the mark and the relationship are both required.

### Measures (enter each verbatim)

    Total Offered = SUM ( mart_311_monthly[offered] )

    Total Handled = SUM ( mart_311_monthly[handled] )

    Total Abandoned = SUM ( mart_311_monthly[abandoned] )

    Abandonment Rate = DIVIDE ( [Total Abandoned], [Total Offered] )

    Answer Rate = DIVIDE ( [Total Handled], [Total Offered] )

    Offered LY = CALCULATE ( [Total Offered], SAMEPERIODLASTYEAR ( 'Date'[Date] ) )

    Offered Rolling 3M = CALCULATE ( [Total Offered], DATESINPERIOD ( 'Date'[Date], MAX ( 'Date'[Date] ), -3, MONTH ) )

Format `Abandonment Rate` and `Answer Rate` as Percentage with 2 decimal places (the
model stores `0.00%;-0.00%;0.00%`). Leave the five count measures on the whole-number
format `0`.

Both rates divide summed counts, which is why they hold at any grain: the same measure
gives a month's rate in the line chart's tooltip and a year's rate on the card.

### Visuals

- **Slicer**: `Date[Year]`, set to **Dropdown** mode, with 2025 selected. It filters
  every other visual on the page.
- **Card**: `[Abandonment Rate]`.
- **Card**: `[Answer Rate]`.
- **Card**: `[Total Offered]`, display units set to **None** so it prints the full count.
- **Card**: `[Offered Rolling 3M]`, display units set to **None**.
- **Line chart**: X axis `Date[Month Start]` sorted ascending, Y values `[Total Offered]`
  and `[Offered LY]`, so each month sits against the same month a year earlier.

The page is 1280 by 720, set to **Fit to page**, with the slicer and the four cards in a
row across the top and the line chart filling the rest.

### Save and file the artifacts

1. Turn on the project save format: **File > Options and settings > Options > Preview
   features > Power BI Project (.pbip) save option**, then restart if prompted.
2. **File > Save As**, choose **Power BI project files (.pbip)**, and save into
   `bi/powerbi/` as `311_call_service_levels`. Commit the `.pbip` file together with its
   `.Report/` and `.SemanticModel/` text folders. Never commit a `.pbix`; the binary
   duplicates the data and does not diff.
3. Free Power BI Desktop has no public publish link, so the deliverable is the committed
   project plus an exported PNG or a **File > Export > PDF**. The committed screenshot is
   `bi/powerbi/screenshots/report.png`.

---

## Numbers must match

**The 2025 abandonment rate reads 2.75 percent**, from 10,037 abandoned calls out of
365,053 offered, and it is the same figure in all three places:

- **SQL golden**: `expected/monthly_service_levels.csv`, column `year_abandonment_rate`,
  on every 2025 row, reads `0.0275`. The same rows carry `year_abandoned` 10,037 and
  `year_offered` 365,053.
- **Tableau**: on the `Abandonment heatmap` sheet, the Total cell at the bottom of the
  2025 column reads 2.75%, because `SUM([abandoned]) / SUM([offered])` evaluates over the
  year's twelve months at once. The twelve monthly cells above it range from 0.86% in
  January to 6.26% in February, and averaging those twelve returns 2.61%, not the year's
  rate.
- **Power BI**: with the `Date[Year]` slicer set to 2025, the `[Abandonment Rate]` card
  reads 2.75%, the `[Total Offered]` card reads 365,053, and the `[Answer Rate]` card
  reads 65.11%.

If any of those figures differs, the loaded CSV is stale: re-run `python run.py` from the
project folder, then reconnect or refresh the extract.
