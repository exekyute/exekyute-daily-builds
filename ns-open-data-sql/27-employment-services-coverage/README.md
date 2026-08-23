# 27: Employment-services coverage

Maps the 47 Nova Scotia Works employment services centres across all five declared regions, 42 towns, and 32 postal areas. Cape Breton and HRM tie at the top with 12 centres each, 25.53 percent of the province apiece, and every centre publishes an email address, a website, and a Facebook page, while only 36 of 47 publish a Twitter account.

## The data

Nova Scotia Open Data: **NS Works Centre Locations** (`x7cs-y5zd`). Source, licence, and pull date in SOURCE.md. (Catalog idea #38.)

## What it computes

Centres per region and per town, regions ranked by centre count, and centres per FSA, the forward sortation area taken as the first three characters of the postal code. Coverage gaps are measured against a declared region universe held as a named constant in SQL and left joined onto the observed centres, so a region with no centres would appear as a zero row rather than vanish; spec.md says exactly where that list comes from and what it can and cannot detect. Service completeness is the share of centres publishing each of four declared contact channels. The source names its coordinate columns backwards, latitude in `x_coordinate` and longitude in `y_coordinate`, so the SQL swaps them once and exports the mart with columns named `latitude` and `longitude`. All logic lives in `sql/`; `run.py` holds none of it.

## Testing

DuckDB is the only dependency:

    pip install duckdb

From this folder:

    python run.py            # runs the SQL end to end, then verifies
    python run.py verify     # re-runs the golden diff only
    python run.py show       # prints centres per region

`python run.py` writes out/services_coverage.csv, checks it against expected/services_coverage.csv, and prints PASS when they match row for row. Then double-click dashboard/dashboard.html; it reads the exported data and re-derives the same headline figures. The Tableau build guide is in bi/README.md.

<!-- Screenshots (capture into images/, then replace this comment with the image lines, alt text as a short descriptive sentence ending in a period):
     01-run.png        a full `python run.py` ending in PASS
     02-result.png     `python run.py show` with centres per region
     03-dashboard.png  the dashboard open in a browser -->

## License

MIT. Copyright (c) 2026 Kevin Yu (https://github.com/exekyute).
