# Spec

## Purpose

Take a pinned snapshot of Halifax building permits, one row per permit with its
coordinates attached, and produce deterministic tables that answer three things:
how permit activity and declared construction value have moved by year and work
type, where net new residential units are landing as a per-district running total,
and what the total declared value was in the latest full issue year.

## Inputs

Snapshot: `data/raw/hrm_pplc-building-permits_2026-07-09.csv`, 18,316 rows. It is
the base PPL&C Building Permits attribute table LEFT JOINed to PPL&C Building
Permits Geolocated on permit number, so latitude and longitude ride along on the
18,224 permits that geolocated. See SOURCE.md for both endpoints and the join.

Columns used from the snapshot: `source_object_id`, `permit_number`,
`date_of_permit_issuance`, `estimated_project_value`, `work_type`,
`primary_work_scope`, `permit_status`, `community`, `district`, `net_new_units`,
`number_of_storeys`, `latitude`, `longitude`.

## Pipeline

Five SQL files run in order by `run.py`, which holds no analytical logic.

### 00_schema.sql

Drops every table so a re-run starts clean, then declares `permits_raw` with all
columns typed `VARCHAR`. The committed snapshot is plain text; typing happens next.

### 01_load.sql

Reads the committed snapshot into `permits_raw` with `read_csv`, columns pinned to
`VARCHAR` so the load never depends on type auto-detection. The path is relative to
the project folder, so `run.py` launches DuckDB from here.

### 02_transform.sql

Builds `permit_mart`, one clean typed row per source permit record (18,316 rows):

- `source_object_id` cast to `BIGINT`, the stable key that fixes export row order.
- `issue_year` and `issue_month` from `EXTRACT(... FROM TRY_CAST(date AS DATE))`.
  A blank issuance date yields null year and month.
- `project_value` cast to `DOUBLE` and rounded to 2 decimals. Blank stays null.
- `net_new_units`, `storeys` cast to `INTEGER`; `lat`, `lon` cast to `DOUBLE`.
- text fields trimmed.

It also builds `params`, a one-row table holding the pinned `pull_date`
(`DATE '2026-07-09'`) and `latest_full_year`. The latest full issue year is
`year(pull_date) - 1 = 2025`: the snapshot runs into the pull year (2026), which is
only a partial year, so the most recent complete calendar year is 2025.

### 03_analysis.sql

Every rollup reads `permit_mart` and restricts to `issue_year IS NOT NULL`, because
a permit with no issuance date cannot be placed in a year. Those 2,470 permits still
live in `permit_mart` and in the exported per-permit mart; they are only left out of
the year-based rollups.

**permits_by_year_worktype** (golden). One row per issue year and work type:
`permit_count` = `COUNT(*)`, `total_project_value` =
`ROUND(SUM(COALESCE(project_value, 0)), 2)`, `total_net_new_units` =
`SUM(net_new_units)`. A missing declared value counts as zero in the money sum;
`net_new_units` is never null in the snapshot and can be negative.

**district_units_running_total** (golden). First sum `net_new_units` per district
and year, then carry a cumulative sum across years within each district:

    SUM(net_new_units) OVER (
      PARTITION BY district ORDER BY issue_year
      ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
    )

This is exactly the running-total table calculation the Tableau guide rebuilds
(Compute Using `issue_year`, partition by `district`).

**permits_by_community** (dashboard feed, not a golden). Declared value and units
by community over all issued permits, ranked by value, so the browser dashboard can
rank communities. A blank community becomes `(Unspecified)`. The money total across
communities equals the money total across year-and-work-type rows, which lets the
dashboard reconcile to the golden.

**headline** (two rows). Ready-to-print lines. `run.py` prints them; it does not
compute them. Line one is the numbers-match anchor carried into both BI guides: the
total declared project value for the latest full issue year.

### 99_export.sql

Writes the two goldens, the community dashboard feed, and the frozen per-permit
`mart_permits.csv`. Every query ends in an `ORDER BY`, so each file is
byte-for-byte reproducible. The mart projects the thirteen dashboard columns and
orders by `source_object_id`.

## Outputs

- `out/permits_by_year_worktype.csv` (golden, 19 rows).
- `out/district_units_running_total.csv` (golden, 104 rows).
- `out/permits_by_community.csv` (dashboard feed).
- `out/mart_permits.csv` (frozen per-permit mart, 18,316 rows), copied to
  `bi/exports/mart_permits.csv` and serialized into `dashboard/data.js` by `run.py`.

`run.py verify` diffs each file in `expected/` against its `out/` twin row for row
and prints PASS on an exact match. The mart is a generated export, not a golden;
its determinism comes from the `ORDER BY source_object_id`.

## Headline figures (issue year 2025, the latest full year)

- Total declared project value: **$3,856,416,602.50**.
- Permits issued: **3,100**.
- Net new residential units: **11,793**.

Across all issued permits 2020 to 2026: 15,846 permits, $18,683,679,885.12
declared, 71,257 net new units.

## Edge cases

- **No issuance date:** 2,470 permits carry no `Date_of_Permit_Issuance`, so their
  `issue_year` is null and they drop out of every year-based rollup while remaining
  in the per-permit mart.
- **No coordinates:** 92 permits have no geolocated match and carry blank
  `lat`/`lon`. They keep all attributes and simply do not appear on a map.
- **Duplicate permit numbers:** `permit_number` is not unique (16,030 distinct
  across 18,316 records); the observed duplicates are exact repeats. The mart keeps
  the base record grain and orders by `source_object_id`, so the output is stable
  regardless.
- **Missing declared value:** 119 permits have no `estimated_project_value`. It is
  treated as zero in the money sums and stays blank in the per-permit mart.
- **Negative net new units:** some permits reduce the residential unit count (an
  addition that merges units), so `net_new_units` and its running total can fall.
- **Partial final year:** 2026 is a partial year of data. It appears in the rollups
  and the dashboard, but the headline reports 2025, the latest full year.

## Determinism

The snapshot is pinned and committed. Every result query ends in an `ORDER BY`, all
date logic reads the literal `pull_date` constant rather than `CURRENT_DATE`, and
money rounds to the cent. The same input always produces byte-identical output;
`run.py` re-runs the pipeline and diffs the fresh output against `expected/`.
