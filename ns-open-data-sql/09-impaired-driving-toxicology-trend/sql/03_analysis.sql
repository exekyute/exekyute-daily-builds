-- 03_analysis.sql
-- Question this step answers: for each year and for each month, how many driver
-- deaths fell into each toxicology outcome, and what share tested positive?
--
-- Four category labels form a mutually exclusive, exhaustive split of every
-- period's total driver deaths (verified: positive + not_detected +
-- tox_unavailable = total, exactly, in every year and every month):
--   positive         = 'One or more specified drug(s) detected'
--   not_detected     = 'Specified drugs not detected'
--   tox_unavailable  = 'Toxicology not available'   (unknown or pending)
--   total_deaths     = 'Total driver deaths'
-- The many alcohol/THC/cocaine sub-labels in the source overlap each other and
-- are NOT summed here; only the split above is used.
--
-- pct_positive is the positivity rate among drivers who had a toxicology result:
-- positive / (positive + not_detected), as a percentage to one decimal. Deaths
-- with no result available are excluded from that denominator so a year with more
-- pending cases does not read as fewer positives.

CREATE TABLE toxicology_trend AS
WITH
-- By-year slice: one row per calendar year, each outcome pivoted to a column.
year_dim AS (
    SELECT
        'year'                 AS dimension,
        CAST(year AS VARCHAR)  AS period,
        year                   AS period_num,
        MAX(CASE WHEN category = 'Total driver deaths'                       THEN deaths END) AS total_deaths,
        MAX(CASE WHEN category = 'One or more specified drug(s) detected'    THEN deaths END) AS positive,
        MAX(CASE WHEN category = 'Specified drugs not detected'              THEN deaths END) AS not_detected,
        MAX(CASE WHEN category = 'Toxicology not available'                  THEN deaths END) AS tox_unavailable
    FROM driver_deaths
    WHERE year IS NOT NULL AND month IS NULL
    GROUP BY year
),
-- By-month slice: one row per month, pooled across all years, for seasonality.
-- period_num maps the month abbreviation to calendar order (1..12).
month_dim AS (
    SELECT
        'month'  AS dimension,
        month    AS period,
        CASE month
            WHEN 'Jan' THEN 1  WHEN 'Feb' THEN 2  WHEN 'Mar' THEN 3  WHEN 'Apr' THEN 4
            WHEN 'May' THEN 5  WHEN 'Jun' THEN 6  WHEN 'Jul' THEN 7  WHEN 'Aug' THEN 8
            WHEN 'Sep' THEN 9  WHEN 'Oct' THEN 10 WHEN 'Nov' THEN 11 WHEN 'Dec' THEN 12
        END      AS period_num,
        MAX(CASE WHEN category = 'Total driver deaths'                       THEN deaths END) AS total_deaths,
        MAX(CASE WHEN category = 'One or more specified drug(s) detected'    THEN deaths END) AS positive,
        MAX(CASE WHEN category = 'Specified drugs not detected'              THEN deaths END) AS not_detected,
        MAX(CASE WHEN category = 'Toxicology not available'                  THEN deaths END) AS tox_unavailable
    FROM driver_deaths
    WHERE month IS NOT NULL AND year IS NULL
    GROUP BY month
),
combined AS (
    SELECT * FROM year_dim
    UNION ALL
    SELECT * FROM month_dim
)
SELECT
    dimension,
    period,
    period_num,
    total_deaths,
    positive,
    not_detected,
    tox_unavailable,
    CAST(ROUND(100.0 * positive / NULLIF(positive + not_detected, 0), 1) AS DECIMAL(5,1)) AS pct_positive
FROM combined;
