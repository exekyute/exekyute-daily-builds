# 25: Emergency department closure hours

Nova Scotia emergency departments reported 520,811.3 closure hours across 38
sites and twelve fiscal years, 2012-13 to 2023-24. Temporary closures account
for 217,293.8 of those hours, 41.72 percent of the total, and 238 of the 456
site-years reported no closures at all.

## The data

Nova Scotia Open Data: **Emergency Department Closure Hours by Zone, Facility,
and Facility Type** (`75nx-yut7`). Source, licence, pull date, and provenance in
SOURCE.md.

## What it computes

Closure hours by zone, by facility type, and by site over the full window, each
with the temporary and scheduled split and each site's temporary share.
Temporary share is temporary hours over the reported total column, guarded so
the denominator is above zero, and a reconciliation check confirms that
temporary plus scheduled equals that total on all 456 rows, reporting the count
and size of any break. Zone totals also carry year-over-year change, taken by
`LAG` over an integer fiscal year derived from labels like `2023-24`. Rows
reading 0.0 hours are kept throughout, since they mean a site reported no
closures; the count of those is published rather than filtered away. All logic
lives in `sql/`; `run.py` holds none of it.

## Testing

DuckDB is the only dependency:

    pip install duckdb

From this folder:

    python run.py            # runs the SQL end to end, then verifies
    python run.py verify     # re-runs the golden diff only
    python run.py show       # prints closure hours by zone

`python run.py` writes out/ed_closures.csv, checks it against
expected/ed_closures.csv, and prints PASS when they match row for row. Then
double-click dashboard/dashboard.html; it reads the exported data and re-derives
the same headline figures. The Power BI build guide is in bi/README.md.

<!-- Screenshots (capture into images/, then replace this comment with the image lines, alt text as a short descriptive sentence ending in a period):
     01-run.png        a full `python run.py` ending in PASS
     02-result.png     `python run.py show` with closure hours by zone
     03-dashboard.png  the dashboard open in a browser -->

## License

MIT. Copyright (c) 2026 Kevin Yu (https://github.com/exekyute).
