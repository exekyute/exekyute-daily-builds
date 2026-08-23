# 22: Fish landings value by port

Ranks 271 Nova Scotia landing ports by the value of fish bought off the wharf between 2017 and 2024. Digby leads at $533,530,107.96 with Lower Woods Harbour only $3,375,514.28 behind, the top 10 ports hold 40.99 percent of the $8,716,996,237.83 that port rows account for, and the province's own county totals run $2,206,197,636.95 higher because port figures are suppressed wherever too few buyers report.

## The data

Nova Scotia Open Data: **Fish Buyer Purchase Data by Port** (`j9j2-cpn4`). Source, licence, and pull date in SOURCE.md. (Catalog idea #39.)

## What it computes

Dollars and kilograms by port, by county, and by year, plus price per kg guarded so it divides only where kilograms are reported. The top-ports Pareto carries each port's share and a running cumulative share, and the year section carries the move in landed value against the previous year. Most of the rules exist because of how the source is put together. It holds two grains in one table, so the 144 `Total for <County> County` aggregate rows stay out of every sum and go instead to a coverage section that sets each county's published figure against the sum of its ports. Port names repeat across counties, so port identity is the county and the port together. And in 2019 and 2020 alone the province writes out wharf names it omits in the other six years, so a wharf is rolled back into its port before anything is ranked. Blank kilograms and blank dollars are suppressed per measure and never read as zero, every exclusion class is counted in the output, and a totals_tie section re-sums the port, county, and year breakdowns so dollars and kilograms each tie to the cent. All logic lives in `sql/`; `run.py` holds none of it.

## Testing

DuckDB is the only dependency:

    pip install duckdb

From this folder:

    python run.py            # runs the SQL end to end, then verifies
    python run.py verify     # re-runs the golden diff only
    python run.py show       # prints the top ports and landed value

`python run.py` writes out/fish_landings.csv, checks it against expected/fish_landings.csv, and prints PASS when they match row for row. The Tableau and Power BI build guides are in bi/README.md.

<!-- Screenshots (capture into images/, then replace this comment with the image lines, alt text as a short descriptive sentence ending in a period):
     01-run.png     a full `python run.py` ending in PASS
     02-result.png  `python run.py show` with the top ports -->

## License

MIT. Copyright (c) 2026 Kevin Yu (https://github.com/exekyute).
