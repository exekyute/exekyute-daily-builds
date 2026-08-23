-- 03_analysis.sql
-- The audit itself. Every threshold comes from audit_constants; every
-- expectation comes from the station's own measured cadence.

-- ---------------------------------------------------------------------------
-- 1. Completeness per station-day
-- ---------------------------------------------------------------------------
-- readings_expected is the day's duration divided by the station's measured
-- cadence, rounded up to a whole reading. Completeness is then measured as
-- cadence-slot coverage rather than a raw count ratio: a slot is one cadence
-- period inside the day, and a slot counts as covered when at least one
-- reading falls in it. That keeps uptime bounded at 100 percent by
-- construction while a station that bursts above its own cadence still shows
-- its full raw count in readings_actual and the excess in surplus_readings.
CREATE OR REPLACE TABLE station_day_coverage AS
WITH slots AS (
    SELECT
        d.site_id,
        d.reading_date,
        CAST(floor(date_diff('second', d.day_start, r.ts) / cad.cadence_seconds)
             AS BIGINT) AS slot_index
    FROM station_days d
    JOIN station_cadence cad ON cad.site_id = d.site_id
    JOIN readings r
      ON r.site_id = d.site_id
     AND r.ts >= d.day_start
     AND r.ts <  d.day_end
),
per_day AS (
    SELECT site_id, reading_date,
           count(*)                   AS readings_actual,
           count(DISTINCT slot_index) AS slots_covered
    FROM slots
    GROUP BY site_id, reading_date
)
SELECT
    d.site_id,
    d.reading_date,
    cad.cadence_seconds,
    d.day_seconds,
    CAST(ceil(CAST(d.day_seconds AS DOUBLE) / cad.cadence_seconds) AS BIGINT)
                                            AS readings_expected,
    COALESCE(p.readings_actual, 0)          AS readings_actual,
    COALESCE(p.slots_covered, 0)            AS slots_covered,
    COALESCE(p.readings_actual, 0) - COALESCE(p.slots_covered, 0)
                                            AS surplus_readings
FROM station_days d
JOIN station_cadence cad ON cad.site_id = d.site_id
LEFT JOIN per_day p ON p.site_id = d.site_id AND p.reading_date = d.reading_date;

-- ---------------------------------------------------------------------------
-- 2. Gaps
-- ---------------------------------------------------------------------------
-- A gap is an interval longer than gap_k times the station's own cadence. It
-- is dated by the reading that starts it, because that is the moment
-- reporting stopped.
CREATE OR REPLACE TABLE gap_events AS
SELECT
    i.site_id,
    CAST(i.ts_from AS DATE) AS reading_date,
    i.ts_from,
    i.ts_to,
    i.interval_seconds,
    cad.cadence_seconds,
    CAST(round(CAST(i.interval_seconds AS DOUBLE) / cad.cadence_seconds, 1)
         AS DECIMAL(12,1)) AS cadence_multiple
FROM reading_intervals i
JOIN station_cadence cad ON cad.site_id = i.site_id
CROSS JOIN audit_constants c
WHERE i.interval_seconds IS NOT NULL
  AND i.interval_seconds > c.gap_k * cad.cadence_seconds;

-- ---------------------------------------------------------------------------
-- 3. Frozen air-temperature runs
-- ---------------------------------------------------------------------------
-- Gap-and-island over the reading stream: subtracting a per-value row number
-- from a per-station row number gives a constant group id for each contiguous
-- run of the same value. A missing air temperature sits in its own value
-- partition, so a dropout breaks a run instead of bridging it. Runs of NULL
-- are discarded here and counted as missing values in step 5 instead.
CREATE OR REPLACE TABLE frozen_runs AS
WITH ordered AS (
    SELECT
        site_id, ts, air_temperature,
        row_number() OVER (PARTITION BY site_id ORDER BY ts) AS rn
    FROM readings
),
islands AS (
    SELECT
        site_id, ts, air_temperature, rn,
        rn - row_number() OVER (PARTITION BY site_id, air_temperature ORDER BY ts)
            AS run_group
    FROM ordered
),
runs AS (
    SELECT
        site_id,
        air_temperature AS frozen_value,
        run_group,
        count(*)   AS run_length,
        min(ts)    AS ts_from,
        max(ts)    AS ts_to
    FROM islands
    WHERE air_temperature IS NOT NULL
    GROUP BY site_id, air_temperature, run_group
)
SELECT
    r.site_id,
    CAST(r.ts_from AS DATE) AS reading_date,
    r.frozen_value,
    r.run_length,
    r.ts_from,
    r.ts_to,
    date_diff('second', r.ts_from, r.ts_to) AS run_seconds
FROM runs r
CROSS JOIN audit_constants c
WHERE r.run_length >= c.frozen_run_min_readings;

-- ---------------------------------------------------------------------------
-- 4. Out-of-range measure values
-- ---------------------------------------------------------------------------
-- One row per offending measure value, not per reading, so a reading that
-- fails two bounds is counted twice. A missing value is never out of range;
-- it is counted as missing in step 5.
CREATE OR REPLACE TABLE out_of_range_events AS
SELECT r.site_id, r.reading_date, r.ts, 'air_temperature' AS measure,
       r.air_temperature AS value, c.air_temp_min_c AS bound_min, c.air_temp_max_c AS bound_max
FROM readings r CROSS JOIN audit_constants c
WHERE r.air_temperature IS NOT NULL
  AND (r.air_temperature < c.air_temp_min_c OR r.air_temperature > c.air_temp_max_c)
UNION ALL
SELECT r.site_id, r.reading_date, r.ts, 'relative_humidity',
       r.relative_humidity, c.rh_min_pct, c.rh_max_pct
FROM readings r CROSS JOIN audit_constants c
WHERE r.relative_humidity IS NOT NULL
  AND (r.relative_humidity < c.rh_min_pct OR r.relative_humidity > c.rh_max_pct)
UNION ALL
SELECT r.site_id, r.reading_date, r.ts, 'avg_wind_speed',
       r.avg_wind_speed, c.wind_min, c.wind_max
FROM readings r CROSS JOIN audit_constants c
WHERE r.avg_wind_speed IS NOT NULL
  AND (r.avg_wind_speed < c.wind_min OR r.avg_wind_speed > c.wind_max);

-- ---------------------------------------------------------------------------
-- 5. Missing measure values per station-day
-- ---------------------------------------------------------------------------
CREATE OR REPLACE TABLE missing_by_day AS
SELECT
    site_id,
    reading_date,
    sum(CASE WHEN air_temperature   IS NULL THEN 1 ELSE 0 END) AS missing_air_temperature,
    sum(CASE WHEN relative_humidity IS NULL THEN 1 ELSE 0 END) AS missing_relative_humidity,
    sum(CASE WHEN avg_wind_speed    IS NULL THEN 1 ELSE 0 END) AS missing_avg_wind_speed
FROM readings
GROUP BY site_id, reading_date;

-- ---------------------------------------------------------------------------
-- 6. The station-day grain, which is also the BI mart grain
-- ---------------------------------------------------------------------------
CREATE OR REPLACE TABLE station_day_quality AS
SELECT
    cov.site_id,
    cov.reading_date,
    cov.cadence_seconds,
    cov.readings_actual,
    cov.readings_expected,
    cov.slots_covered,
    cov.surplus_readings,
    CAST(round(100.0 * cov.slots_covered / cov.readings_expected, 2) AS DECIMAL(9,2))
                                                       AS uptime_pct,
    COALESCE(g.gap_count, 0)                           AS gap_count,
    COALESCE(f.frozen_run_count, 0)                    AS frozen_run_count,
    COALESCE(o.out_of_range_count, 0)                  AS out_of_range_count,
    COALESCE(m.missing_air_temperature, 0)             AS missing_air_temperature,
    COALESCE(m.missing_relative_humidity, 0)           AS missing_relative_humidity,
    COALESCE(m.missing_avg_wind_speed, 0)              AS missing_avg_wind_speed,
    COALESCE(m.missing_air_temperature, 0)
      + COALESCE(m.missing_relative_humidity, 0)
      + COALESCE(m.missing_avg_wind_speed, 0)          AS missing_values
FROM station_day_coverage cov
LEFT JOIN (SELECT site_id, reading_date, count(*) AS gap_count
           FROM gap_events GROUP BY 1, 2) g
       ON g.site_id = cov.site_id AND g.reading_date = cov.reading_date
LEFT JOIN (SELECT site_id, reading_date, count(*) AS frozen_run_count
           FROM frozen_runs GROUP BY 1, 2) f
       ON f.site_id = cov.site_id AND f.reading_date = cov.reading_date
LEFT JOIN (SELECT site_id, reading_date, count(*) AS out_of_range_count
           FROM out_of_range_events GROUP BY 1, 2) o
       ON o.site_id = cov.site_id AND o.reading_date = cov.reading_date
LEFT JOIN missing_by_day m
       ON m.site_id = cov.site_id AND m.reading_date = cov.reading_date;

-- ---------------------------------------------------------------------------
-- 7. Station scorecard over the whole window
-- ---------------------------------------------------------------------------
CREATE OR REPLACE TABLE station_scorecard AS
WITH agg AS (
    SELECT
        q.site_id,
        max(q.cadence_seconds)          AS cadence_seconds,
        sum(q.readings_actual)          AS readings_actual,
        sum(q.readings_expected)        AS readings_expected,
        sum(q.slots_covered)            AS slots_covered,
        sum(q.surplus_readings)         AS surplus_readings,
        sum(q.gap_count)                AS gap_count,
        sum(q.frozen_run_count)         AS frozen_run_count,
        sum(q.out_of_range_count)       AS out_of_range_count,
        sum(q.missing_air_temperature)  AS missing_air_temperature,
        sum(q.missing_relative_humidity) AS missing_relative_humidity,
        sum(q.missing_avg_wind_speed)   AS missing_avg_wind_speed,
        sum(q.missing_values)           AS missing_values,
        sum(CASE WHEN q.readings_actual = 0 THEN 1 ELSE 0 END) AS days_with_no_readings,
        sum(CASE WHEN q.uptime_pct < 100 THEN 1 ELSE 0 END)    AS days_below_full,
        count(*)                        AS days_in_window
    FROM station_day_quality q
    GROUP BY q.site_id
),
scored AS (
    SELECT
        a.*,
        CAST(round(100.0 * a.slots_covered / a.readings_expected, 2) AS DECIMAL(9,2))
            AS uptime_pct,
        list_filter([
            CASE WHEN 100.0 * a.slots_covered / a.readings_expected < c.uptime_flag_pct
                 THEN 'uptime below ' || CAST(CAST(c.uptime_flag_pct AS DECIMAL(9,2)) AS VARCHAR) || ' percent' END,
            CASE WHEN a.days_with_no_readings > 0 THEN 'silent days' END,
            CASE WHEN a.frozen_run_count > 0 THEN 'frozen air temperature run' END,
            CASE WHEN a.out_of_range_count > 0 THEN 'out-of-range values' END,
            CASE WHEN a.readings_actual > 0 AND a.missing_air_temperature = a.readings_actual
                 THEN 'air_temperature never reported' END,
            CASE WHEN a.readings_actual > 0 AND a.missing_relative_humidity = a.readings_actual
                 THEN 'relative_humidity never reported' END,
            CASE WHEN a.readings_actual > 0 AND a.missing_avg_wind_speed = a.readings_actual
                 THEN 'avg_wind_speed never reported' END
        ], x -> x IS NOT NULL) AS reasons
    FROM agg a CROSS JOIN audit_constants c
)
SELECT
    s.* EXCLUDE (reasons),
    CASE WHEN len(s.reasons) > 0 THEN 'flagged' ELSE 'ok' END AS station_flag,
    CASE WHEN len(s.reasons) > 0 THEN array_to_string(s.reasons, '; ') ELSE '' END
        AS station_flag_reasons
FROM scored s;

-- ---------------------------------------------------------------------------
-- 8. Completeness ranking, worst first
-- ---------------------------------------------------------------------------
-- Percentages tie constantly, so site_id is the tie-breaker and the rank is
-- reproducible regardless of scan order.
CREATE OR REPLACE TABLE completeness_ranking AS
SELECT
    row_number() OVER (ORDER BY uptime_pct ASC, site_id ASC) AS completeness_rank,
    s.*
FROM station_scorecard s;

-- ---------------------------------------------------------------------------
-- 9. The BI mart: one row per station per day, station scorecard carried along
-- ---------------------------------------------------------------------------
CREATE OR REPLACE TABLE mart_station_quality AS
SELECT
    q.site_id,
    q.reading_date,
    q.cadence_seconds,
    q.readings_actual,
    q.readings_expected,
    q.slots_covered,
    q.surplus_readings,
    q.uptime_pct,
    q.gap_count,
    q.frozen_run_count,
    q.out_of_range_count,
    q.missing_air_temperature,
    q.missing_relative_humidity,
    q.missing_avg_wind_speed,
    q.missing_values,
    r.completeness_rank        AS station_completeness_rank,
    r.uptime_pct               AS station_uptime_pct,
    r.readings_actual          AS station_readings_actual,
    r.readings_expected        AS station_readings_expected,
    r.gap_count                AS station_gap_count,
    r.frozen_run_count         AS station_frozen_run_count,
    r.out_of_range_count       AS station_out_of_range_count,
    r.missing_values           AS station_missing_values,
    r.days_with_no_readings    AS station_days_with_no_readings,
    r.station_flag,
    r.station_flag_reasons
FROM station_day_quality q
JOIN completeness_ranking r ON r.site_id = q.site_id;

-- ---------------------------------------------------------------------------
-- 10. The sectioned golden result
-- ---------------------------------------------------------------------------
-- One file, eleven sections, a fixed column set. Columns that mean nothing to
-- a section are left blank rather than reused for something else.
CREATE OR REPLACE TABLE station_quality AS

-- headline -------------------------------------------------------------------
SELECT
    1 AS section_order, 'headline' AS section, 1 AS rank,
    r.site_id, CAST(NULL AS DATE) AS reading_date,
    'worst_station_by_completeness' AS measure,
    'lowest slot coverage over the audited window' AS detail,
    r.cadence_seconds, CAST(NULL AS BIGINT) AS seconds,
    r.readings_actual, r.slots_covered, r.readings_expected, r.uptime_pct,
    CAST(NULL AS DECIMAL(9,2)) AS share_pct,
    r.gap_count, r.frozen_run_count, r.out_of_range_count, r.missing_values
FROM completeness_ranking r WHERE r.completeness_rank = 1

UNION ALL
SELECT 1, 'headline', 2, NULL, NULL, 'stations_flagged',
       'stations failing at least one audit rule',
       NULL, NULL, NULL, count(*), (SELECT count(*) FROM station_scorecard),
       NULL, NULL, NULL, NULL, NULL, NULL
FROM station_scorecard WHERE station_flag = 'flagged'

UNION ALL
SELECT 1, 'headline', 3, NULL, NULL, 'window_slot_coverage',
       'every station, every day, slots covered against slots expected',
       NULL, NULL,
       (SELECT sum(readings_actual)   FROM station_day_quality),
       (SELECT sum(slots_covered)     FROM station_day_quality),
       (SELECT sum(readings_expected) FROM station_day_quality),
       (SELECT CAST(round(100.0 * sum(slots_covered) / sum(readings_expected), 2)
                    AS DECIMAL(9,2)) FROM station_day_quality),
       NULL, NULL, NULL, NULL, NULL

-- constants ------------------------------------------------------------------
UNION ALL
SELECT 2, 'constants', v.rank, NULL, NULL, v.measure, v.detail,
       NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL
FROM audit_constants c,
LATERAL (VALUES
    (1,  'WINDOW_START',            CAST(c.window_start AS VARCHAR) || ' (inclusive UTC date)'),
    (2,  'WINDOW_END_EXCL',         CAST(c.window_end_excl AS VARCHAR) || ' (exclusive UTC date)'),
    (3,  'GAP_K',                   CAST(c.gap_k AS VARCHAR) || ' x station cadence marks a gap'),
    (4,  'FROZEN_RUN_MIN_READINGS', CAST(c.frozen_run_min_readings AS VARCHAR) || ' identical air temperatures in a row'),
    (5,  'MIN_INTERVALS_FOR_MODE',  CAST(c.min_intervals_for_mode AS VARCHAR) || ' intervals needed before a station sets its own cadence'),
    (6,  'UPTIME_FLAG_PCT',         CAST(CAST(c.uptime_flag_pct AS DECIMAL(9,2)) AS VARCHAR) || ' percent slot coverage, below this the station is flagged'),
    (7,  'AIR_TEMP_MIN_C',          CAST(CAST(c.air_temp_min_c AS DECIMAL(9,2)) AS VARCHAR) || ' degrees Celsius'),
    (8,  'AIR_TEMP_MAX_C',          CAST(CAST(c.air_temp_max_c AS DECIMAL(9,2)) AS VARCHAR) || ' degrees Celsius'),
    (9,  'RH_MIN_PCT',              CAST(CAST(c.rh_min_pct AS DECIMAL(9,2)) AS VARCHAR) || ' percent relative humidity'),
    (10, 'RH_MAX_PCT',              CAST(CAST(c.rh_max_pct AS DECIMAL(9,2)) AS VARCHAR) || ' percent relative humidity'),
    (11, 'WIND_MIN',                CAST(CAST(c.wind_min AS DECIMAL(9,2)) AS VARCHAR) || ' in the published wind unit'),
    (12, 'WIND_MAX',                CAST(CAST(c.wind_max AS DECIMAL(9,2)) AS VARCHAR) || ' in the published wind unit')
) AS v(rank, measure, detail)

-- window ---------------------------------------------------------------------
UNION ALL
SELECT 3, 'window', v.rank, NULL, NULL, v.measure, v.detail,
       NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL
FROM audit_constants c, load_audit la,
LATERAL (VALUES
    (1, 'window_days',
        CAST(date_diff('day', c.window_start, c.window_end_excl) AS VARCHAR)),
    (2, 'window_seconds',
        CAST(date_diff('second', CAST(c.window_start AS TIMESTAMP),
                       CAST(c.window_end_excl AS TIMESTAMP)) AS VARCHAR)),
    (3, 'stations',            CAST((SELECT count(*) FROM stations) AS VARCHAR)),
    (4, 'station_days',        CAST((SELECT count(*) FROM station_day_quality) AS VARCHAR)),
    (5, 'snapshot_rows',       CAST(la.snapshot_rows AS VARCHAR)),
    (6, 'rows_unparseable_timestamp', CAST(la.rows_unparseable_timestamp AS VARCHAR)),
    (7, 'rows_outside_window', CAST(la.rows_outside_window AS VARCHAR)),
    (8, 'readings_kept',       CAST(la.readings_kept AS VARCHAR)),
    (9, 'unparseable_air_temperature',    CAST(la.unparseable_air_temperature AS VARCHAR)),
    (10, 'unparseable_relative_humidity', CAST(la.unparseable_relative_humidity AS VARCHAR)),
    (11, 'unparseable_avg_wind_speed',    CAST(la.unparseable_avg_wind_speed AS VARCHAR))
) AS v(rank, measure, detail)

-- coverage_tie ---------------------------------------------------------------
UNION ALL
SELECT 4, 'coverage_tie', v.rank, NULL, NULL, v.measure, v.detail,
       NULL, NULL, v.n, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL
FROM (VALUES
    (1, 'snapshot_rows_minus_exclusions',
        'snapshot rows less unparseable timestamps and rows outside the window',
        (SELECT snapshot_rows - rows_unparseable_timestamp - rows_outside_window
         FROM load_audit)),
    (2, 'sum_readings_actual_station_days',
        'readings summed over every station-day in the mart',
        (SELECT sum(readings_actual) FROM station_day_quality)),
    (3, 'sum_readings_actual_scorecard',
        'readings summed over the station scorecard',
        (SELECT sum(readings_actual) FROM station_scorecard))
) AS v(rank, measure, detail, n)

-- station_cadence ------------------------------------------------------------
UNION ALL
SELECT 5, 'station_cadence',
       row_number() OVER (ORDER BY cad.site_id),
       cad.site_id, NULL, 'modal_interval',
       cad.cadence_source || ', ' || CAST(cad.modal_interval_count AS VARCHAR)
         || ' of ' || CAST(cad.measured_intervals AS VARCHAR) || ' measured intervals',
       cad.cadence_seconds, cad.cadence_seconds, NULL, NULL,
       CAST(86400 / cad.cadence_seconds AS BIGINT), NULL,
       CAST(round(100.0 * cad.modal_interval_count
                  / nullif(cad.measured_intervals, 0), 2) AS DECIMAL(9,2)),
       NULL, NULL, NULL, NULL
FROM station_cadence cad

-- station_scorecard ----------------------------------------------------------
UNION ALL
SELECT 6, 'station_scorecard',
       row_number() OVER (ORDER BY s.site_id),
       s.site_id, NULL, 'window_total',
       s.station_flag
         || CASE WHEN s.station_flag_reasons <> ''
                 THEN ': ' || s.station_flag_reasons ELSE '' END,
       s.cadence_seconds, NULL,
       s.readings_actual, s.slots_covered, s.readings_expected,
       s.uptime_pct, NULL,
       s.gap_count, s.frozen_run_count, s.out_of_range_count, s.missing_values
FROM station_scorecard s

-- completeness_ranking -------------------------------------------------------
UNION ALL
SELECT 7, 'completeness_ranking', r.completeness_rank,
       r.site_id, NULL, 'slot_coverage',
       CAST(r.days_below_full AS VARCHAR) || ' of '
         || CAST(r.days_in_window AS VARCHAR) || ' days below full, '
         || CAST(r.days_with_no_readings AS VARCHAR) || ' silent, '
         || r.station_flag,
       r.cadence_seconds, NULL,
       r.readings_actual, r.slots_covered, r.readings_expected,
       r.uptime_pct, NULL,
       r.gap_count, r.frozen_run_count, r.out_of_range_count, r.missing_values
FROM completeness_ranking r

-- missing_by_measure ---------------------------------------------------------
UNION ALL
SELECT 8, 'missing_by_measure',
       row_number() OVER (ORDER BY m.share DESC, m.site_id, m.measure),
       m.site_id, NULL, m.measure,
       'missing values against readings received',
       NULL, NULL, m.readings_actual, NULL, NULL, NULL,
       CAST(round(m.share, 2) AS DECIMAL(9,2)),
       NULL, NULL, NULL, m.missing
FROM (
    SELECT site_id, 'air_temperature' AS measure, readings_actual,
           missing_air_temperature AS missing,
           100.0 * missing_air_temperature / nullif(readings_actual, 0) AS share
    FROM station_scorecard
    UNION ALL
    SELECT site_id, 'relative_humidity', readings_actual,
           missing_relative_humidity,
           100.0 * missing_relative_humidity / nullif(readings_actual, 0)
    FROM station_scorecard
    UNION ALL
    SELECT site_id, 'avg_wind_speed', readings_actual,
           missing_avg_wind_speed,
           100.0 * missing_avg_wind_speed / nullif(readings_actual, 0)
    FROM station_scorecard
) m
WHERE m.missing > 0

-- gap_detail -----------------------------------------------------------------
UNION ALL
SELECT 9, 'gap_detail',
       row_number() OVER (ORDER BY g.interval_seconds DESC, g.site_id, g.ts_from),
       g.site_id, g.reading_date, 'reporting_gap',
       strftime(g.ts_from, '%Y-%m-%dT%H:%M:%S') || ' to '
         || strftime(g.ts_to, '%Y-%m-%dT%H:%M:%S') || ', '
         || CAST(g.cadence_multiple AS VARCHAR) || 'x cadence',
       g.cadence_seconds, g.interval_seconds,
       NULL, NULL, NULL, NULL, NULL,
       1, NULL, NULL, NULL
FROM gap_events g

-- frozen_detail --------------------------------------------------------------
UNION ALL
SELECT 10, 'frozen_detail',
       row_number() OVER (ORDER BY f.run_length DESC, f.site_id, f.ts_from),
       f.site_id, f.reading_date, 'air_temperature',
       'held ' || CAST(CAST(f.frozen_value AS DECIMAL(9,2)) AS VARCHAR) || ' from '
         || strftime(f.ts_from, '%Y-%m-%dT%H:%M:%S') || ' to '
         || strftime(f.ts_to, '%Y-%m-%dT%H:%M:%S'),
       cad.cadence_seconds, f.run_seconds,
       f.run_length, NULL, NULL, NULL, NULL,
       NULL, 1, NULL, NULL
FROM frozen_runs f
JOIN station_cadence cad ON cad.site_id = f.site_id

-- out_of_range_detail --------------------------------------------------------
UNION ALL
SELECT 11, 'out_of_range_detail',
       row_number() OVER (ORDER BY o.ts, o.site_id, o.measure),
       o.site_id, o.reading_date, o.measure,
       'value ' || CAST(CAST(o.value AS DECIMAL(9,2)) AS VARCHAR) || ' at '
         || strftime(o.ts, '%Y-%m-%dT%H:%M:%S') || ', plausible range '
         || CAST(CAST(o.bound_min AS DECIMAL(9,2)) AS VARCHAR) || ' to '
         || CAST(CAST(o.bound_max AS DECIMAL(9,2)) AS VARCHAR),
       NULL, NULL, NULL, NULL, NULL, NULL, NULL,
       NULL, NULL, 1, NULL
FROM out_of_range_events o;
