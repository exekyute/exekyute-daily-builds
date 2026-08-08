# BI build guides: EV charging network growth

Both dashboards read one frozen file, `bi/exports/mart_ev.csv`, written by the SQL
export step. One row is one installed, publicly accessible HRM charging station, 33
rows in total. Neither tool recomputes any of the analysis: each aggregates the mart
as written, so a figure read off the Tableau dashboard equals the same figure on the
Power BI report and in the SQL golden. Every measure below counts stations, not
ports. Column meanings are in `bi/exports/data_dictionary.md`.

Tableau live link: https://public.tableau.com/views/HalifaxEVChargingNetworkGrowth/HalifaxEVChargingNetworkGrowth

- [Tableau guide](#tableau-guide-map-and-growth-curve)
- [Power BI guide](#power-bi-guide-cumulative-total-and-mix)
- [Numbers must match](#numbers-must-match)

---

## Tableau guide: map and growth curve

### What this dashboard shows

Two sheets stacked in one dashboard. The top sheet plots all 33 stations as circles
on a map, coloured by charging level and sized by power rating. The bottom sheet is
a running total of stations by install year, drawn as an area chart, so the curve
steps 10, 29, 33 across 2024 to 2026. A charging-level filter drives both sheets.

### Prerequisites

- Tableau Public Desktop Edition, free from https://public.tableau.com (Download on
  the top nav). Install with defaults.
- A free public.tableau.com account (Sign Up on the same page). Anything published
  with Tableau Public is public, which is fine here because the source is open data.
- Tableau Public works extract-only from files. It loads the CSV into an extract on
  publish and needs no database connection.

### Connect the data

1. Open Tableau Public. Under **Connect > To a File**, click **Text file**.
2. Browse to `bi/exports/mart_ev.csv` and open it.
3. On the data source page, confirm the field types Tableau inferred:
   - `evcsid`, `owner`, `chartype`, `connectype`, `location`, `access` are strings
     (Abc icon).
   - `power_kw`, `lat`, `lon` are numbers (#), decimals.
   - `install_year` and `quantity` are whole numbers (#).
   - `lat` and `lon` pick up the Latitude and Longitude geographic roles from their
     names, with Avg as the default aggregation. If they do not, set the roles by
     hand from the field dropdown (**Geographic Role > Latitude** and **Longitude**).
   Leave the connection on **Extract**.
4. In the data pane, right-click `install_year` and choose **Convert to Dimension**.
   It is a year index, not a quantity to sum.
5. Click **Sheet 1** to start building.

### Sheet 1: Charger map

The station map, one mark per station.

1. Rename the sheet `Charger map`.
2. Drag `lon` to **Columns** and `lat` to **Rows**. Both pills should read `AVG(lon)`
   and `AVG(lat)` and the view should switch to a map.
3. Set the Marks type to **Circle**.
4. Drag `evcsid` to **Detail**. That splits the view to one mark per station, 33
   circles, instead of one averaged point.
5. Drag `chartype` to **Color**. Two colours, `L2` and `DCFC`.
6. Drag `power_kw` to **Size**. Confirm the pill reads `SUM(power_kw)`. With `evcsid`
   on Detail the sum per mark is that station's own rating, so the 175 kW DC fast
   chargers draw largest and the 6.6 and 7 kW Level 2 chargers draw smallest.

### Sheet 2: Network growth

The cumulative curve.

1. New worksheet, rename it `Network growth`.
2. Drag `install_year` to **Columns**. It is a dimension after the conversion above,
   so it lands discrete (blue) and gives one column per year.
3. Drag `evcsid` to **Rows** and set the pill to `CNT(evcsid)` (right-click the pill >
   **Measure > Count**). That is the count of stations installed in each year: 10, 19,
   4.
4. Right-click the `CNT(evcsid)` pill and choose **Quick Table Calculation > Running
   Total**. Then **Edit Table Calculation** and confirm it summarises with **Sum**,
   computed along `install_year`. The row now reads the cumulative count: 10, 29, 33.
5. Set the Marks type to **Area**.
6. Turn on **Show Mark Labels** (the label toolbar button, or the Label card) so each
   year prints its cumulative value on the chart.
7. Right-click the row axis, choose **Edit Axis**, and set the title to
   `Cumulative chargers`.
8. Drag `chartype` to the **Filters** shelf, tick all members, right-click the pill
   and choose **Show Filter**, then right-click again and set **Apply to Worksheets >
   All Using This Data Source**. One card then drives both sheets. With every member
   ticked the totals are unchanged, which is the state the committed workbook is in.

Every field this workbook uses comes straight from the mart. The running total is the
built-in table calculation from step 4, applied to the `CNT(evcsid)` pill.

### Dashboard

1. Click **New Dashboard** and name it `Halifax EV Charging Network Growth`.
2. Set Size to **Fixed size**, 1200 by 800.
3. Show the dashboard title at the top.
4. Drag `Charger map` in, then drag `Network growth` below it, so the two sheets split
   the vertical space.
5. Keep the `Chartype` colour legend and the `Power Kw` size legend in a fixed 160
   pixel column down the right side. Remove any duplicate legend or filter cards the
   drop created.

### Publish and file the artifacts

Tableau Public Desktop has no local save to disk. **File > Save** and **File > Save
As** both redirect to **Save to Tableau Public As...**, which uploads to the Tableau
Public cloud, so getting the committable `.twb` runs through the cloud and a `.twbx`
unzip.

1. **File > Save to Tableau Public As...**, sign in, and name it
   `Halifax EV Charging Network Growth`. Publishing uploads the extract and opens the
   viz in a browser. That is the live link at the top of this file.
2. On the viz page, click **Download Workbook**. It always downloads as a `.twbx`
   (packaged), never a bare `.twb`.
3. A `.twbx` is a zip. Copy it, rename the copy to `.zip`, unzip it, and take the
   `.twb` from the archive root. Commit that file as
   `bi/tableau/ev_charging_network_growth.twb`. Never commit the `.twbx`: the packaged
   extract duplicates the data, bloats the repo, and does not diff.
4. The unzipped `.twb` points its text connection at the packaged copy of the CSV. The
   committed workbook is repointed at `../exports/mart_ev.csv`, relative to
   `bi/tableau/`, so it reopens against the repo mart. Repoint it the same way before
   committing.
5. Screenshots go in `bi/tableau/screenshots/`. The committed ones are
   `01-charger-map.png`, `02-network-growth.png`, and `03-dashboard.png`, one per sheet
   and one of the whole dashboard.

---

## Power BI guide: cumulative total and mix

### What this report shows

One page, 1280 by 720, holding five items: a title text box, a card for the network
size, a line chart of the cumulative station count by install year, a bar chart of
stations by charging level with a rank in the tooltip, and a matrix of stations by
connector type with a background colour scale.

### Import and type the data

1. **Home > Get Data > Text/CSV**, pick `bi/exports/mart_ev.csv`, then
   **Transform Data** to open Power Query.
2. Set the column types:
   - `evcsid`, `owner`, `chartype`, `connectype`, `location`, `access` = Text
   - `power_kw`, `lat`, `lon` = Decimal Number
   - `install_year`, `quantity` = Whole Number
3. **Close & Apply**. The table lands as `mart_ev`, 33 rows.
4. Select `install_year` in the Data pane and set **Column tools > Summarization** to
   **Don't summarize**. It is a year index, so a default sum on it would be
   meaningless.

The model is the single `mart_ev` table. `install_year` holds a whole number rather
than a date, so the cumulative measure below indexes on that column directly.

### Measures (enter each verbatim)

    Chargers = COUNTROWS ( mart_ev )

    Cumulative Chargers =
    VAR y = MAX ( mart_ev[install_year] )
    RETURN
        CALCULATE (
            [Chargers],
            REMOVEFILTERS ( mart_ev[install_year] ),
            mart_ev[install_year] <= y
        )

    Chartype Rank = RANKX ( ALLSELECTED ( mart_ev[chartype] ), [Chargers], , DESC, Skip )

Set the format string of all three to `0` (Measure tools > Format > Whole number, 0
decimals). `Cumulative Chargers` clears the year filter and re-applies a "less than or
equal to the current year" filter, so on a chart with `install_year` on the axis each
point reads the running total rather than that year's own count.

### Visuals

- **Text box** across the top of the page, holding `Halifax EV Charging Network
  Growth` in bold Segoe UI Semibold at 24pt.
- **Card**, value `[Chargers]`. With no filters it reads 33.
- **Line chart**, axis `install_year`, values `[Cumulative Chargers]`. Three points:
  2024 at 10, 2025 at 29, 2026 at 33.
- **Clustered bar chart**, axis `chartype`, values `[Chargers]`, and `[Chartype Rank]`
  in the **Tooltips** well. Sorted by `[Chargers]` descending, so `L2` at 26 leads
  `DCFC` at 7.
- **Matrix**, rows `connectype`, values `[Chargers]`, with **Conditional formatting >
  Background color** on `[Chargers]` set to a two-colour linear gradient (minimum to
  maximum). Three rows: `J1772` 26, `CCSCHADEMO` 6, `CCSNACS` 1.

### Save and file the artifacts

1. Turn on the project save format: **File > Options and settings > Options > Preview
   features > Power BI Project (.pbip) save option**, then restart if prompted.
2. **File > Save As**, choose **Power BI project files (.pbip)**, and save into
   `bi/powerbi/` as `ev_charging_network_growth`. Commit the `.pbip` file together
   with its `.Report/` and `.SemanticModel/` text folders. Never commit a `.pbix`: the
   binary duplicates the data and does not diff.
3. Free Power BI Desktop has no public publish link, so the deliverable is the
   committed project plus an export. Use **File > Export > PDF**, or take a PNG of the
   full page, and file it at `bi/powerbi/screenshots/report.png`.

---

## Numbers must match

**HRM's public EV charging network reaches a cumulative 33 stations by 2026.** With
no filters applied, that figure reads the same three ways:

- **SQL golden**: `expected/chargers_by_year.csv`, the `cumulative_chargers` column,
  reads 10 at 2024, 29 at 2025, and 33 at 2026. `expected/mart_ev.csv` carries the
  matching 33 rows.
- **Tableau**: on the `Network growth` sheet, the running total of `CNT(evcsid)` at
  the 2026 column labels 33, and the `Charger map` sheet plots 33 circles.
- **Power BI**: the `[Chargers]` card reads 33, and `[Cumulative Chargers]` at
  `install_year` 2026 reads 33 on the line chart.

If any of those figures differs, the loaded CSV is stale: re-run `python run.py` from
the project folder, then reconnect or refresh the extract.
