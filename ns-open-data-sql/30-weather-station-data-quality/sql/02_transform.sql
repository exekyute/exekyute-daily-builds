-- 02_transform.sql
-- Type the snapshot, count every exclusion class, lay out the station-day
-- calendar, and derive each station's reporting cadence from the data.
-- Nothing here assumes a cadence: the interval is measured, not declared.

-- ---------------------------------------------------------------------------
-- 1. Typed readings
-- ---------------------------------------------------------------------------
-- TRY_CAST rather than CAST on purpose. A row that will not parse is not
-- dropped quietly; it lands in load_audit below and is reported in the golden
-- output. Timestamps are UTC, so reading_date is a UTC day. Converting to
-- Atlantic local time would shift readings across the window boundary and
-- leave the first and last audited days partial, so the audit stays on UTC.
CREATE OR REPLACE TABLE readings AS
SELECT
    r.site_id,
    TRY_CAST(r.datetimeutc AS TIMESTAMP)                     AS ts,
    CAST(TRY_CAST(r.datetimeutc AS TIMESTAMP) AS DATE)       AS reading_date,
    TRY_CAST(r.air_temperature AS DOUBLE)                    AS air_temperature,
    TRY_CAST(r.relative_humidity AS DOUBLE)                  AS relative_humidity,
    TRY_CAST(r.avg_wind_speed AS DOUBLE)                     AS avg_wind_speed
FROM raw_readings r, audit_constants c
WHERE TRY_CAST(r.datetimeutc AS TIMESTAMP) IS NOT NULL
  AND TRY_CAST(r.datetimeutc AS TIMESTAMP) >= CAST(c.window_start AS TIMESTAMP)
  AND TRY_CAST(r.datetimeutc AS TIMESTAMP) <  CAST(c.window_end_excl AS TIMESTAMP);

-- ---------------------------------------------------------------------------
-- 2. Exclusion ledger
-- ---------------------------------------------------------------------------
-- snapshot_rows must equal readings_kept plus every excluded class. The
-- coverage_tie section of the golden output re-proves that from the far end.
CREATE OR REPLACE TABLE load_audit AS
SELECT
    (SELECT count(*) FROM raw_readings) AS snapshot_rows,
    (SELECT count(*) FROM raw_readings
       WHERE TRY_CAST(datetimeutc AS TIMESTAMP) IS NULL) AS rows_unparseable_timestamp,
    (SELECT count(*) FROM raw_readings r, audit_constants c
       WHERE TRY_CAST(r.datetimeutc AS TIMESTAMP) IS NOT NULL
         AND (TRY_CAST(r.datetimeutc AS TIMESTAMP) <  CAST(c.window_start AS TIMESTAMP)
           OR TRY_CAST(r.datetimeutc AS TIMESTAMP) >= CAST(c.window_end_excl AS TIMESTAMP))
    ) AS rows_outside_window,
    (SELECT count(*) FROM readings) AS readings_kept,
    (SELECT count(*) FROM raw_readings
       WHERE air_temperature IS NOT NULL
         AND TRY_CAST(air_temperature AS DOUBLE) IS NULL) AS unparseable_air_temperature,
    (SELECT count(*) FROM raw_readings
       WHERE relative_humidity IS NOT NULL
         AND TRY_CAST(relative_humidity AS DOUBLE) IS NULL) AS unparseable_relative_humidity,
    (SELECT count(*) FROM raw_readings
       WHERE avg_wind_speed IS NOT NULL
         AND TRY_CAST(avg_wind_speed AS DOUBLE) IS NULL) AS unparseable_avg_wind_speed;

-- ---------------------------------------------------------------------------
-- 3. Station-day calendar
-- ---------------------------------------------------------------------------
-- Dates come from the declared constants, not from the data, so a station that
-- went silent for a whole day still gets a row and still scores zero. Day
-- length is the overlap of the calendar day with the audit window, in seconds,
-- so a leap day or a part-day window boundary cannot break the denominator.
CREATE OR REPLACE TABLE window_calendar AS
SELECT CAST(c.window_start + CAST(i AS INTEGER) AS DATE) AS reading_date
FROM audit_constants c,
     range(0, (SELECT date_diff('day', window_start, window_end_excl)
               FROM audit_constants)) AS t(i);

CREATE OR REPLACE TABLE stations AS
SELECT DISTINCT site_id FROM readings;

CREATE OR REPLACE TABLE station_days AS
SELECT
    s.site_id,
    w.reading_date,
    GREATEST(CAST(w.reading_date AS TIMESTAMP),
             CAST(c.window_start AS TIMESTAMP))               AS day_start,
    LEAST(CAST(w.reading_date + 1 AS TIMESTAMP),
          CAST(c.window_end_excl AS TIMESTAMP))               AS day_end,
    date_diff('second',
        GREATEST(CAST(w.reading_date AS TIMESTAMP),
                 CAST(c.window_start AS TIMESTAMP)),
        LEAST(CAST(w.reading_date + 1 AS TIMESTAMP),
              CAST(c.window_end_excl AS TIMESTAMP)))          AS day_seconds
FROM stations s
CROSS JOIN window_calendar w
CROSS JOIN audit_constants c;

-- ---------------------------------------------------------------------------
-- 4. Intervals between consecutive readings
-- ---------------------------------------------------------------------------
CREATE OR REPLACE TABLE reading_intervals AS
SELECT
    site_id,
    ts AS ts_to,
    lag(ts) OVER (PARTITION BY site_id ORDER BY ts) AS ts_from,
    date_diff('second', lag(ts) OVER (PARTITION BY site_id ORDER BY ts), ts)
        AS interval_seconds
FROM readings;

-- ---------------------------------------------------------------------------
-- 5. Derived cadence, one value per station
-- ---------------------------------------------------------------------------
-- The window-wide modal interval is the fallback for a station too sparse to
-- establish its own mode (fewer than min_intervals_for_mode measured
-- intervals). Ties inside a station break on the shorter interval, so the
-- expectation never lands below what the station demonstrably sustains.
CREATE OR REPLACE TABLE window_modal_interval AS
SELECT interval_seconds
FROM reading_intervals
WHERE interval_seconds IS NOT NULL AND interval_seconds > 0
GROUP BY interval_seconds
ORDER BY count(*) DESC, interval_seconds ASC
LIMIT 1;

CREATE OR REPLACE TABLE station_cadence AS
WITH counted AS (
    SELECT site_id, interval_seconds, count(*) AS n
    FROM reading_intervals
    WHERE interval_seconds IS NOT NULL AND interval_seconds > 0
    GROUP BY site_id, interval_seconds
),
ranked AS (
    SELECT
        site_id, interval_seconds, n,
        sum(n) OVER (PARTITION BY site_id) AS measured_intervals,
        row_number() OVER (
            PARTITION BY site_id
            ORDER BY n DESC, interval_seconds ASC
        ) AS rk
    FROM counted
)
SELECT
    s.site_id,
    CASE WHEN COALESCE(rk.measured_intervals, 0) >= c.min_intervals_for_mode
         THEN rk.interval_seconds
         ELSE (SELECT interval_seconds FROM window_modal_interval)
    END                                                   AS cadence_seconds,
    COALESCE(rk.measured_intervals, 0)                    AS measured_intervals,
    COALESCE(rk.n, 0)                                     AS modal_interval_count,
    CASE WHEN COALESCE(rk.measured_intervals, 0) >= c.min_intervals_for_mode
         THEN 'derived' ELSE 'window fallback'
    END                                                   AS cadence_source
FROM stations s
CROSS JOIN audit_constants c
LEFT JOIN ranked rk ON rk.site_id = s.site_id AND rk.rk = 1;
