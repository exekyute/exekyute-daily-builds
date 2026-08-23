# Tableau build guide: public-housing supply by county

This folder holds the BI face of the build. The SQL pipeline is the single brain: it computes every number and exports one mart, `bi/exports/mart_housing.csv`. Tableau reads that mart and re-derives the same figures; it never recomputes a normalization rule. When the workbook is built, its headline numbers must match the golden output exactly.

## Why Tableau for this data

The question here is county geography plus share-of-total, and both of those are Tableau's home ground. A filled map keyed on a county name is a drag-and-drop in Tableau and a plugin exercise almost anywhere else, and the share-of-provincial-units figure is the textbook case for a FIXED level-of-detail expression: a per-county aggregate divided by a whole-table aggregate, computed independently of whatever dimension the view happens to be sliced by. This is a single-tool build by deliberate selection rather than by default. The SQL base build is complete and verified on its own, the mart is frozen alongside a committed golden file, and the workbook can be backfilled any time after the fact against exactly the same numbers.

## Prerequisites

Tableau Public Desktop Edition, free for Windows, plus a free public.tableau.com account. Everything published is public, there are no private workbooks, and the data connection is extract-only from the CSV. Publish to public.tableau.com and keep the live link for the README. Commit the .twb XML into bi/tableau/ alongside the CSV. Never commit a .twbx.

## Step 1: connect to the mart and set types

1. Open Tableau Public Desktop. Under **Connect > To a File**, pick **Text file**.
2. Browse to `bi/exports/mart_housing.csv` inside this project folder.
3. On the data source page, confirm the text-file encoding reads as **UTF-8**. Three Inverness County rows sit in Petit Étang; if the accented character comes through as garbage, the encoding is wrong and needs setting before you go further.
4. Set the data type on each field by clicking its type icon in the data source grid:

   | Field | Type | Notes |
   | --- | --- | --- |
   | program_type | String | |
   | source_id | String | Tableau will guess Number. Force it to String, or it becomes a measure and starts summing row ids. |
   | county | String | |
   | municipality | String | |
   | community | String | |
   | property_label | String | |
   | housing_authority | String | |
   | units | Number (whole) | Must land in Measures. |
   | latitude | Number (decimal) | |
   | longitude | Number (decimal) | |

5. Assign the geographic roles. Right-click **county** > **Geographic Role** > **County**. Right-click **latitude** > **Geographic Role** > **Latitude**, and **longitude** > **Geographic Role** > **Longitude**.
6. Set the country context, or the County role has nothing to resolve against. Two ways, either is fine:
   - **Calculated field.** Analysis > Create Calculated Field, name it `Country`, formula `"Canada"`. Right-click it > Geographic Role > Country/Region. Drop it on **Detail** in any map view.
   - **Edit Locations.** Build the map first, then Map > **Edit Locations**, and set Country/Region to the fixed value **Canada**.
7. Go to a worksheet. Tableau Public builds an extract automatically; that is the expected behaviour, not a misconfiguration.

Sanity check before anything else: drag **units** to the view as SUM. It must read **11,251**. If it does not, the type on `units` or the connection is wrong.

## Step 2: the filled county map

1. New worksheet, name it `Units by county map`.
2. Double-click **county**. Tableau places Latitude (generated) and Longitude (generated) on Rows and Columns and puts county on Detail.
3. Marks card: change the mark type from Automatic to **Map**.
4. Drag **units** to **Color**. Marks card > Color > Edit Colors, sequential palette, and tick **Include totals** off. Keep the default aggregation as SUM.
5. Drag **units** to **Tooltip** as well, and add **county** so the tooltip reads county and unit count.
6. Look at the bottom-right of the view for an **unknown** or **ambiguous** indicator.

**If Nova Scotia counties do not geocode**, and this is a real possibility because Tableau resolves Canadian counties as census divisions and the name forms do not always line up, do this: click the unknown-locations indicator, open **Edit Locations**, and match the unmatched names by hand. If more than a handful are unmatched, stop matching and switch to the fallback layout below. Do not fake a map with a scatter of points and call it a choropleth.

**Fallback layout, ranked bar plus treemap.** Replace the map sheet with two sheets that answer the same question without geocoding.

- Sheet `Units by county bar`: **county** on Rows, **units** on Columns, mark type Bar. Sort descending by SUM(units) through the field's sort control on Rows. Add **units** to Label. Eighteen bars fit on one screen with no filtering.
- Sheet `Units by county treemap`: **county** on Detail, **units** on Size and on Color, mark type **Square**. Add **county** and **units** to Label. The treemap carries the share-of-total reading that the choropleth would have carried, and it does it without a map service.

Either way, the mart also carries `latitude` and `longitude` on every row, so a point map of individual properties sized by units is available as an extra layer. It is a different view of the data, not a substitute for the county one.

## Step 3: the share-of-provincial-units LOD

Create three calculated fields through Analysis > Create Calculated Field. Write them exactly as below.

`County Units`

```
{ FIXED [County] : SUM([Units]) }
```

`Provincial Units`

```
{ FIXED : SUM([Units]) }
```

`County Share of Provincial Units`

```
{ FIXED [County] : SUM([Units]) } / { FIXED : SUM([Units]) }
```

Format `County Share of Provincial Units` as Percentage with 2 decimal places: right-click the field in the Data pane > Default Properties > Number Format > Percentage, 2.

Two things to know about FIXED before you wire it into anything.

- The empty `{ FIXED : ... }` deliberately has no dimension in it. That is what makes `Provincial Units` the whole-table total, 11,251, no matter what the view is sliced by.
- **A FIXED expression is computed before dimension filters run.** Put `program_type` on Filters and set it to Seniors, and `County Share of Provincial Units` will not move, because both halves of the division still see every row. That is correct behaviour and it is usually what you want here, since the denominator is meant to be the provincial total. If you want the share to follow the filter instead, right-click the `program_type` filter and choose **Add to Context**; context filters run before FIXED. Pick one and be consistent, because the two readings answer different questions.

Drag `County Share of Provincial Units` onto **Label** on the map sheet, or onto the bar sheet if you are on the fallback. Halifax must read **33.45%**.

## Step 4: the stacked bar, Families against Seniors

1. New worksheet, name it `Units by county and program`.
2. **county** on Rows, **units** on Columns, mark type Bar.
3. **program_type** on **Color**. The bar splits into a Families segment and a Seniors segment.
4. Sort the counties by total units descending: click the sort control on the county pill on Rows, sort by Field, SUM of units, Descending.
5. Drag **units** to **Label** and set the label to show per segment, so each stack shows both program figures.

The split is the point of the sheet. Halifax reads 1,546 Families units against 2,217 Seniors units, and the seniors side is the larger one in every county. The property counts run the other way: 1,145 families records against 41 seniors buildings in Halifax, because a families record is one civic address and a seniors record is a whole building. Do not put `properties` and `units` on the same axis.

## Step 5: the dashboard

1. New dashboard, size Automatic, name it `NS Public Housing Supply by County`.
2. Drop in the map sheet (or the bar plus treemap pair if you took the fallback) and the stacked bar sheet.
3. Add the program-type filter: on any sheet, drag **program_type** to Filters, show all values, then on the dashboard use the sheet's **More options > Filters > program_type** to surface it, and set **Apply to Worksheets > All Using This Data Source** so one control drives the whole dashboard. A single-select dropdown with a `(All)` option reads best with only two values.
4. Add a text title: `Nova Scotia public housing, 11,251 units in 3,289 property records`.
5. Remember what Step 3 said about FIXED and filters. With the filter on Seniors, the stacked bar and the map colour both move; the LOD share does not, unless you promoted the filter to context. Whichever you choose, say so in the dashboard caption so a reader is not left guessing why a percentage sits still.
6. Screenshots go into `bi/tableau/screenshots/`. Capture the dashboard with the filter cleared, and one with the filter set to a single program.

## Step 6: save and publish

1. **File > Save to Tableau Public As**, sign in with the free account, and name the workbook `NS Public Housing Supply by County`. Publishing is what saves the workbook on Tableau Public.
2. Keep the live link and put it in the project README.
3. **File > Export As Version** or **File > Save As** with type **Tableau Workbook (.twb)** into `bi/tableau/`. The .twb is XML and gets committed. A .twbx bundles the extract and never gets committed.

## Numbers-match check

With the program-type filter cleared, the finished workbook must read identically to the golden output:

- Top county: **Halifax, 3,763 units**, 33.45 percent of the province
- Provincial total: **11,251 units** across 3,289 property records
- Second county: Cape Breton, 2,670 units
- Halifax split: 1,546 Families units and 2,217 Seniors units
- Program totals: Seniors 7,772 units, Families 3,479 units

If any figure differs, the mart import or a calculated field is wrong. The SQL golden is the arbiter.
