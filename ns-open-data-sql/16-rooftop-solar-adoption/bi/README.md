# Tableau build guide: rooftop solar adoption

This folder holds the Tableau Public side of the project. The SQL pipeline exports a
Tableau-ready mart to `exports/mart_solar.csv`; this guide walks through building and
publishing the viz from that file, step by step. The base project is complete without
it, so this build can happen any time after a `python run.py` PASS.

## Why Tableau Public for this dataset

The mart is FSA-level geography (the first three characters of a postal code) plus a
time series, which is the exact shape Tableau handles well and a plain browser dashboard
handles poorly: Tableau geocodes Canadian FSAs natively, so a map of installs by region
takes minutes, and the same data feeds a dual-axis growth chart with a built-in running
total. Publishing also produces a live link anyone can open without installing anything.
Sheets 2 and 3 spell out the two formulas this data shape calls for, a FIXED
level-of-detail expression and a running-total table calculation, exactly as typed.

## Prerequisites

- Tableau Public Desktop Edition for Windows, free from https://public.tableau.com
  (Download on the top nav). Install with defaults.
- A free public.tableau.com account (Sign Up on the same page). Vizzes published with
  Tableau Public are public; that is fine here because the data is already open data.
- Tableau Public works extract-only from files: it loads the CSV into an extract when
  you publish. It needs no database connection.

## Connect the data

1. Open Tableau Public. On the start page, under **Connect > To a File**, click
   **Text file**.
2. Browse to this project folder and open `bi/exports/mart_solar.csv`.
3. On the data source page, check the field types Tableau inferred:
   - `fsa` should be a string (Abc icon).
   - `year` may arrive as a number. Leave it as a whole number; the charts below use it
     as a discrete dimension.
   - `installs` should be a whole number, `installed_kw` a decimal.
4. Give `fsa` its geographic role: click the icon above the `fsa` column header (or
   right-click the field in the data pane on a worksheet), then
   **Geographic Role > Postal Code**. Set the workbook location to Canada first if
   Tableau asks: **Map > Edit Locations > Country/Region > Canada**.
5. Click **Sheet 1** to start building.

## Sheet 1: installs by region (map)

1. Rename the sheet `Installs by FSA`.
2. Double-click `fsa` in the data pane. With the Postal Code role set, Tableau puts
   generated Latitude and Longitude on Rows and Columns and draws a symbol map.
3. Drag `installs` to **Size** on the Marks card and again to **Color**. Set the mark
   type dropdown to **Circle**.
4. Drag `installed_kw` to **Tooltip** so hovering a circle shows both measures.
5. If unknown values appear (bottom right corner shows "N unknown"), click the
   indicator, choose **Edit Locations**, and confirm the country is Canada. FSAs that
   still do not geocode stay in the unknown bucket; note the count.

**Fallback if FSAs do not geocode cleanly.** Tableau's Canadian postal-code coverage at
the FSA level varies by version. If the map leaves a large share of rows unknown, build
the same sheet as ranked bars instead: put `fsa` on Rows, `SUM(installs)` on Columns,
sort descending by `installs`, drag `installed_kw` to Tooltip, and use **Filter >
Top > By Field > Top 15 by SUM(installs)** to keep it readable. Every later step works
the same with the bar version.

## Sheet 2: each region's share of provincial installs (FIXED LOD)

1. New worksheet, rename it `Share of Province`.
2. Create a calculated field (**Analysis > Create Calculated Field**), name it
   `FSA Share of Installs`, and enter exactly:

       SUM([installs]) / SUM({ FIXED : SUM([installs]) })

   The `{ FIXED : ... }` part computes the provincial total once, ignoring whatever
   dimensions are on the view, so each FSA's bar divides by the same denominator even
   when a year filter is active later. Note for the numbers check: with no filters
   applied, the denominator equals the total install count printed in the mart.
3. Format the field as a percentage: right-click it in the data pane,
   **Default Properties > Number Format > Percentage**, 1 decimal place.
4. Put `fsa` on Rows and `FSA Share of Installs` on Columns, sort descending.
5. Add `SUM(installs)` to Tooltip so each bar shows the raw count behind the share.

## Sheet 3: growth curve (dual axis with a running total)

1. New worksheet, rename it `Growth Curve`.
2. Drag `year` to Columns. Right-click the pill and pick **Discrete** if it is not
   already (blue pill).
3. Drag `installs` to Rows. This is the annual bar series: set its mark type to **Bar**.
4. Drag `installs` to Rows a second time, next to the first pill. On this second pill,
   right-click and choose **Quick Table Calculation > Running Total**. Confirm it is
   computing across `year`: right-click the pill again, **Edit Table Calculation**, and
   set **Compute Using > Specific Dimensions** with `Year` checked. Written out, the
   calculation Tableau applies is exactly:

       RUNNING_SUM(SUM([installs]))

5. Right-click the second pill and choose **Dual Axis**. Leave the axes unsynchronized:
   the cumulative scale should float above the annual scale, so skip **Synchronize
   Axis** if Tableau offers it.
6. Set the second series' mark type to **Line**. You now have annual bars with a
   cumulative line over them.
7. The last point of the running-total line must equal the total install count from the
   golden output (numbers check below).

## Sheet 4: dashboard with a year filter

1. Click **New Dashboard**. Size: Automatic.
2. Drag `Growth Curve` to the top, `Installs by FSA` (map or bar fallback) bottom left,
   `Share of Province` bottom right.
3. Add the year filter: on the Growth Curve sheet, drag `year` to the Filters shelf,
   choose all years, then on the dashboard click the Growth Curve object's dropdown,
   **Filters > Year**. Set the filter control to **Single Value (dropdown)** plus an
   **(All)** option.
4. Make the filter apply everywhere: click the filter control's dropdown,
   **Apply to Worksheets > All Using This Data Source**.
5. Note the LOD behaviour when a single year is selected: the map and the growth curve
   reflect that year only, while `FSA Share of Installs` still divides by the fixed
   provincial all-years total. That contrast is the point of the FIXED expression.

## Numbers must match the golden output

With no filters applied, the finished viz must read identically to the SQL golden
output in `expected/solar_adoption.csv`:

- Total installations: **6,019** (the last point of the running-total line, and the sum
  the FIXED denominator computes).
- Total installed capacity: **62,489.47 kW** (SUM of `installed_kw` across the mart).
- Leading region: **B0J** with **398** installs (6.6% of the province), first in the
  ranked share view and the largest mark on the map.

If any of these differ, the CSV loaded is stale: re-run `python run.py` from the project
root and reconnect the extract (**Data > Refresh** or re-open the file).

## Publish and file the artifacts

1. **File > Save to Tableau Public As...**, sign in, name it
   `NS Rooftop Solar Adoption`. Publishing uploads the extract and opens the viz in a
   browser; copy the live link from the address bar.
2. Download the workbook file: on your viz page on public.tableau.com, use
   **Download > Tableau Workbook**, or in the desktop app **File > Export As** where
   offered. Save the `.twb` into `bi/tableau/` and commit it together with the CSV the
   guide connects to. Do not commit `.twbx` files; the packaged extract duplicates the
   data and bloats the repo.
3. Take screenshots of the published dashboard (full view plus one with a single year
   selected) into `bi/tableau/screenshots/`.
4. Paste the live link at the top of this file when done.
