# Spec

## Purpose

Take a pinned snapshot of Halifax traffic collisions and produce two deterministic result tables plus a frozen BI mart that answer two things: how collision counts and each contributing factor's share move year over year, and when in the day and the year collisions cluster.

## Inputs

Dataset: Traffic Collisions (`HRM::traffic-collisions`, item `e0293fd4721e41d7be4d7386c3c59c16`), pulled to `data/raw/hrm_traffic-collisions_2026-07-09.csv`. See SOURCE.md.

Columns used: `COLLISION_SK`, `Accident Date and Time`, `Latitude WGS84`, `Longitude WGS84`, `Road Location`, `Intersecting Road Location`, `Collision Configuration`, `Non Fatal Injury`, `Fatal Injury`, `Pedestrian Collision`, `Bicycle Collision`, `Aggressive Driving`, `Distracted Driving`, `Impaired Driving`, `Intersection Collision`, `Light Condition`, `Weather Condition`.

## Load (00_schema.sql, 01_load.sql)

The raw landing table declares every used column as VARCHAR. The load reads the snapshot with `all_varchar = true` so type auto-detection is off, quoting each friendly CSV header and aliasing it to a clean raw column name. All casting happens in the transform, so a re-run can never drift on inferred types.

## Cleaning and validation rules (02_transform.sql)

1. Parse `Accident Date and Time` with the format `%-m/%-d/%Y %-I:%M:%S %p` into a local timestamp. The CSV renders the timestamp in local Halifax wall-clock time, so no timezone conversion is applied.
2. Cast latitude and longitude to doubles, and `COLLISION_SK` to a big integer.
3. Turn each factor field into a clean 0/1 integer: the driving and mode flags on `= 'Y'`, the injury flags on a value of `Yes` (they arrive as `Yes` or blank).
4. Derive `accident_date` (date), `year`, `month`, `hour` (0 to 23), and `weekday` (`isodow`, 1 = Monday to 7 = Sunday) from the parsed timestamp.
5. Drop any row with no parseable timestamp or a blank latitude or longitude. In this snapshot that removes 37 rows with an empty datetime (0.08 percent), leaving 46,248 of 46,285. Every downstream count then works on a complete, typed record.

The cleaned table is one row per collision and is both the analysis source and the mart source.

## Analysis logic (03_analysis.sql)

**collisions_by_year** (one row per year). Groups the clean rows by year and, since each factor column is a 0/1 integer, computes a count as `SUM(flag)` and a share as `round(100.0 * SUM(flag) / count(*), 1)`. Keeps both the raw counts (pedestrian, bicycle, impaired, distracted, intersection, fatal) and their percents. The counts are the ground truth the dashboard re-derives its headline from; the percents are what the Power BI cards and the trend read.

**collisions_month_hour** (one row per hour of day, 0 to 23). A month-by-hour count matrix: twelve columns `m01` to `m12`, each cell the collision count for that hour and month, built with conditional sums. This is the calendar heatmap the Tableau and browser views both draw.

**headline** (two lines). Uses the literal pull-date constant `DATE '2026-07-09'`. The latest full year is `year(pull_date) - 1 = 2025`, since the pull year is only partway complete. Reports the 2025 collision total and the pedestrian-involved count as two ready-to-print lines. `run.py` prints these; it does not compute them.

## Outputs (99_export.sql)

- `out/collisions_by_year.csv` (golden, 9 rows) and `expected/collisions_by_year.csv`.
- `out/collisions_month_hour.csv` (golden, 24 rows) and `expected/collisions_month_hour.csv`.
- `out/mart_collisions.csv` (46,248 rows), copied by `run.py` to `bi/exports/mart_collisions.csv`. One wide, denormalized row per collision for Tableau and Power BI. The factor flags keep their source-style uppercase names so the Power BI DAX binds to them verbatim.
- `out/meta.csv`, the pull-date constant and the latest full year, read only by the dashboard so its headline year and the SQL agree by construction.

Row order is fixed: the per-year table by `year`, the matrix by `hour`, the mart by `collision_id`. That makes each file byte-for-byte reproducible against expected/.

## Numbers that must agree across the three faces

With the year set to 2025:

- Collisions: **5,734**.
- Pedestrian-involved collisions: **169** (2.9 percent of the year).

These read identically in the SQL golden (`expected/collisions_by_year.csv`, the 2025 row), the Tableau density map filtered to 2025, and the Power BI cards with the year slicer on 2025.

## Edge cases

- **Missing timestamp:** 37 rows have a blank datetime and are dropped in cleaning before any date arithmetic runs.
- **Partial current year:** 2026 is incomplete on the pull date. The headline pins to 2025 through the literal pull-date constant; the 2026 rows remain in the mart and the per-year table as the most recent, partial year.
- **Coordinates:** every row in this snapshot carries a latitude and longitude, so none drop for missing coordinates; the rule still guards the map views if a future snapshot has blanks.
- **Blank factor fields:** a blank flag is read as 0 (not that factor), so counts and shares never inflate on empty cells.

## Determinism

The snapshot is pinned and committed. Every result query ends in an `ORDER BY`, percents are rounded to one decimal, and any date arithmetic uses the literal pull-date constant, never `CURRENT_DATE`. The golden files were built from a first verified run; `run.py` re-runs the pipeline and diffs the fresh output against them, printing PASS only on an exact row-for-row match.
