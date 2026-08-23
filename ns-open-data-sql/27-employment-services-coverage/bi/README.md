# Tableau build guide: employment-services coverage

This folder holds the Tableau Public side of the project. The SQL pipeline is the brain: it computes every number and exports one mart, `bi/exports/mart_services.csv`. Tableau reads that mart and re-derives the same figures, never a cleaning rule of its own. When the viz is built, its headline must match the golden output exactly.

## Why Tableau for this data

The mart is point geography from real coordinates, one latitude and longitude per centre, so the obvious face for it is a map. Forty-seven dots on the province say more about where employment services actually reach than any table of counts does, and a browser dashboard cannot draw a geographic basemap without pulling a mapping library and tiles across the network. Tableau plots raw coordinate pairs directly, no geocoding step and no postal-code lookup involved, which sidesteps the usual Canadian FSA-coverage problem entirely. This is a single-tool build by deliberate selection rather than a two-tool comparison: the SQL base build and the browser dashboard are complete and verified without it. The mart is frozen, so this guide is backfillable and can be followed any time after a `python run.py` PASS.

## Prerequisites

Tableau Public Desktop Edition, free for Windows, plus a free public.tableau.com account. Everything published is public, there are no private workbooks, and the data connection is extract-only from the CSV. Publish to public.tableau.com and keep the live link for the README. Commit the .twb XML into bi/tableau/ alongside the CSV. Never commit a .twbx.

## Step 1: connect to the mart, and fix the geographic roles

1. Open Tableau Public. Under **Connect > To a File**, click **Text file**.
2. Browse to this project folder and open `bi/exports/mart_services.csv`.
3. Check the types Tableau inferred on the data source page. `region`, `center_name`, `city_town`, `street_address`, `postal_code`, and `fsa` should be strings (Abc). `latitude` and `longitude` should be decimals. `has_email` through `region_centres` should be whole numbers.

**The geographic roles, and why this step matters here.** The mart deliberately exposes columns named `latitude` and `longitude`, because the source file names them backwards: its `x_coordinate` column holds latitude and its `y_coordinate` column holds longitude. The SQL corrected that once and named the outputs for what they actually contain, so in Tableau you can trust the column names in front of you. Assign the roles by those names:

- Right-click `latitude` in the data pane, **Geographic Role > Latitude**.
- Right-click `longitude` in the data pane, **Geographic Role > Longitude**.

Do not assign a role to `postal_code` or `fsa`. This build maps real coordinates and never needs Tableau's Canadian postal geocoding, which is the whole point of having the coordinates.

A quick sanity check before moving on: `latitude` should run from about 43.5 to 46.7, and `longitude` from about -66.1 to -60.0. If your latitude values are negative, the roles are on the wrong two columns.

4. Click **Sheet 1** to start building.

## Sheet 1: the centre map

1. Rename the sheet `Centre Map`.
2. Drag `longitude` to **Columns** and `latitude` to **Rows**. Both arrive as `AVG()` pills, which would collapse all 47 centres into one dot per group.
3. Drag `center_name`, `city_town`, and `street_address` onto **Detail** on the Marks card. That splits the marks back out to one per centre, which is what you want, and it survives however the pills are aggregated. The mark count in the status bar at the bottom left must read **47 marks**.
4. Set the Marks type dropdown to **Circle**.
5. Drag `region` to **Color**. Five regions, five colours.
6. Drag `postal_code`, `fsa`, and `contact_channels` onto **Tooltip** so hovering a centre shows its address, its postal area, and how many of the four contact channels it publishes.
7. Size the circles up a little (Size slider on the Marks card) so single-centre towns are readable against the basemap.

If the map draws but the marks cluster off the coast, stop and recheck the geographic roles in Step 1.

## Sheet 2: centres per region

1. New worksheet, rename it `Centres by Region`.
2. Drag `region` to **Rows**.
3. Drag `Number of Records` to **Columns**. If your version of Tableau Public does not offer that field, use the auto-generated `mart_services (Count)` measure instead, or create a calculated field named `Centres` containing exactly:

       COUNT([Region])

   Every mart row is one centre and `region` is never blank, so counting it counts centres.
4. Sort descending: click the sort icon on the `region` axis, or use the visual's **Sort** dialog with **Field > Centres > Descending**.
5. Drag `Centres` to **Label** so each bar shows its count.

**Read the tie before you trust the sort.** Cape Breton and HRM both hold 12 centres. The SQL breaks that tie alphabetically and ranks Cape Breton first; Tableau's descending sort may put either one on top, and both are correct readings of the same 12. Compare counts, not positions. If you want the two to agree exactly, set the sort to **Manual** and drag Cape Breton above HRM.

## Sheet 3: each region's share of all centres (FIXED LOD)

1. New worksheet, rename it `Region Share`.
2. **Analysis > Create Calculated Field**, name it `Region Share of Centres`, and enter exactly:

       COUNT([Region]) / MIN({ FIXED : COUNT([Region]) })

3. Format it as a percentage: right-click the field in the data pane, **Default Properties > Number Format > Percentage**, 2 decimal places.
4. Put `region` on **Rows** and `Region Share of Centres` on **Columns**. Sort descending.
5. Drag `region_share_pct` onto **Tooltip** and set it to **Minimum** rather than Sum. That column is the same share precomputed in SQL and repeated on every row of a region, so it is your cross-check: the calculated field and the tooltip must agree to two decimals on all five bars.

**Why `MIN` wraps the LOD, and why `SUM` would be wrong.** `{ FIXED : COUNT([Region]) }` has no dimension before the colon, so it computes the provincial total once, ignoring whatever is on the view, and then repeats that same value on every row. An aggregate has to collapse those repeats into one number. `MIN` picks one of the identical values, which is 47. `SUM` would add 47 up once per row in the partition, so Cape Breton's denominator would come out as 12 x 47 and every share would be wrong by a different factor. That mistake is quiet, because the bars still draw and still look ranked.

## Sheet 4: the dashboard

1. Click **New Dashboard**. Size: Automatic.
2. Drag `Centre Map` across the top, `Centres by Region` bottom left, `Region Share` bottom right.
3. Add the region filter: on the `Centre Map` sheet, drag `region` to the **Filters** shelf and select all five. Back on the dashboard, click the map object's dropdown, **Filters > Region**, and set the control to **Multiple Values (dropdown)**.
4. Make it apply everywhere: click the filter control's dropdown, **Apply to Worksheets > All Using This Data Source**.
5. Add the centre detail tooltip: on `Centre Map`, open **Worksheet > Tooltip** and write a layout that names the centre and its provider, for example:

       <center_name>
       <city_town>, <postal_code>  (<fsa>)
       <street_address>
       Contact channels published: <contact_channels> of 4

   Keep `center_name`, `city_town`, `street_address`, `postal_code`, `fsa`, and `contact_channels` on the Marks card so those references resolve.
6. Note what the FIXED expression does when a single region is selected: the map and the region bar narrow to that region, while `Region Share of Centres` keeps dividing by the provincial 47 and so still reads that region's true provincial share. That contrast is the reason the denominator is FIXED rather than computed on the view.
7. Give the dashboard a title: "Nova Scotia Works Centre Coverage".

## Numbers must match the golden output

With the region filter cleared, the finished viz must read identically to `expected/services_coverage.csv`:

- Marks on the map: **47**
- Top region bar: **Cape Breton, 12 centres**, tied on count with HRM at 12 and ranked first alphabetically
- `Region Share of Centres` for Cape Breton: **25.53%**, matching the `region_share_pct` tooltip
- Smallest region bar: **Annapolis Valley, 6 centres, 12.77%**
- The five region bars sum to 47 and their shares sum to 100.00%

If any of these differ, the extract is stale or a measure is wrong. Re-run `python run.py` from the project folder, refresh the extract (**Data > Refresh**), and check the FIXED expression first. The SQL golden is the arbiter.

## Publish and file the artifacts

1. **File > Save to Tableau Public As...**, sign in, and name it `NS Works Centre Coverage`. Publishing uploads the extract and opens the viz in a browser. Copy the live link out of the address bar and paste it at the top of this file.
2. Download the workbook: on your viz page on public.tableau.com use **Download > Tableau Workbook**. Save the `.twb` into `bi/tableau/` and commit it next to the CSV this guide connects to. Do not commit a `.twbx`: the packaged version duplicates the data into the repo.
3. Screenshot the published dashboard into `bi/tableau/screenshots/`, one full view and one with a single region selected.
