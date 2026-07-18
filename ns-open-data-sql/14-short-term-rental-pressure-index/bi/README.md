# Tableau build guide: short-term-rental pressure index

This guide builds one Tableau Public dashboard from the mart this pipeline
exports. Follow it top to bottom; every field name below matches
`bi/exports/mart_str_pressure.csv` exactly. The base SQL build is complete
without this dashboard, so this guide can be followed any time after
`python run.py` prints PASS.

## Why Tableau Public for this data

The mart is one row per region with a count, a share of the provincial total,
and a commercial share, which is exactly the shape Tableau handles well: a
map (or ranked bars) for regional density, and a FIXED level-of-detail
expression to recompute each region's share of the province inside the viz.
That FIXED LOD calculation is the reason to pick Tableau; the same numbers
already exist in the mart, so the calculated field can be checked against the
pipeline's own output. One tool is enough here: the dataset is a single small
table and needs no modelling layer.

## Prerequisites

- **Tableau Public Desktop Edition** (free): download from
  https://public.tableau.com/en-us/s/download and install the Windows build.
- **A free Tableau Public account** at https://public.tableau.com. Everything
  published to Tableau Public is public; this mart contains only aggregated
  counts from an open government dataset, so that is fine.
- Tableau Public connects to files as an **extract only**. That is the normal
  mode here; the CSV is small and static.
- Run `python run.py` first so `bi/exports/mart_str_pressure.csv` exists and
  matches the golden output.

## Connect to the mart

1. Open Tableau Public. On the start page, under **Connect > To a File**,
   click **Text file**.
2. Browse to this project folder and open `bi/exports/mart_str_pressure.csv`.
3. In the data grid, set the field types (click the type icon above each
   column header):
   - `region`: **String**. Then right-click the field, choose
     **Geographic Role > County**. If County is not offered directly, use
     **Geographic Role > Create from > County**.
   - `total_registrations`, `commercial_count`, `whole_home_count`,
     `traditional_count`: **Number (whole)**.
   - `commercial_share_pct`, `pct_of_province`: **Number (decimal)**.
   - `rank_by_count`, `rank_by_commercial_share`: **Number (whole)**.
   - `dominant_type`: **String**.
4. Tableau treats the numeric columns as measures and `region` as a
   dimension. Drag `rank_by_count` and `rank_by_commercial_share` from
   Measures up into the dimension area (or right-click each and
   **Convert to Dimension**): they are labels for sorting, not quantities to
   sum.
5. Click **Sheet 1** to start building.

## Sheet 1: map of registrations by region

1. Rename the sheet **Registrations by region**.
2. Double-click `region`. Tableau places it on Detail and draws a map.
3. Tell Tableau which country to geocode against: click the **Map** menu >
   **Edit Locations**, set **Country/Region** to a fixed value of
   **Canada**, and set **State/Province** to a fixed value of
   **Nova Scotia**. The mart's region names already match Nova Scotia's
   county names (the pipeline strips the ` CD` suffix), which is what the
   County role matches on.
4. Drag `total_registrations` to **Color** on the Marks card, and change the
   mark type dropdown from Automatic to **Map** (filled) if it is not
   already. Darker fill = more registered rentals.
5. Drag `total_registrations` to **Label** as well, so each region shows its
   count.
6. In **Edit Locations**, fix any region flagged **Unrecognized** by picking
   the matching county from the dropdown.

**Fallback if the regions do not geocode.** Nova Scotia county polygons
sometimes fail to match on Tableau's County role. If Edit Locations cannot
resolve most regions, build this sheet as a ranked bar plus treemap instead,
in the same workbook:

- Ranked bar: drag `region` to Rows and `total_registrations` to Columns,
  then sort descending by clicking the sort icon on the axis.
- Treemap: on a second sheet, drag `region` to Label and
  `total_registrations` to both **Size** and **Color**, and pick **Treemap**
  from Show Me.

Everything else in this guide works unchanged with the fallback layout.

## Sheet 2: FIXED LOD share of the province

1. New sheet, named **Share of province**.
2. Create a calculated field (**Analysis > Create Calculated Field**), name
   it `Share of Provincial Registrations`, and enter exactly:

       SUM([total_registrations]) / SUM({ FIXED : SUM([total_registrations]) })

   The `{ FIXED : ... }` block computes the provincial total once, ignoring
   whatever dimensions are on the sheet, so each region's bar divides by the
   same denominator even when the view is filtered.
3. Drag `region` to Rows and the new `Share of Provincial Registrations`
   field to Columns.
4. Format the axis as a percentage: right-click the field pill >
   **Format** > Numbers > **Percentage**, 1 decimal place.
5. Sort regions descending by the share.
6. Cross-check: the mart already carries this number in `pct_of_province`.
   Drag `pct_of_province` to Tooltip (aggregated as AVG, since it is one
   value per region row) and confirm the LOD value and the pipeline value
   agree for every region.

## Sheet 3: commercial share bar

1. New sheet, named **Commercial share by region**.
2. Drag `region` to Rows.
3. Drag `commercial_share_pct` to Columns. Because the mart has one row per
   region, set the aggregation to **AVG** (right-click the pill >
   Measure > Average) so the number reads as the share itself, not a sum.
4. Sort descending (toolbar sort icon), so the most commercial region sits on
   top.
5. Drag `dominant_type` to **Color**, so the bars also show which STR
   category leads each region, and drag `commercial_count` and
   `whole_home_count` to Tooltip for the underlying counts.

## Dashboard

1. Click **New Dashboard**. Name it
   **Short-term-rental pressure index, Nova Scotia**.
2. Set size to **Automatic** (dashboard pane, Size dropdown).
3. Drag in **Registrations by region** (the map, or the fallback bar plus
   treemap), then **Share of province**, then
   **Commercial share by region**.
4. Add one region filter that drives everything: on the commercial-share
   sheet inside the dashboard, click its funnel icon
   (**Use as Filter**), then on each of the other sheets choose the filter's
   dropdown > **Apply to Worksheets > All Using This Data Source**.
   Clicking a region now highlights and filters the whole dashboard.

## The numbers must match the pipeline

The golden output this dashboard mirrors says: **Halifax** has the most
registered short-term rentals, **710** of the province's 2,556, which is
**27.8 percent** of the province, with a commercial share of
**31.7 percent** (the lowest of the 18 regions). The top of the
commercial-share sheet must be **Colchester at 66.7 percent**. The finished
dashboard must read identically: the map's largest value, the top bar of the
LOD sheet, and the commercial-share bars all have to show these same
numbers. If they differ, the connection is pointing at a stale CSV; re-run
`python run.py` and refresh the extract (**Data > mart_str_pressure >
Refresh**).

## Publish

1. **File > Save to Tableau Public As...**, sign in, and name the workbook
   `ns-str-pressure-index`.
2. The browser opens the published viz. Copy the live link; it goes into the
   project README later.
3. Download the workbook as XML: Tableau Public has no plain local save, so
   use the published page's **Download > Tableau Workbook (.twb)** option and
   place the file in `bi/tableau/`.
4. Commit the `.twb` together with `bi/exports/mart_str_pressure.csv` (the
   workbook is XML and diffs cleanly; the data travels next to it). Never
   commit a `.twbx` bundle.
5. Take screenshots of each sheet and the dashboard into
   `bi/tableau/screenshots/`.
