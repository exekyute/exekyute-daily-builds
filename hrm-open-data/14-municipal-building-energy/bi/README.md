# BI build guides: municipal building energy and emissions

Both dashboards read one frozen file, `bi/exports/mart_energy.csv`, written by the SQL
export step. It is 285 rows and one row is one building and one energy type: the
building's total consumption in that fuel's unit, its total cost in dollars and cents,
and the cost per unit. Neither tool recomputes any of the analysis. Both aggregate the
frozen cents as written, so a figure read in Tableau equals the same figure in Power BI
to the cent. One rule governs every aggregation below: `cost` is the only column that
sums across fuels, because consumption is metered in gigajoules, kilowatt-hours, and
litres, so a consumption total is only meaningful within a single `energy_type`. Column
meanings are in `bi/exports/data_dictionary.md`.

Tableau live link: https://public.tableau.com/views/HalifaxMunicipalBuildingEnergyandEmissions/Energydashboard

- [Tableau guide](#tableau-guide-cost-and-consumption)
- [Power BI guide](#power-bi-guide-decomposition-and-ranking)
- [Numbers must match](#numbers-must-match)

---

## Tableau guide: cost and consumption

### What this dashboard shows

Two stacked panels over the same mart. The top panel is a bar of total cost per building
for the 20 costliest buildings, each bar split by fuel colour, so the fuel mix inside a
building is readable at the same time as its rank. The bottom panel is a small-multiple
bar, one row band per fuel, of consumption per building. The fuels use three different
units, so each row band gets its own axis and no two units ever share a scale. A third
worksheet holds the total cost figure on its own and is not placed on the dashboard.

### Prerequisites

- Tableau Public Desktop Edition, free from https://public.tableau.com (Download on the
  top nav). Install with defaults.
- A free public.tableau.com account (Sign Up on the same page). Anything published with
  Tableau Public is public, which is fine here because the source is open data.
- Tableau Public works extract-only from files. It loads the CSV into an extract on
  publish and needs no database connection.

### Connect the data

1. Open Tableau Public. Under **Connect > To a File**, click **Text file**.
2. Browse to this repo's `bi/exports/mart_energy.csv` and open it.
3. Check the types Tableau inferred on the data source page:
   - `building_name`, `hrm_building_id`, `energy_type`, `unit_of_measure` are strings
     (Abc icon), and land as dimensions.
   - `consumption`, `cost`, `cost_per_unit` are numbers (#), decimals, and land as
     measures.
   Leave the connection on **Extract**.
4. Right-click the `Cost` field > **Default Properties > Number Format**, pick **Number
   (Custom)**, 2 decimal places, thousands separator on. The committed workbook carries
   `n#,##0.00;-#,##0.00` on this field.
5. Click **Sheet 1** to start building.

### Sheet 1: Cost by building and fuel

The 20 costliest buildings, each bar split by fuel.

1. Rename the sheet `Cost by building and fuel`.
2. Drag `Building Name` to **Columns**. It stays discrete (blue).
3. Drag `Cost` to **Rows**. Confirm the pill reads `SUM(Cost)`.
4. Drag `Energy Type` to **Color** on the Marks card. The mark type is **Bar**, and with
   one measure and a colour dimension the bars stack, so each bar is the building's total
   cost split into its fuels.
5. Drag `Building Name` to the **Filters** shelf. On the **Top** tab choose **By field**,
   **Top**, `20`, by `Cost`, `Sum`. That is the 20-building cut.
6. Sort the axis: right-click the `Building Name` pill > **Sort**, sort by **Field**,
   **Descending**, field `Cost`, aggregation `Sum`. Scotiabank Centre leads.

There are no calculated fields on this sheet. Every pill is a raw mart column.

### Sheet 2: Consumption by fuel

One bar band per fuel, each on its own axis.

1. New worksheet, rename it `Consumption by fuel`.
2. Drag `Building Name` to **Columns**.
3. Drag `Energy Type` to **Rows**, then drag `Consumption` to **Rows** to its right. The
   view splits into one row band per fuel, with `SUM(Consumption)` drawn as bars in each.
4. Right-click the `SUM(Consumption)` axis > **Edit Axis**, and under **Range** tick
   **Independent axis ranges for each row or column**. This is the step that keeps
   gigajoules, kilowatt-hours, and litres off a shared scale. Without it the electricity
   band flattens the other three to nothing.
5. Sort the axis: right-click the `Building Name` pill > **Sort**, by **Field**,
   **Descending**, field `Consumption`, aggregation `Sum`.

This sheet carries no filter, so all 160 buildings are on it, unlike sheet 1.

### Sheet 3: Numbers match

A single text mark carrying the municipal total.

1. New worksheet, rename it `Numbers match`. Leave **Rows** and **Columns** empty.
2. Set the Marks type to **Text**, and drag `Cost` onto **Text**. Confirm `SUM(Cost)`.
3. Format the number on the pill, not in the label editor: right-click `SUM(Cost)` on
   the **Text** card > **Format**, and on the **Pane** tab set **Numbers > Currency
   (Custom)** with 2 decimal places, thousands separator on, and negatives in
   parentheses (`$#,##0.00;($#,##0.00)`). This overrides the plain-number default set on
   the field at connect time, for this sheet only. The mark reads $86,444,113.77.

### Dashboard

1. Click **New Dashboard** and rename it `Energy dashboard`. Size: **Automatic**.
2. Drag `Cost by building and fuel` in first, then drag `Consumption by fuel` below it.
   The two sheets stack vertically at roughly equal height.
3. Keep the dashboard title shown at the top.
4. Keep one `Energy Type` colour legend on the right and set that zone to a fixed width
   of 160. Remove any duplicate legend the second sheet brings in.
5. Leave `Numbers match` off the dashboard. It is a check sheet, not a panel.

Tableau auto-generates a Phone layout for this dashboard; the committed workbook keeps it.

### Publish and file the artifacts

Tableau Public Desktop has no local save to disk. **File > Save** and **File > Save As**
both redirect to **Save to Tableau Public As...**, which uploads to the Tableau Public
cloud, so getting a committable `.twb` runs through the cloud and a `.twbx` unzip.

1. **File > Save to Tableau Public As...**, sign in, and name it
   `Halifax Municipal Building Energy and Emissions`. Publishing uploads the extract and
   opens the viz in a browser. That name is what produces the live link at the top of
   this file.
2. On the viz page, click **Download Workbook**. It always downloads as a `.twbx`
   (packaged), never a bare `.twb`.
3. A `.twbx` is a zip. Copy it, rename the copy to `.zip`, unzip it, and pull the `.twb`
   from the archive root. Commit that file as
   `bi/tableau/municipal_building_energy.twb`. Never commit the `.twbx`: the packaged
   extract duplicates the data, bloats the repo, and does not diff.
4. The unzipped `.twb` points its text connection at the packaged copy of the CSV. The
   committed workbook is repointed at `../exports/mart_energy.csv`, relative to
   `bi/tableau/`, so it reopens against the repo mart. Repoint it the same way before
   committing.
5. Screenshots go in `bi/tableau/screenshots/`. The committed one is
   `dashboard-full.png`.

---

## Power BI guide: decomposition and ranking

### What this report shows

One page, four visuals over the same mart. A card holds the municipal energy cost. A
decomposition tree breaks that cost down by fuel and then by building. A bar chart ranks
the 20 costliest buildings with rank and cost share in the tooltip. A matrix reads cost
per unit for each fuel, one row per fuel, which is the only shape where a cross-fuel
consumption denominator cannot form.

### Import and type the data

1. **Home > Get Data > Text/CSV**, choose this repo's `bi/exports/mart_energy.csv`, then
   **Transform Data** to open Power Query.
2. Set the column types:
   - `building_name` = Text
   - `hrm_building_id` = Text
   - `energy_type` = Text
   - `unit_of_measure` = Text
   - `consumption` = Decimal Number
   - `cost` = Fixed decimal number
   - `cost_per_unit` = Decimal Number
3. **Close & Apply**. The table lands as `mart_energy`.

The model is this one table. The mart has no date column, so the committed semantic model
carries no date table, no calendar, and no relationships.

### Measures (enter each verbatim)

Five clicks of **Modeling > New measure**, one per block, exactly as written:

    Total Cost = SUM ( mart_energy[cost] )

    Total Consumption = SUM ( mart_energy[consumption] )

    Cost per Unit = DIVIDE ( [Total Cost], [Total Consumption] )

    Building Rank = RANKX ( ALLSELECTED ( mart_energy[building_name] ), [Total Cost], , DESC, Skip )

    Cost Share = DIVIDE ( [Total Cost], CALCULATE ( [Total Cost], ALL ( mart_energy ) ) )

Formats, set on each measure under **Measure tools > Format**:

- `Total Cost`: Currency, 2 decimal places (`$#,0.00`).
- `Cost per Unit`: Decimal, 4 decimal places (`#,0.0000`).
- `Building Rank`: Whole number (`0`).
- `Cost Share`: Percentage, 2 decimal places (`0.00%`).
- `Total Consumption` keeps the general number format.

`Total Consumption` is a plain `SUM` across whatever rows are in context, so it will
happily add gigajoules to litres if you let it. Only read it, and only read
`Cost per Unit` which divides by it, inside a single `energy_type`. That is why the one
visual carrying `Cost per Unit` puts `energy_type` on rows.

`Cost Share` divides by `ALL ( mart_energy )`, so its denominator is the full municipal
cost regardless of the current filter, and `Building Rank` ranks over
`ALLSELECTED ( mart_energy[building_name] )`, so the rank respects a slicer but not the
row context.

### Visuals

- **Card**: `Data` = `[Total Cost]`. Set **Display units** to **None** so it prints the
  full figure rather than a rounded millions abbreviation. With no filters it reads
  $86,444,113.77.
- **Decomposition tree**: `Analyze` = `[Total Cost]`, `Explain by` = `energy_type` then
  `building_name`, in that order. Pin both levels and sort by `[Total Cost]` descending.
  Set **Max bars to show** per level to 6. Expanding the Electricity node walks straight
  from the largest fuel to the buildings inside it.
- **Clustered bar chart**: `Y axis` = `[Total Cost]`, `Y axis category` =
  `building_name`, `Tooltips` = `[Building Rank]` and `[Cost Share]`. Add a **Top N**
  filter on `building_name`, Top `20` by `[Total Cost]`, and sort descending. This is the
  same 20-building cut as the Tableau cost panel.
- **Matrix**: `Rows` = `energy_type`, then `unit_of_measure` beneath it as a drill level,
  `Values` = `[Cost per Unit]`. Turn **row subtotals** and **column subtotals** off: a
  subtotal here would divide dollars by a mixed-unit denominator and produce a figure
  that means nothing.

### Save and file the artifacts

1. Turn on the project save format: **File > Options and settings > Options > Preview
   features > Power BI Project (.pbip) save option**, then restart if prompted.
2. **File > Save As**, choose **Power BI project files (.pbip)**, and save into
   `bi/powerbi/` as `municipal_building_energy`. Commit the `.pbip` file together with its
   `.Report/` and `.SemanticModel/` text folders, which is where the measures above live
   as TMDL and the visuals as JSON. Never commit a `.pbix`; the binary duplicates the data
   and does not diff.
3. Free Power BI Desktop has no public publish link, so the deliverable is the committed
   project plus an exported PNG or a **File > Export > PDF**. The committed screenshot is
   `bi/powerbi/screenshots/report.png`.

---

## Numbers must match

**Total municipal energy cost reads $86,444,113.77**, identical in all three places by
construction:

- **SQL golden**: in `expected/cost_by_fuel.csv`, the `cost` column sums across the four
  fuel rows to 86,444,113.77 (Electricity 64,450,969.11, Natural Gas 15,153,963.12, Fuel
  Oil 5,938,197.64, Propane 900,983.90).
- **Tableau**: the `Numbers match` worksheet is a single text mark of `SUM(Cost)` over
  all 285 mart rows and prints $86,444,113.77.
- **Power BI**: the `[Total Cost]` card, with no filters and display units set to None,
  reads $86,444,113.77.

The same holds one level down. Scotiabank Centre is the costliest building at
$6,127,063.69, which is rank 1 in `expected/costliest_buildings.csv`, the tallest bar on
the Tableau cost panel, and `[Total Cost]` 6,127,063.69 with `[Building Rank]` 1 and
`[Cost Share]` 7.09% on the Power BI bar chart. Cost per unit ties the same way:
`expected/cost_per_unit_by_fuel.csv` gives Electricity 0.1158, Fuel Oil 0.9879, Natural
Gas 16.9263, Propane 0.6277, which is exactly what the Power BI matrix prints per fuel
row.

If any tied figure differs, the CSV loaded is stale. Re-run `python run.py` from the
project folder, then refresh the Tableau extract and the Power BI import.
