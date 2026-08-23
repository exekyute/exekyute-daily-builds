# BI layer: long-term care bed supply

This folder holds the BI face of the build. The SQL pipeline is the single brain: it computes every number and exports one mart, `bi/exports/mart_ltc.csv`. Power BI reads that mart and re-derives the same figures; it never recomputes a rule. When the report is built, its headline numbers must match the golden output exactly.

## Why Power BI for this data

The whole build turns on a bed definition, and a definition has to hold everywhere it is used. `Total Beds` must filter to the two core bed types on a card, on a bar, and inside every matrix cell, which is what a DAX measure does and what a chart option cannot. The other half of the report is a zone-by-bed-type matrix, and the mart's long shape was chosen so that matrix is a plain rows-by-columns drop rather than a pivot. Cards and a matrix over one measure is what Power BI is best at. This is a single-tool build by deliberate selection: the SQL base build and the browser dashboard are complete and verified on their own, and this guide can be followed any time after the fact.

## Prerequisites

Power BI Desktop, free from the Microsoft Store. Enable File > Options > Preview features > "Power BI Project (.pbip) save option". No service account and no tenant is needed. The free deliverable is the committed .pbip plus exported PNG or PDF, because Publish to web is not available on the free tier. Commit the .pbip .Report and .SemanticModel text folders. Never commit a .pbix.

## Step 1: connect to the mart

1. Home > **Get Data** > **Text/CSV**.
2. Browse to `bi/exports/mart_ltc.csv` inside this project folder.
3. In the preview dialog choose **Transform Data** (not Load) so you can set types explicitly.
4. In Power Query, set each column type by clicking its type icon:

   | Column | Type |
   | --- | --- |
   | facility_id | Text |
   | facility_name | Text |
   | town | Text |
   | postal_code | Text |
   | zone | Text |
   | facility_type | Text |
   | sea_participating | Text |
   | longitude | Decimal Number |
   | latitude | Decimal Number |
   | facility_total_beds | Whole Number |
   | bed_type | Text |
   | is_core_bed | Whole Number |
   | beds | Whole Number |

   Leave `postal_code` as Text. Power Query will not guess it wrong here, but a later re-import on different data can, and a postal code typed as anything else stops being a postal code.
5. **Close & Apply**. Connection mode is Import, the default for CSV; nothing here needs DirectQuery.

The table lands as `mart_ltc`, 580 rows: one row per facility per bed type, so a facility appears four times. Every measure below is written for that grain.

## The mart has no date column

There is nothing to build a date table from, so **do not use time-intelligence functions anywhere in this report**: no `SAMEPERIODLASTYEAR`, `DATEADD`, `TOTALYTD`, `DATESBETWEEN`, or `CALENDAR`. They need a marked date table and will either error or return silent nonsense. Nothing in this report needs one; it is a snapshot of standing capacity, not a time series.

## Step 2: base measures

Modeling > New measure, once per measure. These four carry the definition; everything else builds on them.

```DAX
Total Beds =
CALCULATE (
    SUM ( mart_ltc[beds] ),
    mart_ltc[is_core_bed] = 1
)
```

```DAX
Facility Count = DISTINCTCOUNT ( mart_ltc[facility_id] )
```

```DAX
Respite Beds =
CALCULATE (
    SUM ( mart_ltc[beds] ),
    mart_ltc[is_core_bed] = 0
)
```

```DAX
Beds by Type = SUM ( mart_ltc[beds] )
```

`Total Beds` is the definition in code: nursing home beds plus residential care beds, the two rows flagged `is_core_bed = 1`, with respite beds left out. `Beds by Type` sums whatever bed types are in filter context and exists only for the matrix in Step 4, where the `bed_type` column does the splitting itself. Never use `Beds by Type` on a card.

Do not shorten that fourth name to `Beds`. Measures and columns share one namespace inside a table, `mart_ltc` already has a column called `beds`, and Power BI refuses the measure with "The name 'Beds' is already used in table 'mart_ltc'." The measure never saves, and Step 4 then has nothing to drop into Values.

Format all four as Whole Number with a thousands separator (Measure tools > Format > Whole number, then turn on the comma).

## Step 3: the KPI cards

Insert three **Card** visuals across the top of the page:

1. `Total Beds`, titled **Total beds**. It must read **8,764**.
2. `Facility Count`, titled **Facilities**. It must read **145**.
3. `Respite Beds`, titled **Respite beds (excluded)**. It must read **43**.

Give the first card a subtitle in the Format pane (General > Title > Subtitle, or a text box under it) reading: `nursing home beds + residential care beds; respite excluded`. The definition should be visible on the page, not just in this file.

Two more measures for a second card row, both of which the SQL golden also reports:

```DAX
Average Beds per Facility =
DIVIDE ( [Total Beds], [Facility Count] )
```

```DAX
Median Beds per Facility =
MEDIANX (
    VALUES ( mart_ltc[facility_id] ),
    CALCULATE ( [Total Beds] )
)
```

Format both as Decimal Number with 2 decimal places. `MEDIANX` iterates one row per facility and takes the continuous median, averaging the two middle facilities when the count is even, which is the same thing DuckDB's `MEDIAN` does. With no slicer applied the cards read **60.44** and **47.00**.

## Step 4: the zone-by-bed-type matrix

1. Insert a **Matrix**.
2. Rows: `zone`. Columns: `bed_type`. Values: `Beds by Type`.
3. Format pane > **Subtotals** > **Column subtotals**: turn it **Off**.

That last step matters. With column subtotals on, the matrix adds a Total column on the right that sums across all four bed types, so Central would read 3,145 rather than its 3,135 total beds. That number mixes respite into the total and contradicts the definition the rest of the report uses. Turn the column off and let the `Total Beds` bar in Step 5 carry the zone totals.

Leave **Row subtotals** on. The bottom Total row sums each bed type down the zones, and those four figures are real: **8,026** nursing, **738** residential, **41** nursing_respite, **2** residential_respite.

The finished grid, all sixteen cells:

| zone | nursing | nursing_respite | residential | residential_respite |
| --- | --- | --- | --- | --- |
| Central | 2,999 | 10 | 136 | 0 |
| Eastern | 1,759 | 9 | 147 | 0 |
| Northern | 1,333 | 9 | 216 | 0 |
| Western | 1,935 | 13 | 239 | 2 |

The three zeroes are real zeroes, not gaps. The mart carries a row for every facility and every bed type, so an empty cell would mean an import problem.

## Step 5: zones by total beds

1. Insert a **Clustered bar chart**.
2. Y-axis: `zone`. X-axis: `Total Beds`.
3. Sort: visual header **More options (...)** > Sort axis > `Total Beds` > Sort descending.
4. Turn on data labels (Format pane > Data labels).

The bars must read Central **3,135**, Western **2,174**, Eastern **1,906**, Northern **1,549**, and they must add to 8,764. This is the visual that carries zone totals under the stated definition, which is why the matrix gives its total column up.

Add a share measure if you want the percentages on the page:

```DAX
Share of Total Beds % =
DIVIDE (
    [Total Beds],
    CALCULATE ( [Total Beds], REMOVEFILTERS ( mart_ltc[zone] ) )
)
```

Format as Percentage with 2 decimals. Dropped into the bar chart's tooltip it reads Central **35.77%**, Western **24.81%**, Eastern **21.75%**, Northern **17.67%**.

## Step 6: the facility detail table

1. Insert a **Table** visual with columns `facility_name`, `town`, `zone`, `facility_type`, then the measures `Total Beds` and `Respite Beds`.
2. Use the measures, not the `facility_total_beds` column. That column repeats down each facility's four rows, and the table groups those four into one line, so the repetition is invisible and the damage is silent: dropped in as a field it defaults to **Sum** and counts each facility four times, so 144-bed Adeline Hall reads 576 and the column total reads 35,056 instead of 8,764. If you want it as a field rather than a measure, set its aggregation to **Maximum**, never Sum. The per-facility numbers are then right, but the visual's Total row reads 385, the largest single facility, not a sum.
3. Sort by `Total Beds` descending.
4. Add a **Slicer** with `zone`, dropdown style, and a second slicer with `facility_type` if the page has room.

With the slicers cleared the table shows 145 rows, its `Total Beds` column totals 8,764, and the top row is **Northwood Incorporated, Halifax, Central, 385 beds**. Select Central in the zone slicer and the table drops to 37 rows totalling 3,135, and every card and the bar chart follow, because all of them are measures over the same filter context.

## Step 7: layout and formatting

- Page title: "Nova Scotia Long-Term Care Bed Supply".
- Suggested layout: the three cards across the top, the zone bar chart below them on the left, the zone-by-bed-type matrix on the right, the facility table across the bottom, slicers in a narrow strip down the left edge.
- Every bed field is a whole number with a thousands separator. Averages, medians, and percentages carry 2 decimals.
- Put the bed definition on the page as a text box, word for word: `Total beds = nursing home beds + residential care beds. Respite beds are reported separately and excluded.` A reader who does not have this file should still be able to tell what the 8,764 counts.

## Numbers match

With every slicer cleared, the finished report must read identically to the golden output in `expected/ltc_bed_supply.csv`:

- Total beds card: **8,764**, under the definition total beds = nursing home beds + residential care beds, with the 41 nursing respite and 2 residential care respite beds excluded.
- Facilities card: **145**.
- Respite beds card: **43**.
- Average and median beds per facility: **60.44** and **47.00**.
- Zone bars: Central **3,135**, Western **2,174**, Eastern **1,906**, Northern **1,549**.
- Matrix bottom Total row: nursing **8,026**, residential **738**, nursing_respite **41**, residential_respite **2**.
- Facility table top row: **Northwood Incorporated**, 385 beds.

If any figure differs, the mart import or a measure is wrong; the SQL golden is the arbiter.

## Step 8: save and export

1. **File > Save as**, navigate into `bi/powerbi/`, and save as `ltc_bed_supply` with save type **Power BI project files (*.pbip)**. Desktop writes `ltc_bed_supply.pbip` plus `ltc_bed_supply.Report/` and `ltc_bed_supply.SemanticModel/` folders; all of that is text and gets committed. Use the short snake_case name; renaming a `.pbip` afterwards means patching five references by hand.
2. **Scrub the absolute path before any push.** Power BI bakes the full local CSV path, Windows username included, into `ltc_bed_supply.SemanticModel/definition/tables/mart_ltc.tmdl` on the `Source = Csv.Document(File.Contents("C:\Users\...\mart_ltc.csv"))` line. Open that file and replace the path with the relative `..\exports\mart_ltc.csv`, then grep the whole `.pbip` tree for your username, not just that one file, because the path can appear in more than one place. Power BI may prompt to relocate the CSV the next time it opens the project; point it back at `bi/exports/mart_ltc.csv`.
3. Export visuals: **File > Export > Export to PDF** into `bi/powerbi/screenshots/`, or take a PNG of the report page as `bi/powerbi/screenshots/ltc_bed_supply.png`.
4. Do not commit any `.pbix`, and do not commit the machine-local `.pbi/` folders that Desktop writes next to the project (`localSettings.json`, `editorSettings.json`, and a binary `cache.abf`). The repo's `.gitignore` excludes both. What does get committed is the definition text: `.Report/` and `.SemanticModel/` under `definition/`, plus `.platform`, `definition.pbir`, `definition.pbism`, `StaticResources`, and `diagramLayout.json`. Power BI writes CRLF and git normalizes it to LF, which reopens fine.
