-- The same replay at four service levels, every part together: z = 0, which
-- is the average rule of query 02 with no safety stock, and z = 1.28, 1.65
-- and 2.33, the one-sided normal values for about 90, 95 and 99 percent.
-- safety_stock adds up every part's safety stock at that level: the units
-- its reorder points hold above the lead-time demand, in exchange for the
-- cycles that no longer run out. The safety stock and the replay are
-- worked out as in queries 03 and 04, with z held in hundredths so that
-- z x z x 10000 is a whole number.
WITH RECURSIVE
levels(service_pct, z_hundredths) AS (
    VALUES (50, 0), (90, 128), (95, 165), (99, 233)
),
start AS (
    SELECT julianday(MIN(day)) AS first_jd FROM usage
),
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
newton(service_pct, z_hundredths, part, lead_days, lead_demand, m, x, next_x) AS (
    -- m is the safety stock squared at this level, rounded up.
    SELECT service_pct, z_hundredths, part, lead_days, lead_demand, m, m, (m + 1) / 2
    FROM (
        SELECT
            l.service_pct,
            l.z_hundredths,
            c.part,
            c.lead_days,
            (2 * c.lead_days * c.units + c.days) / (2 * c.days) AS lead_demand,
            (l.z_hundredths * l.z_hundredths * c.lead_days * c.spread + 10000 * c.days * (c.days - 1) - 1)
                / (10000 * c.days * (c.days - 1)) AS m
        FROM levels l
        CROSS JOIN per_part c
    )
    UNION ALL
    SELECT service_pct, z_hundredths, part, lead_days, lead_demand, m, next_x, (next_x + m / next_x) / 2
    FROM newton
    WHERE next_x < x
),
rules AS (
    SELECT
        service_pct,
        z_hundredths,
        part,
        lead_days,
        MIN(x) + (MIN(x) * MIN(x) < m) AS safety_stock,
        lead_demand + MIN(x) + (MIN(x) * MIN(x) < m) AS reorder_point
    FROM newton
    GROUP BY service_pct, z_hundredths, part, lead_days, lead_demand, m
),
stretches AS (
    SELECT u.part, COUNT(*) AS days, SUM(u.units) AS used
    FROM usage u
    JOIN parts p ON p.part = u.part
    CROSS JOIN start s
    GROUP BY u.part, CAST(julianday(u.day) - s.first_jd AS INTEGER) / p.lead_days
),
replayed AS (
    -- One row per level and part: the part's safety stock once, and its
    -- cycles and run-outs against that level's reorder point.
    SELECT
        r.service_pct,
        r.z_hundredths,
        r.safety_stock,
        SUM(t.days = r.lead_days) AS cycles,
        SUM(t.days = r.lead_days AND t.used > r.reorder_point) AS ran_out
    FROM rules r
    JOIN stretches t ON t.part = r.part
    GROUP BY r.service_pct, r.z_hundredths, r.part, r.safety_stock
)
SELECT
    service_pct,
    printf('%d.%02d', z_hundredths / 100, z_hundredths % 100) AS z,
    SUM(safety_stock) AS safety_stock,
    SUM(cycles) AS cycles,
    SUM(ran_out) AS ran_out,
    (200 * SUM(ran_out) + SUM(cycles)) / (2 * SUM(cycles)) AS ran_out_pct
FROM replayed
GROUP BY service_pct, z_hundredths
ORDER BY service_pct;
