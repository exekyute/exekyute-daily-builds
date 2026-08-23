# 28: Surgical wait-time SLA tracker

Measures 2,853 published facility-procedure-quarter lines from Nova Scotia's
surgical wait-time table against a stated 182-day target on the published
surgery median: 276 of the 2,729 lines that carry a median sit above it, 10.11
percent. The longest published median in the window is 560 days, at the IWK for
adult dental extractions and restorations in 2024 Q2, where the 90th percentile
reached 1,301 days.

## The data

Nova Scotia Open Data: **Surgical Wait Times** (`wu5w-qxki`). Source, licence,
and pull date in SOURCE.md. (Catalog idea #11.)

## What it computes

Breach counts and rates for every facility and every procedure against two
separate named targets, 182 days on the surgery median and 90 days on the
consultation median. Each measure pair also gets a tail-gap column, the 90th
percentile minus the median, which is how far past the middle the slow tenth
of that queue ran. The source
publishes the medians and 90th percentiles itself, so this build consumes them
and never recomputes a percentile. Rolling-window rows and the province's own
`Total` / `Provincial` rollup rows are held out of the facility grain so nothing
double counts, and every held-out class is counted in the output rather than
dropped quietly; the rollup rows come back as the published provincial reference
series behind the quarter-over-quarter trend. All logic lives in `sql/`; `run.py`
holds none of it.

## Testing

DuckDB is the only dependency:

    pip install duckdb

From this folder:

    python run.py            # runs the SQL end to end, then verifies
    python run.py verify     # re-runs the golden diff only
    python run.py show       # prints the breach summary

`python run.py` writes out/wait_time_sla.csv, checks it against
expected/wait_time_sla.csv, and prints PASS when they match row for row. The
Tableau and Power BI build guides are in bi/README.md.

<!-- Screenshots (capture into images/, then replace this comment with the image lines, alt text as a short descriptive sentence ending in a period):
     01-run.png     a full `python run.py` ending in PASS
     02-result.png  `python run.py show` with the breach summary -->

## License

MIT. Copyright (c) 2026 Kevin Yu (https://github.com/exekyute).
