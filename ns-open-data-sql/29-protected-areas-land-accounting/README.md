# 29: Protected-areas land accounting

Accounts for 743,084.11 hectares of protected land across 1,161 published
records, 13.93 percent of Nova Scotia's land area. Wilderness areas hold 71.18
percent of it, and 11 records cover half the total, so the protected estate is a
handful of very large parcels plus a long tail of small ones.

## The data

Nova Scotia Open Data: **NS Protected Areas System** (`ticv-5du5`). Source,
licence, and pull date in SOURCE.md. (Catalog idea #44.)

## What it computes

Hectares and record counts by designation type, by responsible authority, by
land owner, and by protection status, each with its share of the provincial
protected total, plus a concentration curve that ranks records largest first and
carries a running hectare total. This is a geometry-bearing layer read tabularly
only: `the_geom` is excluded at the pull, no spatial extension is loaded, and
area comes from the province's published `ha_gis` field. Hectares are rounded
once at the record level, which is why five independent re-summations in the
`totals_tie` section all read 743,084.11 exactly. All logic lives in `sql/`;
`run.py` holds none of it.

One thing the data will not support: `stat_date`, the layer's designation year,
is empty in all 1,161 rows of the current publication, so there is no time
series to draw and this build does not pretend otherwise. spec.md sets out what
that costs and what the pipeline does instead.

## Testing

DuckDB is the only dependency:

    pip install duckdb

From this folder:

    python run.py            # runs the SQL end to end, then verifies
    python run.py verify     # re-runs the golden diff only
    python run.py show       # prints hectares by designation

`python run.py` writes out/protected_areas.csv, checks it against
expected/protected_areas.csv, and prints PASS when they match row for row. The
Power BI build guide is in bi/README.md.

<!-- Screenshots (capture into images/, then replace this comment with the image lines, alt text as a short descriptive sentence ending in a period):
     01-run.png     a full `python run.py` ending in PASS
     02-result.png  `python run.py show` with hectares by designation -->

## License

MIT. Copyright (c) 2026 Kevin Yu (https://github.com/exekyute).
