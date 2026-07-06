-- 03_analysis.sql
-- Questions this step answers:
--   What share of each fiscal year's registered farms did each commodity hold?
--   How did each commodity's farm count move from one fiscal year to the next?
--   Over the full window, which commodity gained the most share of the mix and which lost the most?

-- commodity_mix: one row per commodity per fiscal year, the table 99_export.sql writes out.
-- share_pct is the commodity's percent of that year's total registered farms. The year-over-year
-- columns are filled only when the previous fiscal year is the immediately adjacent one, so a gap
-- in a commodity's history does not produce a misleading jump.
DROP TABLE IF EXISTS commodity_mix;
CREATE TABLE commodity_mix AS
WITH base AS (
    SELECT
        c.commodity,
        c.fiscal_year,
        d.yr_rank,
        c.farms,
        y.year_total_farms,
        round(100.0 * c.farms / y.year_total_farms, 2) AS share_pct
    FROM clean_farm c
    JOIN fiscal_year_dim d USING (fiscal_year)
    JOIN year_total      y USING (fiscal_year)
),
withlag AS (
    SELECT
        *,
        lag(farms)   OVER (PARTITION BY commodity ORDER BY yr_rank) AS prev_farms,
        lag(yr_rank) OVER (PARTITION BY commodity ORDER BY yr_rank) AS prev_rank
    FROM base
)
SELECT
    commodity,
    fiscal_year,
    farms,
    year_total_farms,
    share_pct,
    CASE WHEN prev_rank = yr_rank - 1 THEN prev_farms END          AS prev_year_farms,
    CASE WHEN prev_rank = yr_rank - 1 THEN farms - prev_farms END  AS yoy_change_farms,
    CASE WHEN prev_rank = yr_rank - 1 AND prev_farms <> 0
         THEN round(100.0 * (farms - prev_farms) / prev_farms, 2)
    END                                                            AS yoy_pct
FROM withlag
ORDER BY commodity, fiscal_year;

-- commodity_growth: share change between the first and last fiscal year of the window, for
-- commodities present in BOTH endpoint years. A commodity present in only one endpoint entered
-- or left the mix inside the window (often a relabelling), so it has no comparable pair of
-- endpoint shares and is held out of this ranking.
DROP TABLE IF EXISTS commodity_growth;
CREATE TABLE commodity_growth AS
WITH bounds AS (
    SELECT min(fiscal_year) AS first_year, max(fiscal_year) AS last_year FROM fiscal_year_dim
),
endpoints AS (
    SELECT
        m.commodity,
        max(CASE WHEN m.fiscal_year = b.first_year THEN m.share_pct END) AS first_share_pct,
        max(CASE WHEN m.fiscal_year = b.last_year  THEN m.share_pct END) AS last_share_pct
    FROM commodity_mix m
    CROSS JOIN bounds b
    WHERE m.fiscal_year IN (b.first_year, b.last_year)
    GROUP BY m.commodity
)
SELECT
    commodity,
    first_share_pct,
    last_share_pct,
    round(last_share_pct - first_share_pct, 2) AS share_change_pp,
    CASE
        WHEN last_share_pct - first_share_pct > 0 THEN 'growing'
        WHEN last_share_pct - first_share_pct < 0 THEN 'shrinking'
        ELSE 'flat'
    END AS direction
FROM endpoints
WHERE first_share_pct IS NOT NULL AND last_share_pct IS NOT NULL
ORDER BY share_change_pp DESC, commodity;

-- headline: the single fastest-growing and fastest-shrinking named commodity over the window,
-- by change in share of the mix. 'Other' is a residual catch-all rather than a commodity, so it
-- is left out of the ranking.
DROP TABLE IF EXISTS headline;
CREATE TABLE headline AS
WITH ranked AS (
    SELECT * FROM commodity_growth WHERE commodity <> 'Other'
),
top AS (SELECT * FROM ranked ORDER BY share_change_pp DESC, commodity LIMIT 1),
bot AS (SELECT * FROM ranked ORDER BY share_change_pp ASC,  commodity LIMIT 1)
SELECT 'fastest growing'   AS metric, commodity, first_share_pct, last_share_pct, share_change_pp FROM top
UNION ALL
SELECT 'fastest shrinking' AS metric, commodity, first_share_pct, last_share_pct, share_change_pp FROM bot
ORDER BY share_change_pp DESC;
