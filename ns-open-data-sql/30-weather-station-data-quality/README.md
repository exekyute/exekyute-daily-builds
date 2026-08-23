# 30: Weather-station data-quality auditor

Audits 234,835 readings from all 46 Nova Scotia road weather stations over fourteen days, 2024-01-01 to 2024-01-14 UTC. The network covered 233,712 of 238,896 expected reporting slots, 97.83 percent, and 21 of the 46 stations fail at least one audit rule. The worst is RNSKM at 59.78 percent, silent for two whole days.

## The data

Nova Scotia Open Data: **NS Weather Station Data** (`kafq-j9u4`). Source, licence, pull date, and the exact narrowing query in SOURCE.md. (Catalog idea #24.)

## What it computes

Each station's reporting cadence is measured rather than assumed: the audit takes the modal interval between that station's consecutive readings and uses it as the denominator, so 43 stations are scored against 240 seconds, two against 120, and one against 600. Completeness is then cadence-slot coverage per station per day, which keeps uptime bounded at 100 percent even when a station bursts above its own rate, and carries the excess in its own column instead of hiding it. On top of that: 36 reporting gaps where a station went quiet for more than three times its cadence, 12 frozen air-temperature runs found with a gap-and-island pattern, 6 out-of-range values, and 41,711 blank measure values including two stations that reported air temperature and humidity zero times in fourteen days while their wind channel kept working. The window is fourteen whole UTC days, fixed as literal date constants; all logic lives in `sql/`, and `run.py` holds none of it.

## Testing

DuckDB is the only dependency:

    pip install duckdb

From this folder:

    python run.py            # runs the SQL end to end, then verifies
    python run.py verify     # re-runs the golden diff only
    python run.py show       # prints the station quality scorecard

`python run.py` writes out/station_quality.csv, checks it against expected/station_quality.csv, and prints PASS when they match row for row. The Tableau and Power BI build guides are in bi/README.md.

<!-- Screenshots (capture into images/, then replace this comment with the image lines, alt text as a short descriptive sentence ending in a period):
     01-run.png     a full `python run.py` ending in PASS
     02-result.png  `python run.py show` with the station scorecard -->

## License

MIT. Copyright (c) 2026 Kevin Yu (https://github.com/exekyute).
