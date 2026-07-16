-- 03_analysis.sql
-- The tax burden index:
--   spread            = commercial_rate - residential_rate, rounded to 4 decimals
--                       (both rates are dollars per $100 of assessed value)
--   rank_in_year      = RANK() by spread within each year, widest spread first;
--                       ties share a rank
--   yoy_spread_change = spread minus the same municipality's previous observed
--                       year (LAG over year_start); NULL in a municipality's
--                       first observed year. A municipality is (area, area_type):
--                       six names exist as both a Town and a Rural Municipality.
--   is_outlier        = latest year only: spread at or above the 90th percentile
--                       (quantile_cont(0.90), linear interpolation) of all
--                       latest-year spreads; false everywhere else

CREATE TABLE tax_burden_index AS
WITH spreads AS (
    SELECT
        area,
        area_type,
        year_label,
        year_start,
        residential_rate,
        commercial_rate,
        round(commercial_rate - residential_rate, 4) AS spread
    FROM rates_clean
),
ranked AS (
    SELECT
        *,
        rank() OVER (PARTITION BY year_start ORDER BY spread DESC) AS rank_in_year,
        round(spread - lag(spread) OVER (PARTITION BY area, area_type ORDER BY year_start), 4) AS yoy_spread_change
    FROM spreads
),
latest AS (
    SELECT max(year_start) AS latest_year FROM spreads
),
threshold AS (
    SELECT quantile_cont(s.spread, 0.90) AS p90_spread
    FROM spreads s, latest l
    WHERE s.year_start = l.latest_year
)
SELECT
    r.area,
    r.area_type,
    r.year_label,
    r.year_start,
    r.residential_rate,
    r.commercial_rate,
    r.spread,
    r.rank_in_year,
    r.yoy_spread_change,
    (r.year_start = l.latest_year AND r.spread >= t.p90_spread) AS is_outlier
FROM ranked r
CROSS JOIN latest l
CROSS JOIN threshold t
ORDER BY r.year_start, r.rank_in_year, r.area, r.area_type;
