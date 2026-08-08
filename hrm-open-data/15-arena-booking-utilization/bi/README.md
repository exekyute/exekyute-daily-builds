# BI build guides: arena booking utilization

Two dashboards, one dataset. The SQL pipeline freezes a use-type mart to
`bi/exports/mart_arena.csv` (one row per pad, month, and use type); both tools read that
same file and recompute nothing. Tableau draws a facility-by-month heatmap and an
ice-versus-dry-floor dual read; Power BI builds a proper date table with
time-intelligence measures and a ranked matrix. Column meanings are in
`bi/exports/data_dictionary.md`. `booked_hours` sums cleanly, so every total below is a
ratio or sum of that one column.

Tableau live link: https://public.tableau.com/views/HalifaxArenaBookingUtilization/Arenabookingutilization

- [Tableau guide](#tableau-guide-heatmap-and-stacked-area)
- [Power BI guide](#power-bi-guide-time-intelligence-and-matrix)
- [Numbers must match](#numbers-must-match)

---

## Tableau guide: heatmap and stacked area

### What this dashboard shows

A facility-by-month grid of booking intensity is a heatmap, which Tableau reads at a
glance, and the ice-versus-dry-floor story is a two-series time shape (a stacked area)
that Tableau builds in a few clicks. There is no geography in this dataset, so no
geocoding step and no boundary join: the whole story is the calendar of bookings and how
ice and dry-floor time move through it.

### Prerequisites

- Tableau Public Desktop Edition for Windows, free from https://public.tableau.com
  (Download on the top nav). Install with defaults.
- A free public.tableau.com account (Sign Up on the same page). Vizzes published with
  Tableau Public are public; that is fine here because the data is already open data.
- Tableau Public works extract-only from files: it loads the CSV into an extract when
  you publish. It needs no database connection.

### Connect the data

1. Open Tableau Public. Under **Connect > To a File**, click **Text file**.
2. Browse to this repo's `bi/exports/mart_arena.csv` and open it.
3. On the data source page, check the field types Tableau inferred:
   - `facility`, `use_type` should be strings (Abc icon).
   - `month_start` should be a Date.
   - `year`, `bookings` should be whole numbers (#).
   - `booked_hours` should be a number (#), a decimal.
   Tableau connects as an extract by default here; leave it on **Extract**.
4. Click **Sheet 1** to start building.

### Sheet 1: utilization heatmap

A pad-by-month grid coloured by how heavily each pad is booked.

1. Rename the sheet `Utilization heatmap`.
2. Drag `month_start` to **Columns** and set it to discrete `MONTH(month_start)`
   (right-click the pill > Month from the **upper** date-part group, the blue one). Drag
   a second `month_start` to **Columns** to the **right** of that pill and set it to
   discrete `YEAR(month_start)`. Month is then the outer header and year the inner one,
   so each January column splits into 2025, 2026 and 2027 and the same month lines up
   season against season.
3. Drag `facility` to **Rows**. Each pad is now a row.
4. Drag `booked_hours` to **Color**. Confirm the pill reads `SUM(booked_hours)`. Pick a
   sequential ramp (for example Orange or Blue, light to dark) so the busiest pad-months
   read darkest. Set the mark type to **Square** for a filled heatmap. The committed
   sheet also prints the hours in each cell: drop a second `booked_hours` on **Label**.
5. Optional, colour by the utilization proxy instead of raw hours. The proxy needs a
   pad-month capacity, which is `days_in_month * 18`. Add these calculated fields with
   **Analysis > Create Calculated Field**, once per field, typing the name to the left of
   the `=` into the box at the top of the editor and only the expression after it into
   the formula body (they are only well defined when each cell resolves to a single real
   month, so keep `YEAR` on the view from step 2):

       Days In Month = DAY ( DATEADD ( 'day', -1, DATEADD ( 'month', 1, DATETRUNC ( 'month', [month_start] ) ) ) )
       Capacity Hours = MIN ( [Days In Month] ) * 18
       Utilization = SUM ( [booked_hours] ) / [Capacity Hours]

   Drag `Utilization` onto Color in place of `booked_hours`. Format it as a percentage.
   It matches the golden's `utilization` column per pad-month and, as documented, can
   exceed 100 percent because bookings overlap. Colouring by `booked_hours` is the
   simpler default, is what the committed sheet uses, and is what the numbers-match check
   below asserts.

### Sheet 2: ice vs dry floor

The two-use time shape.

1. New worksheet, rename it `Ice vs dry floor`.
2. Drag `month_start` to **Columns**. It lands as discrete Year (blue) by default. Open
   the pill dropdown and pick **Month** from the **upper** group (the date-part group,
   shown as `May`), then set the same pill to **Continuous**. It turns green and the axis
   reads `Month of Month Start`, 1 to 12, so every January in the file stacks into one
   point and the chart is a season profile rather than a running timeline.
3. Drag `booked_hours` to **Rows**. Confirm `SUM(booked_hours)`.
4. Drag `use_type` to **Color**. Set the mark type to **Area** for a stacked area: ice,
   dry floor, and other stack into the month's total, and the ice band is the tall one.
5. Drag `year` to the **Filters** shelf and keep 2025 to 2027, the range the committed
   sheet uses. `year` is a number, so Tableau asks how to filter first: choose
   **All values**, then set the range. What the filter drops is 76.0 booked hours in 2028
   and 22.0 in 2029, forward holds with no ice in them.
6. To unstack into three separate lines instead of a stacked area, set
   **Analysis > Stack Marks > Off**, or switch the Marks type to **Line**. (A dual axis
   does not work here; it needs two measures and cannot split one measure by `use_type`.)

### Dashboard

1. Click **New Dashboard** and name it `Arena booking utilization`. Set Size to
   **Fixed size**, 1000 by 800.
2. Drag `Utilization heatmap` to the top and `Ice vs dry floor` below it.
3. Drag `facility` to the Filters shelf on **one** sheet, then right-click the pill and
   set **Apply to Worksheets > All Using This Data Source**. That single filter drives
   both sheets. Do not add it per sheet, that makes redundant pills. The committed
   dashboard leaves the filter applied but not shown, so the only cards down the right
   side are the two colour legends.

### Publish and file the artifacts

Tableau Public Desktop has no local save to disk. **File > Save** and **File > Save As**
both redirect to **Save to Tableau Public As...**, which uploads to the Tableau Public
cloud, so getting a committable `.twb` runs through the cloud and a `.twbx` unzip.

1. **File > Save to Tableau Public As...**, sign in, and name it
   `Halifax Arena Booking Utilization`. Publishing uploads the extract and opens the viz
   in a browser at the live link above.
2. On the viz page, click **Download Workbook**. It always downloads as a `.twbx`
   (packaged), never a bare `.twb`.
3. A `.twbx` is a zip. Copy it, rename the copy to `.zip`, unzip it, and pull the `.twb`
   from the archive root. Commit that file as
   `bi/tableau/arena_booking_utilization.twb`. Never commit the `.twbx`: the packaged
   extract duplicates the data, bloats the repo, and does not diff.
4. The unzipped `.twb` points its text connection at the packaged copy of the CSV. The
   committed workbook is repointed at `../exports/mart_arena.csv`, relative to
   `bi/tableau/`, so it reopens against the repo mart. Repoint it the same way before
   committing.
5. Screenshots go in `bi/tableau/screenshots/`. The committed one is
   `dashboard-full.png`.

---

## Power BI guide: time intelligence and matrix

### What this report shows

The month column is a real date, so Power BI's date table and time-intelligence
functions apply: a `SAMEPERIODLASTYEAR` measure sets each season against the one before
without any manual year indexing. A pad-by-use-type matrix with a RANKX ranking beside it
reads the busiest pads at a glance. The heatmap and the season profile stay in Tableau;
this report covers the year-over-year read and the ranking.

### Import and type the data

1. **Get Data > Text/CSV**, choose this repo's `bi/exports/mart_arena.csv`, then
   **Transform Data** to open Power Query.
2. Set the column types:
   - `facility` = Text
   - `use_type` = Text
   - `month_start` = Date
   - `year` = Whole Number
   - `bookings` = Whole Number
   - `booked_hours` = Decimal Number
3. **Close & Apply**. The table lands as `mart_arena`.

### Add a date table

Modeling > New table:

    Date = CALENDAR ( MIN ( mart_arena[month_start] ), MAX ( mart_arena[month_start] ) )

Mark it as a date table (Table tools > Mark as date table, on the `[Date]` column). In
Model view, create a relationship `Date[Date]` to `mart_arena[month_start]`,
many-to-one, single direction.

The mart is monthly, so the line chart plots a month label rather than a day. Add one
calculated column on the date table (Table tools > New column):

    Year-Month = FORMAT ( 'Date'[Date], "YYYY-MM" )

### Measures (enter each verbatim)

    Booked Hours = SUM ( mart_arena[booked_hours] )

    Total Bookings = SUM ( mart_arena[bookings] )

    Ice Hours = CALCULATE ( [Booked Hours], mart_arena[use_type] = "Ice" )

    Ice Share = DIVIDE ( [Ice Hours], [Booked Hours] )

    Booked Hours LY = CALCULATE ( [Booked Hours], SAMEPERIODLASTYEAR ( 'Date'[Date] ) )

    Facility Rank = RANKX ( ALLSELECTED ( mart_arena[facility] ), [Booked Hours], , DESC, Skip )

Format `Ice Share` as Percentage with 2 decimal places (Measure tools > Format >
Percentage, 2 decimals).

### Visuals

1. **Cards**: one card for `[Booked Hours]` and one for `[Ice Share]`. With no filters,
   they read the numbers-match figures below (107,533.25 and 70.11 percent).
2. **Line chart, the time-intelligence view**: axis `Date[Year-Month]`, values
   `[Booked Hours]` and `[Booked Hours LY]`, so each month sits against the same month a
   year earlier.
3. **Matrix**: **Rows** = `facility`, **Columns** = `use_type`, **Values** =
   `[Booked Hours]`. Turn on **Conditional formatting > Background color** on the measure,
   a two-colour gradient over `[Booked Hours]`, so the heaviest cells stand out. It
   carries the same read as the Tableau heatmap's colour ramp, across use types rather
   than months.
4. **Ranked bar**: **Axis** = `facility`, **Values** = `[Booked Hours]`, and add
   `[Facility Rank]` to the tooltip or as a data label. Sort descending; Arena leads.

### Save and file the artifacts

1. Turn on the project save format: **File > Options and settings > Options > Preview
   features > Power BI Project (.pbip) save option**, then restart if prompted.
2. **File > Save As**, choose **Power BI project files (.pbip)**, and save into
   `bi/powerbi/` as `arena_booking_utilization`. Commit the `.pbip` file together with its
   `.Report/` and `.SemanticModel/` text folders. Never commit a `.pbix`; the binary
   duplicates the data and does not diff.
3. Free Power BI Desktop has no public publish link, so the deliverable is the committed
   project plus an exported **File > Export > PDF** or a PNG screenshot of the cards, the
   line chart, the matrix, and the ranked bar. The committed screenshot is
   `bi/powerbi/screenshots/report.png`.

---

## Numbers must match

Every view aggregates the same frozen mart, so the same figures read across all three.

**Total booked arena hours read 107,533.25, with ice 70.11 percent**, identical in all
three by construction:

- **SQL golden** (`expected/arena_utilization.csv`): the `booked_hours` column sums to
  107,533.25 and the `ice_hours` column to 75,394.0, so ice is 75,394.0 / 107,533.25 =
  70.11 percent. The project README quotes those two figures, 107,533.25 booked hours and
  ice at 70.11 percent.
- **Tableau**: on the `Utilization heatmap` sheet, the cell labels total 107,533.25 across
  every pad and month. All 75,394.0 ice hours fall inside 2025 to 2027, so the ice band of
  the `Ice vs dry floor` sheet reads that same 75,394.0 with its year filter on.
- **Power BI**: the `[Booked Hours]` card reads 107,533.25 and the `[Ice Share]` card
  reads 70.11 percent (`[Ice Hours]` = 75,394.0).

If any tied figure differs, the CSV loaded is stale: re-run `python run.py` from the
project folder and reconnect or refresh the extract.
