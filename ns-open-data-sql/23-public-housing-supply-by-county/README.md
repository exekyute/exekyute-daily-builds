# 23: Public-housing supply by county

Stacks the province's two public-housing unit lists into one county view: 11,251 units across 3,289 property records, spread over all eighteen Nova Scotia counties. Halifax holds 3,763 of those units (33.45 percent) and Cape Breton 2,670 (23.73 percent), so the two largest counties carry 57.18 percent of the provincial supply between them.

## The data

- **Public Housing Units - Nova Scotia Families** (`nxzm-xxps`)
- **Public Housing Units - Nova Scotia Seniors** (`2d4m-9e6x`)

Source, licence, and pull date in SOURCE.md. (Catalog idea #37.)

## What it computes

The two files stack into one long table with a `program_type` column, the two differently named unit columns (`number_of_units` and `residential_units`) folded into one `units` column, and county spellings run through a declared mapping constant. Units and property counts come out by county, by program type, and by both together, each with its share of the provincial unit total. The county grid is an explicit cross join of the counties present in either source against both program types, so a county carried by one file and not the other lands as a zero instead of going missing. A reconciliation block totals each source on its own and proves the two add to the combined total, and a row-accounting block reports every exclusion class at its actual count. All logic lives in `sql/`; `run.py` holds none of it.

## Testing

DuckDB is the only dependency:

    pip install duckdb

From this folder:

    python run.py            # runs the SQL end to end, then verifies
    python run.py verify     # re-runs the golden diff only
    python run.py show       # prints units by county and program type

`python run.py` writes out/housing_supply.csv, checks it against expected/housing_supply.csv, and prints PASS when they match row for row. The Tableau build guide is in bi/README.md.

<!-- Screenshots (capture into images/, then replace this comment with the image lines, alt text as a short descriptive sentence ending in a period):
     01-run.png     a full `python run.py` ending in PASS
     02-result.png  `python run.py show` with units by county -->

## License

MIT. Copyright (c) 2026 Kevin Yu (https://github.com/exekyute).
