# 24: LTC bed-supply gap

145 licensed facilities hold 8,764 long-term care and residential care beds across Nova Scotia: 8,026 nursing home beds and 738 residential care beds. Central zone carries 35.77 percent of that supply from 37 facilities, and a single facility, Northwood Incorporated in Halifax, accounts for 385 beds on its own.

## The data

Nova Scotia Open Data: **Long-term Care and Residential Care Facilities** (`x76a-axw2`). Source, licence, and pull date in SOURCE.md. (Catalog idea #14.)

## What it computes

Beds per facility, per zone, and per facility type, under one stated definition: total beds are nursing home beds plus residential care beds, and the two respite bed columns are reported separately rather than folded in. On top of that it computes the nursing versus residential split, average and median beds per facility by zone, zones ranked by total beds, and the count of facilities in single entry access. Every row of the snapshot is either kept or assigned an exclusion class and counted, and the output carries a totals_tie section that re-sums the bed total five independent ways. All logic lives in `sql/`; `run.py` holds none of it.

## Testing

DuckDB is the only dependency:

    pip install duckdb

From this folder:

    python run.py            # runs the SQL end to end, then verifies
    python run.py verify     # re-runs the golden diff only
    python run.py show       # prints beds by zone and type

`python run.py` writes out/ltc_bed_supply.csv, checks it against expected/ltc_bed_supply.csv, and prints PASS when they match row for row. Then double-click dashboard/dashboard.html; it reads the exported data and re-derives the same headline figures. The Power BI build guide is in bi/README.md.

<!-- Screenshots (capture into images/, then replace this comment with the image lines, alt text as a short descriptive sentence ending in a period):
     01-run.png        a full `python run.py` ending in PASS
     02-result.png     `python run.py show` with beds by zone
     03-dashboard.png  the dashboard open in a browser -->

## License

MIT. Copyright (c) 2026 Kevin Yu (https://github.com/exekyute).
