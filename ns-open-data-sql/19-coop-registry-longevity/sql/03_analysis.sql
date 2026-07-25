-- 03_analysis.sql
-- Question this step answers: how many of today's registered co-ops date from each
-- incorporation year and decade, and what does each surviving cohort look like?
--
-- The registry lists co-operatives registered as of the extract date, so every row is a
-- survivor by definition. Survivorship here reads the registry from the other side:
-- for each incorporation cohort, how many co-ops made it onto today's registry, what
-- share of the registry they are, and how the non-profit / for-profit mix shifts
-- across cohorts. There is no status column to split active from dissolved; presence
-- in the snapshot is the active rule (spec.md, Cleaning and validation rules).

-- Incorporations by year, among co-ops surviving on the registry.
INSERT INTO incorporations_by_year
SELECT
    incorporation_year,
    count(*)                          AS incorporated,
    sum(is_nonprofit)                 AS nonprofit_count,
    count(*) - sum(is_nonprofit)      AS forprofit_count
FROM clean_coops
GROUP BY incorporation_year;

-- One row per incorporation decade: the surviving cohort profile.
INSERT INTO cohort_longevity
WITH per_decade AS (
    -- cohort size, mix, and the earliest incorporation still on the registry
    SELECT
        decade,
        count(*)                      AS survivors,
        sum(is_nonprofit)             AS nonprofit_count,
        count(*) - sum(is_nonprofit)  AS forprofit_count,
        min(incorporation_date)       AS first_incorporation
    FROM clean_coops
    GROUP BY decade
),
peak AS (
    -- the busiest incorporation year inside each decade; ties go to the earliest year
    SELECT
        c.decade,
        y.incorporation_year          AS peak_year,
        y.incorporated                AS peak_count,
        row_number() OVER (
            PARTITION BY c.decade
            ORDER BY y.incorporated DESC, y.incorporation_year ASC
        ) AS rn
    FROM incorporations_by_year y
    JOIN (SELECT DISTINCT decade, incorporation_year FROM clean_coops) c
      USING (incorporation_year)
),
registry AS (
    SELECT count(*) AS registry_total FROM clean_coops
)
SELECT
    d.decade,
    d.survivors,
    -- this cohort's share of the whole registry, as a percentage to one decimal place
    round(d.survivors * 100.0 / r.registry_total, 1)        AS registry_share_pct,
    d.nonprofit_count,
    d.forprofit_count,
    round(d.nonprofit_count * 100.0 / d.survivors, 1)       AS nonprofit_share_pct,
    k.peak_year,
    k.peak_count,
    -- age of the cohort's oldest survivor as of the pull date declared in 02_transform.sql
    round(date_diff('day', d.first_incorporation, p.pull_date) / 365.2425, 1)
                                                            AS oldest_age_years
FROM per_decade d
JOIN peak k ON k.decade = d.decade AND k.rn = 1
CROSS JOIN registry r
CROSS JOIN params p;

-- The row-level mart Power BI reads. Same grain as clean_coops: one row per co-op.
INSERT INTO mart_coop_longevity
SELECT
    registry_id,
    co_op_name,
    town,
    incorporation_date,
    incorporation_year,
    decade,
    org_form,
    is_nonprofit,
    coop_type,
    age_years
FROM clean_coops;
