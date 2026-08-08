# BI build guides: permit approval wait times

Both dashboards read one frozen file, `bi/exports/mart_processing.csv`, written by
the SQL export step. One row is one permit at one issuance stage under one
jurisdictional breakdown, 149,705 rows across 57,076 permits, so a permit
contributes several rows and `total_duration` is a per-permit value rather than a
pre-aggregated total. Neither tool recomputes any of the analysis: both aggregate
the mart exactly as written, so a figure read off one dashboard equals the same
figure on the other and in the SQL golden. Column meanings and the duration unit
are in `bi/exports/data_dictionary.md`.

Tableau live link: https://public.tableau.com/views/HalifaxPermitApprovalWaitTimes/Permitapprovalwaittimes

- [Tableau guide](#tableau-guide-box-plot-and-totals)
- [Power BI guide](#power-bi-guide-decomposition-and-matrix)
- [Numbers must match](#numbers-must-match)

---

## Tableau guide: box plot and totals

### What this dashboard shows

Two reads of the same column, stacked. The top sheet is a sorted bar of total
processing time by issuance stage, labelled with the totals. The bottom sheet is a
box plot of per-permit duration by stage, one circle per permit, so the median and
the quartile spread of each stage are visible next to the long tail. The committed
workbook holds no calculated fields: every pill on both sheets is a raw mart
column, aggregated with `SUM`.

### Prerequisites

- Tableau Public Desktop, free from https://public.tableau.com (Download on the top
  nav). Install with defaults.
- A free public.tableau.com account (Sign Up on the same page). Anything published
  from Tableau Public is public, which is fine here because the source is open data.
- Tableau Public works extract-only from files. It loads the CSV into an extract on
  publish and needs no database connection.

### Connect the data

1. Open Tableau Public. Under **Connect > To a File**, click **Text file**.
2. Browse to this repo's `bi/exports/mart_processing.csv` and open it.
3. Check the types Tableau inferred on the data source page:
   - `permit_number`, `issuance_stage`, `jurisdictional_breakdown` are strings (Abc).
   - `total_occurrence` is a whole number (#).
   - `total_duration` is a number (#), decimal.
   Leave the connection on **Extract**.
4. On `Total Duration`, set the default number format to **Number (Custom)** with 2
   decimal places and a thousands separator. The committed workbook carries
   `n#,##0.00;-#,##0.00` on that field, which is what makes the bar labels read
   `17,047,940.35` rather than a rounded or abbreviated value.
5. Click **Sheet 1** to start building.

### Sheet 1: Duration by stage

The per-permit distribution.

1. Rename the sheet `Duration by stage`.
2. Drag `Issuance Stage` to **Columns**. It stays discrete (blue).
3. Drag `Total Duration` to **Rows**. Confirm the pill reads `SUM(Total Duration)`.
4. Drag `Permit Number` to **Detail** on the Marks card, and set the mark type to
   **Circle**. Each circle is now one permit's total time inside that stage, summed
   across its Customer and Staff rows.
5. Open the **Analytics** pane and drag **Box Plot** onto the view. Take the default
   whiskers (**Data within 1.5 times the IQR**), scope **Per Cell**. The box draws the
   median and the quartiles behind the circles.
6. Leave the stage order alone. With no sort on the pill the categories read
   alphabetically: Other Timeline, Post Issuance, Pre Issuance.

### Sheet 2: Where time goes

The stage totals.

1. New worksheet, rename it `Where time goes`.
2. Drag `Issuance Stage` to **Columns** and `Total Duration` to **Rows**. Confirm
   `SUM(Total Duration)`. Leave the mark type on **Automatic**, which draws bars.
3. Drag `Total Duration` to **Label** as well, so each bar prints its own total. On
   the Label card, leave **Allow labels to overlap other marks** off, so labels that
   would collide are culled.
4. Sort the stage pill descending by `SUM(Total Duration)` (click the pill dropdown >
   **Sort** > Field, Descending, `Total Duration`, Sum). The bars then read Post
   Issuance, Pre Issuance, Other Timeline, left to right.

### Dashboard

1. Click **New Dashboard** and name it `Permit approval wait times`.
2. Set Size to **Fixed size**, 1000 by 800.
3. Drop a **Vertical** layout container onto the canvas. Put `Where time goes` in the
   top half and `Duration by stage` in the bottom half, with the dashboard title
   showing above them.
4. Add nothing else. The committed dashboard carries no filter cards and no legends,
   only the title and the two sheets.
5. Tableau generates a Phone layout automatically, which the committed workbook
   keeps. Leave it as generated.

### Publish and file the artifacts

Tableau Public Desktop has no local save to disk. **File > Save** and **File > Save
As** both redirect to **Save to Tableau Public As...**, which uploads to the Tableau
Public cloud, so getting a committable `.twb` runs through the cloud and a `.twbx`
unzip.

1. **File > Save to Tableau Public As...**, sign in, and name it
   `Halifax Permit Approval Wait Times`. Publishing uploads the extract and opens the
   viz in a browser. That is the live link at the top of this file.
2. On the viz page, click **Download Workbook**. It always downloads as a `.twbx`
   (packaged), never a bare `.twb`.
3. A `.twbx` is a zip. Copy it, rename the copy to `.zip`, unzip it, and take the
   `.twb` from the archive root. Commit that file as
   `bi/tableau/permit_approval_wait_times.twb`. Never commit the `.twbx`: the packaged
   extract duplicates the data, bloats the repo, and does not diff.
4. The unzipped `.twb` points its text connection at the packaged copy of the CSV. The
   committed workbook is repointed at `../exports/mart_processing.csv`, relative to
   `bi/tableau/`, so it reopens against the repo mart. Repoint it the same way before
   committing.
5. Put screenshots in `bi/tableau/screenshots/`. The committed one is
   `dashboard-full.png`.

---

## Power BI guide: decomposition and matrix

### What this report shows

One page, 1280 by 720. Two cards read the unfiltered totals, a decomposition tree
breaks total processing time down by issuance stage and then by jurisdictional
breakdown, and a conditional-format matrix reads the average duration per permit
across those same two dimensions. A slicer on `issuance_stage` filters the page.

### Import and type the data

1. **Get Data > Text/CSV**, choose this repo's `bi/exports/mart_processing.csv`, then
   **Transform Data** to open Power Query.
2. Set the column types:
   - `permit_number` = Text
   - `issuance_stage` = Text
   - `jurisdictional_breakdown` = Text
   - `total_occurrence` = Whole Number
   - `total_duration` = Decimal Number
3. **Close & Apply**. The table lands as `mart_processing`.

The mart carries no date column, so the committed model is a single table with no
date table and no relationships.

### Measures (enter each verbatim)

    Total Duration = SUM ( mart_processing[total_duration] )

    Permits = DISTINCTCOUNT ( mart_processing[permit_number] )

    Avg Duration per Permit = DIVIDE ( [Total Duration], [Permits] )

    Occurrences = SUM ( mart_processing[total_occurrence] )

    Stage Share of Duration = DIVIDE ( [Total Duration], CALCULATE ( [Total Duration], ALL ( mart_processing ) ) )

Format strings in the committed model: `Permits` and `Occurrences` are `0`,
`Avg Duration per Permit` is `0.00`, and `Total Duration` and
`Stage Share of Duration` are left as general numbers. `Permits` is a distinct count,
so any total row recomputes rather than summing its cells: a permit that appears
under both Customer and Staff inside one stage counts once in that stage's
denominator. `Occurrences` and `Stage Share of Duration` are in the model but are not
placed on a visual.

### Visuals

- **Text box** across the top reading `Halifax permit approval wait times`, Segoe UI
  Semibold, 20pt.
- **Slicer** on `mart_processing[issuance_stage]`. Open the slicer's header dropdown
  (or **Format > Slicer settings > Options > Style**) and choose **List**, which
  renders the vertical checkbox list of Other Timeline, Post Issuance, Pre Issuance.
- **Card** on `[Total Duration]`, display units None and 2 decimal places. Unfiltered
  it reads 24,018,912.58.
- **Card** on `[Avg Duration per Permit]`. Unfiltered it reads 420.82.
- **Decomposition tree**: Analyze = `[Total Duration]`, Explain by =
  `issuance_stage` then `jurisdictional_breakdown`, both levels pinned, 3 bars per
  level. The committed report saves the tree expanded on the Post Issuance branch,
  which splits 17,047,940.35 into Customer 16,890,546.35 and Staff 157,394.00.
- **Matrix**: Rows = `issuance_stage`, Columns = `jurisdictional_breakdown`, Values =
  `[Avg Duration per Permit]`, with **Conditional formatting > Background color** on
  that measure, a two-colour gradient, blanks treated as zero. Unfiltered the cells
  read Post Issuance 371.45 Customer and 11.91 Staff, Pre Issuance 108.06 Customer and
  15.68 Staff, Other Timeline 563.18 Other Type, with stage totals 373.06, 71.98, and
  563.18 and a grand total of 420.82.

### Save and file the artifacts

1. Turn on the project save format: **File > Options and settings > Options > Preview
   features > Power BI Project (.pbip) save option**, then restart if prompted.
2. **File > Save As**, choose **Power BI project files (.pbip)**, and save into
   `bi/powerbi/` as `permit_approval_wait_times`. Commit the `.pbip` file together
   with its `permit_approval_wait_times.Report/` and
   `permit_approval_wait_times.SemanticModel/` text folders. Never commit a `.pbix`:
   the binary duplicates the data and does not diff.
3. Free Power BI Desktop has no public publish link, so the deliverable is the
   committed project plus an exported PNG or a **File > Export > PDF**. The committed
   image is `bi/powerbi/screenshots/report.png`.

---

## Numbers must match

**Post Issuance total processing time reads 17,047,940.35 days**, the same in all
three places by construction:

- **SQL golden**: in `expected/processing_summary.csv`, the `total_duration` column
  on the two Post Issuance rows, Customer 16,890,546.35 and Staff 157,394.003, sums
  to 17,047,940.35.
- **Tableau**: on `Where time goes`, the leftmost bar is Post Issuance and its mark
  label reads 17,047,940.35.
- **Power BI**: the Post Issuance node of the decomposition tree under
  `[Total Duration]` reads 17,047,940.35, and ticking Post Issuance in the
  `issuance_stage` slicer makes the `[Total Duration]` card read the same figure.

If any of the three differs, the loaded CSV is stale: re-run `python run.py` from the
project folder, then reconnect or refresh the extract.
