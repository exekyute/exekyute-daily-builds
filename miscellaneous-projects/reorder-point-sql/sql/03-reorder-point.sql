-- The reorder point with safety stock, at a 95 percent service level:
--   reorder point = lead-time demand + safety stock
--   safety stock  = z x daily standard deviation x square root of the lead time
-- with z = 1.65, the one-sided normal value for about 95 percent. It
-- assumes steady usage, where one day tells nothing about the next, a lead
-- time that does not vary, and usage over a lead time close enough to a
-- normal curve for z to carry its percentage.
--
-- Every step is done in whole numbers. The spread, n x the sum of squares
-- minus the square of the sum, is exact in integers, so it cannot cancel
-- away the way the average of squares minus the squared average does in
-- floating point. The standard deviation of n days is the square root of
-- spread / (n x (n - 1)). SQLite has no square root before 3.35, and it is
-- optional after, so the roots come from a recursive CTE taking Newton
-- steps on whole numbers: x becomes (x + m / x) / 2 until it stops falling,
-- which leaves the largest whole number whose square is at most m.
--
-- Lead-time demand is rounded half up to a whole unit. Safety stock is
-- rounded up, since rounding it down would fall short of the service
-- level: it is the smallest whole number whose square is at least
-- 1.65 x 1.65 x lead days x spread / (n x (n - 1)). That value is rounded
-- up to a whole number m, and the safety stock is the root of m, plus one
-- unless m is a perfect square. The standard deviation is printed to a tenth,
-- rounded half up, and the safety stock is worked out from the exact
-- spread, not from that printed figure.
WITH RECURSIVE
per_part AS (
    SELECT
        p.part,
        p.lead_days,
        COUNT(*) AS days,
        SUM(u.units) AS units,
        COUNT(*) * SUM(u.units * u.units) - SUM(u.units) * SUM(u.units) AS spread
    FROM parts p
    JOIN usage u ON u.part = p.part
    GROUP BY p.part
),
roots_wanted(part, lead_days, days, units, what, m) AS (
    -- what 1: m is the square of twenty times the standard deviation,
    -- rounded down, so its root is twenty times the standard deviation
    -- rounded down, and (root + 1) / 2 is the standard deviation in tenths,
    -- rounded half up. what 2: m is the safety stock squared, rounded up;
    -- 27225 is 1.65 x 1.65 x 10000, so 10000 joins the divisor.
    SELECT
        c.part, c.lead_days, c.days, c.units, w.what,
        CASE w.what
            WHEN 1 THEN 400 * c.spread / (c.days * (c.days - 1))
            ELSE (27225 * c.lead_days * c.spread + 10000 * c.days * (c.days - 1) - 1)
                 / (10000 * c.days * (c.days - 1))
        END
    FROM per_part c
    CROSS JOIN (SELECT 1 AS what UNION ALL SELECT 2) w
),
newton(part, lead_days, days, units, what, m, x, next_x) AS (
    SELECT part, lead_days, days, units, what, m, m, (m + 1) / 2 FROM roots_wanted
    UNION ALL
    SELECT part, lead_days, days, units, what, m, next_x, (next_x + m / next_x) / 2
    FROM newton
    WHERE next_x < x
),
settled AS (
    -- x only ever falls, so its smallest value is the root.
    SELECT
        part,
        lead_days,
        (20 * units + days) / (2 * days) AS average_tenths,
        (MIN(CASE WHEN what = 1 THEN x END) + 1) / 2 AS deviation_tenths,
        (2 * lead_days * units + days) / (2 * days) AS lead_demand,
        MIN(CASE WHEN what = 2 THEN x END) AS stock_root,
        MAX(CASE WHEN what = 2 THEN m END) AS stock_squared
    FROM newton
    GROUP BY part, lead_days, days, units
)
SELECT
    part,
    lead_days,
    printf('%d.%d', average_tenths / 10, average_tenths % 10) AS avg_daily,
    printf('%d.%d', deviation_tenths / 10, deviation_tenths % 10) AS sd_daily,
    lead_demand,
    stock_root + (stock_root * stock_root < stock_squared) AS safety_stock,
    lead_demand + stock_root + (stock_root * stock_root < stock_squared) AS reorder_point
FROM settled
ORDER BY part;
