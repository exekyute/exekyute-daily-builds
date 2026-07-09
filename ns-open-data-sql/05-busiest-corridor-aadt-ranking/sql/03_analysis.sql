-- 03_analysis.sql
-- Builds the corridor ranking: busiest segments by AADT, year-over-year growth per
-- segment, and a flag for segments at or above the stated capacity threshold.

-- Question answered: for each yearly reading, what was the previous reading for the
-- same segment? LAG walks each segment's readings in year order. This is the window
-- function the growth calculation rests on.
CREATE OR REPLACE TABLE segment_growth AS
SELECT
    section_id,
    yr,
    aadt,
    LAG(aadt) OVER (PARTITION BY section_id ORDER BY yr) AS prior_aadt,
    LAG(yr)   OVER (PARTITION BY section_id ORDER BY yr) AS prior_year
FROM segment_year;

-- Question answered: for each segment, what is its most recent AADT and its annualized
-- growth since the previous count? Growth is annualized, so a three-year gap between
-- counts (the usual re-count cadence) reads as a per-year rate rather than a raw jump.
CREATE OR REPLACE TABLE segment_current AS
WITH latest AS (
    SELECT
        section_id,
        yr,
        aadt,
        prior_aadt,
        prior_year,
        row_number() OVER (PARTITION BY section_id ORDER BY yr DESC) AS rn
    FROM segment_growth
)
SELECT
    section_id,
    yr                 AS current_year,
    aadt               AS current_aadt,
    prior_year,
    prior_aadt,
    (yr - prior_year)  AS year_gap,
    CASE
        WHEN prior_aadt IS NOT NULL AND prior_aadt > 0
        THEN round((pow(aadt::DOUBLE / prior_aadt, 1.0 / (yr - prior_year)) - 1) * 100, 2)
    END AS yoy_growth_pct
FROM latest
WHERE rn = 1;

-- Question answered: among established corridors (at least 5,000 vehicles per day at the
-- previous count) with a recent prior reading (within three years), which are growing
-- fastest? The base filter keeps the growth ranking off very low-volume roads, where a
-- small absolute change reads as a large percentage; the recency filter keeps it off
-- stale gaps, where a single annualized figure would not reflect current conditions.
CREATE OR REPLACE TABLE growth_ranked AS
SELECT
    section_id,
    rank() OVER (ORDER BY yoy_growth_pct DESC) AS growth_rank
FROM segment_current
WHERE yoy_growth_pct IS NOT NULL
  AND prior_aadt >= 5000
  AND year_gap <= 3;

-- Question answered: the final ranking. Rank every segment by its latest AADT, carry its
-- growth and growth rank, and flag the segments at or above the capacity threshold. The
-- threshold is stored as a column so the flag is self-documenting.
CREATE OR REPLACE TABLE corridor_ranking AS
SELECT
    rank() OVER (ORDER BY sc.current_aadt DESC)  AS aadt_rank,
    sc.section_id,
    a.highway,
    a.section,
    a.county,
    a.section_description,
    a.section_length_km,
    sc.current_year,
    sc.current_aadt,
    sc.prior_year,
    sc.prior_aadt,
    sc.yoy_growth_pct,
    g.growth_rank,
    10000                       AS capacity_threshold,
    (sc.current_aadt >= 10000)  AS over_capacity
FROM segment_current sc
JOIN segment_attr a USING (section_id)
LEFT JOIN growth_ranked g USING (section_id);
