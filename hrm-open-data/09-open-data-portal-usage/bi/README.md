# BI build guides: open data portal usage

The report reads two frozen files, `bi/exports/mart_usage_monthly.csv` and
`bi/exports/mart_usage_by_dataset.csv`, written by the SQL export step. Both are
byte-for-byte identical to the goldens in `expected/`. The report recomputes nothing
structural: it binds to the same integer hit counts the golden holds, so the Total Usage
card reads the exact figure `expected/mart_usage_monthly.csv` sums to.

The committed dashboard is the Power BI project `bi/powerbi/open_data_portal_usage.pbip`.
Neither mart carries geography, and each row resolves to one monthly count or one
dataset total, so the data has one time grain and one ranking grain and nothing to place
on a map. That is what the report reads: a usage line with a trailing three-month total,
a ranked-dataset bar, and a card.

The marts:

- `bi/exports/mart_usage_monthly.csv`, 136 rows, one per month from 2014-07 to
  2025-10. Carries `month_start`, `year`, `total_usage`, `distinct_datasets`.
- `bi/exports/mart_usage_by_dataset.csv`, 237 rows, one per dataset. Carries
  `dataset`, `total_usage`, `first_month`, `last_month`, `usage_rank`.

Column definitions and the totals to check after import are in
`bi/exports/data_dictionary.md`.

- [Power BI guide](#power-bi-guide-usage-line-and-ranked-datasets)
- [Numbers must match](#numbers-must-match)

---

## Power BI guide: usage line and ranked datasets

### What this report shows

One page, 1280 by 720, holding five items: a title text box, a card for total recorded
usage, a line chart of monthly usage with a trailing three-month total overlaid, a bar
chart ranking the top 15 datasets with the rank in the tooltip, and a year slicer that
drives the line and the card.

### Import and type the data

1. **Home > Get Data > Text/CSV**, pick `bi/exports/mart_usage_monthly.csv`, then
   **Transform Data** to open Power Query.
2. Set the column types:
   - `month_start` = Date
   - `year` = Whole Number
   - `total_usage`, `distinct_datasets` = Whole Number
3. **Close & Apply**. The table lands as `mart_usage_monthly`, 136 rows.
4. **Home > Get Data > Text/CSV** again, pick `bi/exports/mart_usage_by_dataset.csv`,
   **Transform Data**, and set the column types:
   - `dataset` = Text
   - `total_usage` = Whole Number
   - `first_month`, `last_month` = Date
   - `usage_rank` = Whole Number
5. **Close & Apply**. The table lands as `mart_usage_by_dataset`, 237 rows.

The CSV headers import in their lower-case form. DAX resolves column names
case-insensitively, so the `[Dataset]` reference in the rank measure below binds to the
imported `dataset` column.

### Add a date table

**Modeling > New table**, so the usage line and the rolling measure share one calendar:

    Date = CALENDAR ( MIN ( mart_usage_monthly[month_start] ), MAX ( mart_usage_monthly[month_start] ) )

Add two calculated columns on it:

    Year = YEAR ( 'Date'[Date] )

    Month Start = DATE ( YEAR ( 'Date'[Date] ), MONTH ( 'Date'[Date] ), 1 )

Mark it as a date table (**Table tools > Mark as date table**, on the `[Date]` column).
In Model view, create the relationship from `mart_usage_monthly[month_start]` to
`Date[Date]`, many-to-one, single direction, with `Date` on the filtering side.
`month_start` is always the first of the month, so each month's row matches exactly one
date in the calendar.

The two columns each earn their place. `Year` is what the slicer binds to, so the filter
travels through the relationship rather than sitting on the fact table where it would not
propagate. `Month Start` is the line chart axis: marking a table as a date table removes
Power BI's automatic date hierarchy, so there is no month level to drill to and an
explicit column is needed.

### Measures (enter each verbatim)

Four clicks of **Modeling > New measure**, one per block, exactly as written:

    Total Usage = SUM ( mart_usage_monthly[total_usage] )

    Usage Rolling 3M = CALCULATE ( [Total Usage], DATESINPERIOD ( 'Date'[Date], MAX ( 'Date'[Date] ), -3, MONTH ) )

    Dataset Usage = SUM ( mart_usage_by_dataset[total_usage] )

    Dataset Rank = RANKX ( ALLSELECTED ( mart_usage_by_dataset[Dataset] ), [Dataset Usage], , DESC, Skip )

Formats, set on each measure under **Measure tools > Format**: `Total Usage`,
`Usage Rolling 3M` and `Dataset Usage` are whole numbers with a thousands separator
(`#,0`), and `Dataset Rank` is a plain whole number (`0`). The committed model keeps all
four on the `Date` table, which is where **New measure** puts them if `Date` is the
selected table at the time.

`Usage Rolling 3M` sums the three-month window rather than averaging it, so it reads as
trailing volume and sits above the monthly line. It only resolves against the marked date
table, which is why the line chart axis has to come from `Date` and not from
`mart_usage_monthly[month_start]`.

### Visuals

- **Text box** across the top of the page, holding `Halifax open data portal usage` in
  bold at 24pt.
- **Card**, value `[Total Usage]`. Set **Display units** to **None** so it prints the
  full figure rather than a rounded millions abbreviation. With no slicer selection it
  reads 555,050,254.
- **Line chart**, titled `Monthly usage with trailing 3-month total`. Axis
  `'Date'[Month Start]`, sorted ascending; values `[Total Usage]` and
  `[Usage Rolling 3M]` as a second line. The facts sit on the first of each month, so a
  day-grain axis would render a spiky, mostly empty line; the month column is what gives
  the clean 136-point series. To check the rolling measure, hover the final point,
  2025-10: `[Total Usage]` reads 2,758,781 and `[Usage Rolling 3M]` reads 13,375,382,
  which is August plus September plus October in the golden (5,008,636 + 5,607,965 +
  2,758,781).
- **Clustered bar chart**, titled `Top 15 datasets by total usage`. Category `dataset`,
  value `[Dataset Usage]`, `[Dataset Rank]` in the **Tooltips** well, sorted by
  `[Dataset Usage]` descending. Add a **Top N** filter on `dataset`, Top `15` by
  `[Dataset Usage]`. Zoning Boundaries leads at rank 1 with 91,508,850 hits, ahead of
  Street Centrelines at 74,719,864 and Civic Addresses at 44,444,508.
- **Slicer** on `'Date'[Year]`, in **Dropdown** mode, so a reader can hold the line and
  the card to one year. It does not move the ranked bar: `mart_usage_by_dataset` carries
  whole-window totals with no month grain, so it has no relationship to the date table
  and no year to filter on. The bar is the all-time ranking by design.

### Save and file the artifacts

1. Turn on the project save format: **File > Options and settings > Options > Preview
   features > Power BI Project (.pbip) save option**, then restart if prompted.
2. **File > Save As**, choose **Power BI project files (.pbip)**, and save into
   `bi/powerbi/` as `open_data_portal_usage`. Commit the `.pbip` file together with its
   `.Report/` and `.SemanticModel/` text folders, which is where the measures above live
   as TMDL and the visuals as JSON. Never commit a `.pbix`: the binary duplicates the
   data and does not diff.
3. Free Power BI Desktop has no public publish link, so the deliverable is the committed
   project plus an exported PNG or a **File > Export > PDF**. The committed screenshot is
   `bi/powerbi/screenshots/report.png`.

---

## Numbers must match

**Total recorded open-data usage across the window reads 555,050,254**, identical in both
places by construction:

- **SQL golden**: in `expected/mart_usage_monthly.csv`, the `total_usage` column sums to
  555,050,254 across the 136 monthly rows. `expected/mart_usage_by_dataset.csv` sums to
  the same 555,050,254 across its 237 dataset rows, because the two marts roll the same
  hit counts up on different keys.
- **Power BI**: the `[Total Usage]` card, with no slicer selection and display units set
  to None, reads 555,050,254.

The ranking ties the same way. Zoning Boundaries is rank 1 in
`expected/mart_usage_by_dataset.csv` at 91,508,850, which is the top bar on the ranked
chart, reading `[Dataset Usage]` 91,508,850 with `[Dataset Rank]` 1 in the tooltip. The
month grain ties too: the last row of `expected/mart_usage_monthly.csv`, 2025-10, carries
`total_usage` 2,758,781, which is the final point on the usage line.

If any tied figure differs, the loaded CSV is stale. Re-run `python run.py` from the
project folder, then refresh the Power BI import.
