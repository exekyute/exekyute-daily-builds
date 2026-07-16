# Power BI build guide: property tax burden index

A step-by-step build. Follow it top to bottom in Power BI Desktop; nothing here
is automated. The base project (SQL pipeline, golden test, dashboard) is
complete without this report, so this layer can be built any time after the
fact.

## Why Power BI for this data

The mart is one row per municipality per fiscal year, and everything worth
showing is either a ranking or a movement. That shape plays to the DAX
measures face of Power BI: RANKX handles the ranked bar, a year-index
CALCULATE handles the YoY change, and the headline figures sit naturally in
card visuals. A year slicer then gives every visual a time dimension for
free, which the static dashboard version of this project only approximates
with a dropdown. The BI layer is one tool, chosen on purpose for this data
shape rather than built in parallel across several.

## Prerequisites

- Power BI Desktop, free from the Microsoft Store. No service account, tenant,
  or licence sign-up is needed for any step here.
- Turn on the project save format: **File > Options and settings > Options >
  Preview features > Power BI Project (.pbip) save option**, then restart
  Power BI Desktop.
- The free deliverable is the committed `.pbip` project plus exported PNG or
  PDF screenshots. Publish to web is not available on free, and nothing below
  needs it.
- Run `python run.py` in the project folder first so
  `bi/exports/mart_tax_burden.csv` is fresh and verified against the golden
  output.

## Connect the data

1. **Get Data > Text/CSV**, pick `bi/exports/mart_tax_burden.csv`.
2. Keep **Import** mode (the default). Click **Transform Data** instead of
   Load, and set the column types exactly:

   | Column | Type |
   | --- | --- |
   | `area` | Text |
   | `area_type` | Text |
   | `year_label` | Text |
   | `year_start` | Whole Number |
   | `residential_rate` | Decimal Number |
   | `commercial_rate` | Decimal Number |
   | `spread` | Decimal Number |
   | `rank_in_year` | Whole Number |
   | `yoy_spread_change` | Decimal Number |
   | `is_outlier` | True/False |

3. **Close & Apply**. The table lands as `mart_tax_burden`; keep that name,
   the measures below use it.
4. One modelling step: select `year_start` in the Data pane and set
   **Summarization: Don't summarize**. It is a label, not a quantity.
5. One calculated column (**New column** on the table). Six names exist as
   both a Town and a Rural Municipality (Antigonish, Digby, Lunenburg,
   Pictou, Shelburne, Yarmouth), so putting bare `area` on an axis would
   merge two different municipalities into one bar. Build the disambiguated
   label and use it on every axis below:

```dax
municipality =
mart_tax_burden[area] & " (" & mart_tax_burden[area_type] & ")"
```

## Measures

Create each with **New measure** on the `mart_tax_burden` table. Paste
verbatim.

The base value. One row exists per municipality per year, so within any
single municipality-and-year context this sum IS the spread:

```dax
Total Spread = SUM ( mart_tax_burden[spread] )
```

The latest year in the data, immune to slicers:

```dax
Latest Year Overall =
CALCULATE ( MAX ( mart_tax_burden[year_start] ), ALL ( mart_tax_burden ) )
```

### 1. Ranked bar measure (RANKX)

Ranks municipalities by spread within whatever year the slicer has selected.
`Skip` tie handling matches the SQL `RANK()`:

```dax
Spread Rank =
RANKX (
    ALLSELECTED ( mart_tax_burden[municipality] ),
    CALCULATE ( SUM ( mart_tax_burden[spread] ) ),
    ,
    DESC,
    Skip
)
```

### 2. YoY spread change (year-index pattern)

The mart has no date column, so no time-intelligence function applies. The
year-index pattern does the same job: clear the year filter, re-filter to the
current year minus one.

```dax
Spread Prev Year =
VAR CurrentYear = MAX ( mart_tax_burden[year_start] )
RETURN
    CALCULATE (
        SUM ( mart_tax_burden[spread] ),
        REMOVEFILTERS ( mart_tax_burden[year_start] ),
        mart_tax_burden[year_start] = CurrentYear - 1
    )
```

```dax
Spread YoY Change =
VAR Prev = [Spread Prev Year]
RETURN
    IF ( ISBLANK ( Prev ), BLANK (), [Total Spread] - Prev )
```

One caveat: this measure looks at calendar year minus one. The
mart's `yoy_spread_change` column was computed with `LAG` over each
municipality's own observed years, so for a municipality with a gap year the
column compares against the previous observed year while the measure returns
BLANK. The column is authoritative; use it directly in table visuals, and use
the measure where a slicer-responsive value is wanted.

### 3. KPI card measures

A CALCULATE boolean filter cannot reference a measure on its right side, so
`[Latest Year Overall]` is captured in a VAR first and the column is compared
against that scalar:

```dax
Widest Spread =
VAR LatestYear = [Latest Year Overall]
RETURN
    CALCULATE (
        MAX ( mart_tax_burden[spread] ),
        ALL ( mart_tax_burden ),
        mart_tax_burden[year_start] = LatestYear
    )
```

```dax
Widest Spread Municipality =
VAR LatestYear = [Latest Year Overall]
VAR LatestRows =
    FILTER ( ALL ( mart_tax_burden ), mart_tax_burden[year_start] = LatestYear )
VAR TopRow =
    TOPN ( 1, LatestRows, mart_tax_burden[spread], DESC, mart_tax_burden[municipality], ASC )
RETURN
    CONCATENATEX ( TopRow, mart_tax_burden[municipality], ", " )
```

Same VAR treatment as Widest Spread, for the same reason:

```dax
Median Spread Latest Year =
VAR LatestYear = [Latest Year Overall]
RETURN
    CALCULATE (
        MEDIAN ( mart_tax_burden[spread] ),
        ALL ( mart_tax_burden ),
        mart_tax_burden[year_start] = LatestYear
    )
```

### 4. Outlier flag

No measure needed; the mart carries `is_outlier`. The table visual below
filters on it.

## Report layout

One page, roughly three bands:

1. **Top band, three Card visuals:**
   - `Widest Spread` (format: 4 decimal places)
   - `Widest Spread Municipality`
   - `Median Spread Latest Year` (4 decimal places)
2. **Left, the ranked bar:** Bar chart, Y-axis `municipality`, X-axis
   `Total Spread`, tooltips `Spread Rank` and `Spread YoY Change`. Sort
   descending by `Total Spread` (visual header **... > Sort axis**).
3. **Right, the outlier table:** Table visual with `municipality`, `spread`,
   `rank_in_year`, `yoy_spread_change`. In the Filters pane, set
   `is_outlier` **is True**.

**Slicer:** add `year_start` as a dropdown slicer, single select, and select
the latest year. Point it at the bar chart and the outlier table (it will not
disturb the cards; their measures pin the year with `ALL`). With an older year
selected, the bar re-ranks and the outlier table goes empty, which is correct:
the flag is defined on the latest year only.

## Numbers must match

With fiscal 2025/2026 selected (year_start 2025), the report must read
identically to the SQL golden output and the dashboard:

- Widest Spread card: 3.9000
- Widest Spread Municipality card: CLARK'S HARBOUR (Town)
- Median Spread Latest Year card: 1.9760
- Top of the ranked bar: CLARK'S HARBOUR (Town) at 3.90, then
  MULGRAVE (Town) at 3.2882
- Outlier table: exactly 9 rows (Clark's Harbour, Mulgrave, and the seven
  Cape Breton Regional communities tied at spread 3.1901)

If any card disagrees, a column type or a measure was mistyped; nothing else
in this build can move a number.

## Save and export

1. **File > Save as**, choose type **Power BI Project (*.pbip)**, save as
   `mart_tax_burden` inside `bi/powerbi/`. That writes a `.pbip` pointer file
   plus `mart_tax_burden.Report/` and `mart_tax_burden.SemanticModel/`
   folders, all text.
2. Screenshots: with the report open, **File > Export > Export to PDF** (or
   plain screenshots of the page), saved into `bi/powerbi/screenshots/`.

## Data source path

Power BI writes the CSV path into
`mart_tax_burden.SemanticModel/definition/tables/mart_tax_burden.tmdl` as an
absolute path when you first connect. The committed copy is rewritten to the
relative `..\exports\mart_tax_burden.csv` so no local path or machine name
lands in git. On reopening the project, if Power BI cannot resolve that
relative path it will prompt for the file: point it back at
`bi/exports/mart_tax_burden.csv` and refresh. The model, measures, and report
layout are all intact either way.

## Commit rules

- Commit: the `.pbip` file, both project definition folders (`.Report` and
  `.SemanticModel`, everything under `definition/`, plus `.platform`,
  `definition.pbir`, `definition.pbism`, `StaticResources/`), and everything
  in `bi/powerbi/screenshots/`.
- Do not commit: any `.pbix` (binary export) and the machine-local `.pbi/`
  folders (localSettings.json, editorSettings.json, cache.abf). The folder
  `.gitignore` already excludes `**/.pbi/` and `*.pbix`.
