# BI build guides: property tax and assessment burden

The SQL export step freezes two marts. `bi/exports/mart_tax_group.csv` is the wide one,
5,383 rows, one row per `tax_group`, `tax_summary_group`, `rate_code`,
`rate_description`, and `bill_rate_percentage`, carrying account counts, taxable
assessment by class, the billed dollars, and the effective rate.
`bi/exports/mart_tax_class.csv` is the long one, 13 rows, one row per tax group per
assessment class that carries a taxable base, with the taxable dollars and that class
share of the municipal base. Both tools read those two files as written and recompute
none of the analysis: every dollar is already rounded to the cent by the SQL, so a
figure read in Tableau equals the same figure in Power BI and in the golden results.
Column meanings are in `bi/exports/data_dictionary.md`.

Tableau live link: https://public.tableau.com/views/HalifaxPropertyTaxandAssessmentBurden/Propertytaxandassessmentburden

- [Tableau guide](#tableau-guide-stacked-bar-and-rate-ranking)
- [Power BI guide](#power-bi-guide-ranked-bar-and-matrix)
- [Numbers must match](#numbers-must-match)

---

## Tableau guide: stacked bar and rate ranking

### What this dashboard shows

Three sheets on one fixed dashboard: a total-bill text tile, taxable assessment by tax
group coloured by assessment class and carrying a FIXED share of the whole municipal
base, and the realized effective rate for every rate code that has a taxable base,
ranked highest first. Selecting a bar in the taxable sheet filters the other two.

### Prerequisites

- Tableau Public Desktop Edition, free from https://public.tableau.com (Download on the
  top nav). Install with defaults.
- A free public.tableau.com account (Sign Up on the same page). Anything published from
  Tableau Public is public, which suits open data.
- Tableau Public works extract-only from files. Both connections in the committed
  workbook are text-file connections against the `bi/exports` folder, loaded into an
  extract at publish time. No database is involved.

### Connect the data

1. Open Tableau Public. Under **Connect > To a File**, click **Text file** and open
   `bi/exports/mart_tax_class.csv`. It becomes the `mart_tax_class` data source.
2. Check the types Tableau inferred: `tax_group` and `class` are strings (Abc),
   `taxable` is a whole number (#), `share_of_total_taxable` is a decimal number (#).
3. Add the wide mart as a second, independent data source: **Data > New Data Source >
   Text file**, and open `bi/exports/mart_tax_group.csv`. Do not use the **Add** link
   beside Connections on the data source page: that attaches the file to
   `mart_tax_class` and drops it on the relationship canvas. Tableau matches the two on
   `tax_group`, and because the class mart carries 13 rows against the rate mart's
   5,383, every class taxable figure would repeat once per rate line and `SUM(Taxable)`
   would inflate. The committed workbook keeps the two sources apart. The Data pane
   should now list two sources, `mart_tax_class` and `mart_tax_group`; click the source
   name at the top of the pane to choose which one a sheet builds from.
4. Check its types: `tax_group`, `tax_summary_group`, `rate_code`, and
   `rate_description` are strings; `account_count`, `residential_taxable`,
   `commercial_taxable`, `resource_taxable`, and `total_taxable` are whole numbers;
   `bill_rate_percentage`, `bill_amount`, `bill_value`, and `effective_rate` are
   decimal numbers. `bill_amount` carries the default number format
   `c"$"#,##0.00;("$"#,##0.00)` in the committed workbook, which renders as currency
   with two decimals and negatives in parentheses.
5. Leave both on **Extract** and click **Sheet 1**.

### Sheet 1: Taxable by class and group

The class-coloured bar of taxable assessment, on `mart_tax_class`.

1. Rename the sheet `Taxable by class and group`.
2. Drag `Tax Group` to **Columns** as a discrete dimension.
3. Drag `Taxable` to **Rows**. Confirm the pill reads `SUM(Taxable)`.
4. Drag `Class` to **Color**. Each tax group in this mart resolves to exactly one
   assessment class, so every bar carries one colour band and the legend reads as a
   class key across the groups.
5. Add the share calculation. **Analysis > Create Calculated Field**, type
   `Group Share` in the name box at the top, and enter only the expression below it,
   using the field names as the data pane shows them after Tableau's text-file name
   cleanup:

       SUM([Taxable]) / SUM({ FIXED : SUM([Taxable]) })

   Then drag `Group Share` from the data pane onto **Tooltip**. The FIXED with no
   dimension holds the denominator at the whole taxable base, so the share stays
   against the municipal total rather than against whatever the view has been filtered
   to. `1. Municipal Residential` reads 0.613324.
6. Sort the axis: use the field sort on the Columns shelf, `Tax Group` sorted
   **descending** by `SUM(Taxable)`. The committed workbook stores exactly that.

### Sheet 2: Effective rate by rate code

The ranked rate bar, on `mart_tax_group`.

1. New worksheet, rename it `Effective rate by rate code`.
2. Drag `Rate Code` to **Columns** as a discrete dimension.
3. Add the rate calculation. **Analysis > Create Calculated Field**, type
   `Effective Rate (calc)` in the name box at the top, and enter only the expression
   below it:

       SUM([Bill Amount]) / SUM([Total Taxable])

   Then drag `Effective Rate (calc)` from the data pane to **Rows**. This divides the
   summed billed dollars by the summed taxable base inside each rate code, so it is the
   realized rate rather than an average of per-line rates.
4. Drag `Effective Rate (calc)` to the **Filters** shelf and keep **non-null values**
   only. That drops the rate codes whose taxable base is zero, which would otherwise
   divide by zero.
5. Sort the axis: field sort on the Columns shelf, `Rate Code` sorted **descending** by
   `Effective Rate (calc)`. `M130`, Community Area (outside CDD), leads at 0.036923,
   then `M100` Business Park Area at 0.036123 and `M120` Downtown/Community Area at
   0.032050.

### Sheet 3: Total 2024 bill

The single-number tile, on `mart_tax_group`.

1. New worksheet, rename it `Total 2024 bill`.
2. Leave **Rows** and **Columns** empty.
3. Drag `Bill Amount` to **Text**. Confirm the pill reads `SUM(Bill Amount)`.
4. On the Marks card open **Label** and set the text to font size 16, with mark labels
   shown. One text mark renders, formatted by the field's currency format.

### Dashboard

1. Click **New Dashboard**, name it `Property tax and assessment burden`, and set Size
   to **Fixed size**, 1000 by 800.
2. Drop the sheets into a single vertical flow, top to bottom: `Total 2024 bill`,
   `Taxable by class and group`, `Effective rate by rate code`.
3. Keep the `Class` colour legend from the taxable sheet, and put it in a fixed
   vertical container on the right at 160 pixels wide.
4. Add the cross-filter: select the `Taxable by class and group` sheet and use **Use as
   Filter**, or **Dashboard > Actions > Add Action > Filter** with source sheet
   `Taxable by class and group`, target `Property tax and assessment burden`, run on
   **Select**, and clear the selection on exit. The action passes all fields, and
   `tax_group` is the field name the other two sheets share, so clicking a bar filters
   both the rate sheet and the total tile. The committed workbook shows this as
   `Filter 1 (generated)`, and the two target sheets carry the resulting
   `Action (Tax Group)` filter.

### Publish and file the artifacts

Tableau Public Desktop has no local Save to disk. **File > Save** and **File > Save
As** both redirect to **Save to Tableau Public As...**, which uploads to the Tableau
Public cloud, so getting a committable `.twb` runs through the cloud and a `.twbx`
unzip.

1. **File > Save to Tableau Public As...**, sign in, and name it
   `Halifax Property Tax and Assessment Burden`. Publishing uploads the extract and
   opens the viz in a browser. That browser URL is the live link at the top of this
   file.
2. On the viz page, click **Download Workbook**. It always downloads as a `.twbx`
   (packaged), never a bare `.twb`.
3. A `.twbx` is a zip. Copy it, rename the copy to `.zip`, unzip it, and take the
   `.twb` from the archive root. Commit that file as
   `bi/tableau/property_tax_burden.twb`. Never commit the `.twbx`: the packaged extract
   duplicates the data, bloats the repo, and does not diff.
4. Put screenshots in `bi/tableau/screenshots/`. The committed one is
   `dashboard-full.png`.

---

## Power BI guide: ranked bar and matrix

### What this report shows

One page, 1280 by 720, fit to page. A Bill Amount card and an Effective Rate card, a
bar of billed dollars by tax group ranked descending with rank and share in the
tooltip, a tax group by rate code matrix of billed dollars with a background colour
scale, and a tax group dropdown slicer that drives the page.

### Import and type the data

1. **Get Data > Text/CSV**, choose `bi/exports/mart_tax_group.csv`, then **Transform
   Data** to open Power Query. This report imports the wide mart only: every visual on
   the page reads `mart_tax_group`.
2. Set the column types to match the committed query step:
   - `tax_group`, `tax_summary_group`, `rate_code`, `rate_description` = Text
   - `bill_rate_percentage`, `effective_rate` = Decimal Number
   - `account_count`, `residential_taxable`, `commercial_taxable`,
     `resource_taxable`, `total_taxable` = Whole Number
   - `bill_amount`, `bill_value` = Fixed Decimal Number
3. **Close & Apply**. The table lands as `mart_tax_group`. The mart holds one tax year
   and carries no date column, so the model is this single table with no date table and
   no relationships.

### Measures (enter each verbatim)

    Total Taxable = SUM ( mart_tax_group[total_taxable] )

    Bill Amount = SUM ( mart_tax_group[bill_amount] )

    Effective Rate = DIVIDE ( [Bill Amount], [Total Taxable] )

    Bill Share = DIVIDE ( [Bill Amount], CALCULATE ( [Bill Amount], ALL ( mart_tax_group ) ) )

    Group Rank = RANKX ( ALLSELECTED ( mart_tax_group[tax_group] ), [Bill Amount], , DESC, Skip )

`ALL` in `Bill Share` releases every filter on the table, so the denominator stays the
whole billed total while the numerator follows the current tax group. `ALLSELECTED` in
`Group Rank` ranks within the slicer selection rather than within the whole table.
Formats in the committed model: `Bill Amount` currency, `Effective Rate` percentage
with two decimals, `Total Taxable` and `Group Rank` whole numbers.

### Visuals

- **Card**, `[Bill Amount]`, with display units set to **None** so the card prints the
  full figure to the cent rather than a rounded billions label.
- **Card**, `[Effective Rate]`. With nothing selected it reads 0.19 percent, which is
  1,001,727,311.03 over 523,318,932,375.
- **Clustered bar chart**: category axis `tax_group`, value `[Bill Amount]`, sorted by
  `[Bill Amount]` descending. `[Group Rank]` and `[Bill Share]` go in the **Tooltips**
  well, so hovering a bar gives the rank and the share of the municipal bill alongside
  the dollars.
- **Matrix**: **Rows** = `tax_group` sorted ascending, **Columns** = `rate_code`,
  **Values** = `[Bill Amount]`. Turn on **Conditional formatting > Background color**
  on the measure, a two-colour gradient from minimum to maximum, with blanks coloured
  as zero. Most group and rate cells are empty, so the colour picks out the few cells
  that carry the bill.
- **Slicer** on `tax_group`, set to **Dropdown** mode. It filters the cards, the bar,
  and the matrix.

### Save and file the artifacts

1. Turn on the project save format: **File > Options and settings > Options > Preview
   features > Power BI Project (.pbip) save option**, then restart if prompted.
2. **File > Save As**, choose **Power BI project files (.pbip)**, and save into
   `bi/powerbi/` as `property_tax_burden`. Commit the `.pbip` file together with its
   `property_tax_burden.Report/` and `property_tax_burden.SemanticModel/` text folders.
   Never commit a `.pbix`: the binary duplicates the data and does not diff.
3. Free Power BI Desktop has no public publish link, so the deliverable is the
   committed project plus an exported PNG or **File > Export > PDF**. The committed
   image is `bi/powerbi/screenshots/report.png`.

---

## Numbers must match

Total 2024 property tax billed reads **$1,001,727,311.03** in all three places, with no
filter, slicer, or dashboard selection applied:

- **SQL golden**: in `expected/tax_group_summary.csv`, the `bill_amount` column sums to
  1,001,727,311.03 across the 28 tax groups. The same column in
  `expected/rate_effective.csv` sums to the same figure across the rate codes, and so
  does `bill_amount` in `bi/exports/mart_tax_group.csv`.
- **Tableau**: the `Total 2024 bill` tile prints $1,001,727,311.03, since it is
  `SUM(Bill Amount)` over the whole `mart_tax_group` extract.
- **Power BI**: the `[Bill Amount]` card reads $1,001,727,311.03, which is
  `SUM ( mart_tax_group[bill_amount] )` with display units off.

If any of the three differs, the loaded CSV is stale: re-run `python run.py` from the
project folder, then refresh the Tableau extract and the Power BI import.
