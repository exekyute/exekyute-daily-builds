# 26: Invest NS deal book

Reads 4,553 Invest Nova Scotia financial-program deals worth $289,279,591.01 across six fiscal years (2018-2019 to 2023-2024). Halifax County holds $208,658,110.23 of that, or 72.13 percent, and a single recipient, Cognizant Technology Solutions Corporation, took $47,724,415.00 across three deals.

## The data

Nova Scotia Open Data: **Invest NS Financial Programs** (`6aac-8xtn`). Source, licence, and pull date in SOURCE.md. (Catalog idea #34.)

## What it computes

Contribution totals by sector, county, deal type, and fiscal year, each with its share of the total, plus the top 25 recipients and the deal-type mix inside every year. Blank contributions are counted on their own row and kept out of every sum and every denominator; the 257 genuine zeros are kept and counted separately. Deals whose county label is not a county, whose coordinates are missing, or whose coordinates land outside Nova Scotia are each counted and reported rather than dropped. The output carries a totals_tie section re-summing five separate breakdowns to the same grand total, exact to the cent. All logic lives in `sql/`; `run.py` holds none of it.

## Testing

DuckDB is the only dependency:

    pip install duckdb

From this folder:

    python run.py            # runs the SQL end to end, then verifies
    python run.py verify     # re-runs the golden diff only
    python run.py show       # prints contributions by sector

`python run.py` writes out/deal_book.csv, checks it against expected/deal_book.csv, and prints PASS when they match row for row. Then double-click dashboard/dashboard.html; it reads the exported data and re-derives the same headline figures. The Tableau build guide is in bi/README.md.

<!-- Screenshots (capture into images/, then replace this comment with the image lines, alt text as a short descriptive sentence ending in a period):
     01-run.png        a full `python run.py` ending in PASS
     02-result.png     `python run.py show` with contributions by sector
     03-dashboard.png  the dashboard open in a browser -->

## License

MIT. Copyright (c) 2026 Kevin Yu (https://github.com/exekyute).
