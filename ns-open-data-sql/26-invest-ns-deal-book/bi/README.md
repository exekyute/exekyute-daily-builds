# Tableau build guide: Invest NS deal book

This folder holds the Tableau Public side of the project. The SQL pipeline is the single brain: it computes every number and exports one mart, `bi/exports/mart_deal_book.csv`. Tableau reads that mart and re-derives the same figures; it never recomputes a cleaning rule. When the viz is built, its headline numbers must match the golden output to the cent.

## Why Tableau for this data

This mart carries real longitude and latitude on almost every row, which makes the natural first view a point map of individual deals rather than a shaded region chart, and Tableau plots a lat and long pair as a map without any geocoding step. The second thing the data needs is a share-of-total that survives a year filter, which is a FIXED level-of-detail expression, written once and reused across sheets. Tableau handles both the map and the LOD better than a hand-built page does, which is why this project gets a Tableau face rather than a second browser view. It is a single-tool build by deliberate selection: the SQL base build and the browser dashboard are complete and verified without it. The mart is frozen against a committed snapshot, so this guide can be followed any time after the fact and will land on the same numbers.

## Prerequisites

Tableau Public Desktop Edition, free for Windows, plus a free public.tableau.com account. Everything published is public, there are no private workbooks, and the data connection is extract-only from the CSV. Publish to public.tableau.com and keep the live link for the README. Commit the .twb XML into bi/tableau/ alongside the CSV. Never commit a .twbx.

## Connect the data

1. Open Tableau Public. Under **Connect > To a File**, click **Text file**.
2. Browse to this project folder and open `bi/exports/mart_deal_book.csv`.
3. On the data source page, check the types Tableau inferred:
   - `nsbi_financial_contribution` should be a number (decimal). This is the money column.
   - `fiscal_year` string, `fiscal_year_start` whole number.
   - `object_id`, `county_is_geographic`, `has_contribution`, `is_mappable`, `in_ns_bounds` whole numbers.
   - `latitude` and `longitude` will arrive as plain numbers. The next step fixes that.
4. Give the coordinates their geographic roles. Click the type icon above `latitude`, choose **Geographic Role > Latitude**. Do the same on `longitude` with **Geographic Role > Longitude**. This dataset ships real coordinates, so there is no geocoding step and no unknown-locations bucket to clean up.
5. As a secondary option, give `nsbi_county` the county role: click its type icon, then **Geographic Role > County**. Set the workbook location first if Tableau asks: **Map > Edit Locations > Country/Region > Canada**. This is only needed for a filled county map; every sheet below works without it.

   **Fallback if the county does not geocode.** Tableau's Canadian county coverage varies by version. If a large share of counties comes back unknown, build the county view as a ranked bar instead: `nsbi_county` on Rows, `SUM(nsbi_financial_contribution)` on Columns, sorted descending. Every later step works the same with the bar version.
6. Click **Sheet 1** to start building.

## Sheet 1: deals on the map

1. Rename the sheet `Deal Map`.
2. Drag `longitude` to **Columns** and `latitude` to **Rows**. Both pills must read AVG or similar; right-click each and set **Dimension** so every deal draws as its own point instead of collapsing to one average.
3. Drag `object_id` to **Detail** on the Marks card. That gives one mark per deal.
4. Set the mark type to **Circle**.
5. Drag `nsbi_financial_contribution` to **Size** and `nsbi_sector` to **Color**.
6. Drag `account_name`, `nsbi_county`, and `fiscal_year` to **Tooltip**.
7. Filter out the coordinates that are not in the province: drag `in_ns_bounds` to the Filters shelf and keep **1**. Seven deals worth $2,465,355.12 sit outside Nova Scotia (Toronto, Calgary, Dublin, and three at latitude 0, longitude 0), and one more deal has no coordinates at all. Say so on the sheet: add a caption reading "8 of 4,553 deals are not plotted: 7 outside Nova Scotia, 1 with no coordinates. All 4,553 are in the dollar totals."
8. With 39 sector labels, the colour legend will be long. Sort it by dollars and keep the top handful distinct: click the legend, **Edit Colors**, and assign a strong colour to the four leading sectors, leaving the rest grey.

## Sheet 2: each county's share of total contribution (FIXED LOD)

1. New worksheet, rename it `County Share`.
2. **Analysis > Create Calculated Field**, name it `County Share of Contribution`, and enter exactly:

       SUM([Nsbi Financial Contribution]) / SUM({ FIXED : SUM([Nsbi Financial Contribution]) })

   The `{ FIXED : ... }` part computes the provincial total once, ignoring every dimension on the view, so each county's bar divides by the same denominator even when the year filter in Sheet 4 is active. That is the point of the expression: with a single year selected, the bars shrink against the all-years total rather than re-basing to the year.
3. Format it as a percentage: right-click the field, **Default Properties > Number Format > Percentage**, 2 decimal places.
4. Put `nsbi_county` on Rows and `County Share of Contribution` on Columns. Sort descending: use the sort icon on the axis, or the field's **Sort > Descending by County Share of Contribution**.
5. Drag `SUM(nsbi_financial_contribution)` to Tooltip so each bar shows the dollars behind the share.
6. Leave the two non-county labels visible and marked rather than filtering them away. If you prefer them separated, drag `county_is_geographic` to Colour rather than to Filters, so they stay on the chart and stay in the total.

## Sheet 3: sector bars with a deal-type breakdown

1. New worksheet, rename it `Sector by Deal Type`.
2. `nsbi_sector` on Rows, `SUM(nsbi_financial_contribution)` on Columns.
3. Sort by dollars descending: axis sort icon, or **Sort > Descending by SUM(Nsbi Financial Contribution)**.
4. Drag `deal_type` to **Colour** on the Marks card. Each sector bar now splits into its deal types, stacked.
5. Keep it readable: Filters pane, drag `nsbi_sector` onto the visual, filter type **Top**, **By field**, Top 15 by `SUM(Nsbi Financial Contribution)`.
6. Add `deal_type` and `SUM(nsbi_financial_contribution)` to Tooltip so each segment names its own dollars.
7. A note for reading this sheet: the deal-type labels change with the fiscal year, so `PRB` and `Payroll Rebate` are two segments of the same program written two ways, as are `IRP` and `Innovation Rebate Program`. The SQL leaves them distinct on purpose (see spec.md), and this sheet shows them exactly as the golden file does.

## Sheet 4: dashboard with a fiscal-year filter

1. Click **New Dashboard**. Size: Automatic.
2. Drag `Deal Map` across the top, `Sector by Deal Type` bottom left, `County Share` bottom right.
3. Add the year filter: on any sheet, drag `fiscal_year` to the Filters shelf and select all six years. On the dashboard, click that sheet's object dropdown, **Filters > Fiscal Year**. Set the control to **Multiple Values (dropdown)** with an **(All)** option.
4. Make it apply everywhere: the filter control's dropdown, **Apply to Worksheets > All Using This Data Source**.
5. Watch the LOD behaviour when one year is selected. The map and the sector bars redraw for that year, while `County Share of Contribution` keeps dividing by the fixed all-years total, so the bars get shorter instead of re-basing to 100 percent. That contrast is what the FIXED expression is for.
6. Title the dashboard "Invest NS Deal Book, 2018-2019 to 2023-2024".

## Numbers must match the golden output

With the year filter cleared, the finished viz must read identically to `expected/deal_book.csv`, to the cent:

- Total contribution: **$289,279,591.01** across **4,553** deals, and the same number the FIXED denominator computes.
- Leading sector: **ICT (includes Digital Media)** at **$89,152,964.26**, the top bar in Sheet 3.
- Leading county: **Halifax** at **$208,658,110.23**, 72.13 percent, the top bar in Sheet 2.
- Leading deal type: **PRB** at **$82,531,894.00**.
- Year spot check: 2021-2022 = **$72,302,139.00**.
- Map: 4,545 plotted marks, with 8 deals excluded and named in the caption.

If any figure differs, the CSV loaded is stale: re-run `python run.py` from the project folder and refresh the extract (**Data > Refresh**, or reconnect the file).

## Publish and file the artifacts

1. **File > Save to Tableau Public As...**, sign in, name it `Invest NS Deal Book`. Publishing uploads the extract and opens the viz in a browser; copy the live link from the address bar.
2. Download the workbook XML: on the viz page on public.tableau.com use **Download > Tableau Workbook**, or in the desktop app **File > Export As** where offered. Save the `.twb` into `bi/tableau/` and commit it beside the CSV the guide connects to. Do not commit a `.twbx`; the packaged extract duplicates the data and bloats the repo.
3. Screenshots of the published dashboard, full view plus one with a single year selected, go into `bi/tableau/screenshots/`.
4. Paste the live link at the top of this file when done.
