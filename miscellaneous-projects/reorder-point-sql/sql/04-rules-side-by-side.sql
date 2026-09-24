-- The two rules replayed over the same cycles, part by part: the average
-- rule from query 02, which orders at the lead-time demand alone, and the
-- safety-stock rule from query 03, which adds 1.65 standard deviations of
-- lead-time demand. The replay is query 02's: back-to-back stretches one
-- lead time long, counted from the first day of the log, each whole stretch
-- a cycle that starts with the stock at the reorder point and runs out if
-- it uses more than that. The units_short columns add up, over the cycles
-- that ran out, how far each one's usage went past the reorder point: the
-- units asked for at an empty shelf.
WITH RECURSIVE
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
newton(part, lead_days, lead_demand, m, x, next_x) AS (
    -- m is the safety stock squared, rounded up, with 27225 standing for
    -- 1.65 x 1.65 x 10000; the Newton steps find its root in whole numbers,
    -- as in query 03.
    SELECT part, lead_days, lead_demand, m, m, (m + 1) / 2
    FROM (
        SELECT
            part,
            lead_days,
            (2 * lead_days * units + days) / (2 * days) AS lead_demand,
            (27225 * lead_days * spread + 10000 * days * (days - 1) - 1) / (10000 * days * (days - 1)) AS m
        FROM per_part
    )
    UNION ALL
    SELECT part, lead_days, lead_demand, m, next_x, (next_x + m / next_x) / 2
    FROM newton
    WHERE next_x < x
),
rules AS (
    SELECT
        part,
        lead_days,
        lead_demand AS average_point,
        lead_demand + MIN(x) + (MIN(x) * MIN(x) < m) AS safety_point
    FROM newton
    GROUP BY part, lead_days, lead_demand, m
),
stretches AS (
    SELECT u.part, COUNT(*) AS days, SUM(u.units) AS used
    FROM usage u
    JOIN parts p ON p.part = u.part
    CROSS JOIN start s
    GROUP BY u.part, CAST(julianday(u.day) - s.first_jd AS INTEGER) / p.lead_days
),
replayed AS (
    SELECT
        r.part,
        r.average_point,
        r.safety_point,
        SUM(t.days = r.lead_days) AS cycles,
        SUM(t.days = r.lead_days AND t.used > r.average_point) AS average_ran_out,
        SUM(CASE WHEN t.days = r.lead_days AND t.used > r.average_point
                 THEN t.used - r.average_point ELSE 0 END) AS average_short,
        SUM(t.days = r.lead_days AND t.used > r.safety_point) AS safety_ran_out,
        SUM(CASE WHEN t.days = r.lead_days AND t.used > r.safety_point
                 THEN t.used - r.safety_point ELSE 0 END) AS safety_short
    FROM rules r
    JOIN stretches t ON t.part = r.part
    GROUP BY r.part, r.average_point, r.safety_point
),
kinds(total) AS (
    VALUES (0), (1)
)
SELECT
    CASE WHEN k.total = 1 THEN 'all parts' ELSE r.part END AS part,
    SUM(r.cycles) AS cycles,
    CASE WHEN k.total = 1 THEN NULL ELSE MAX(r.average_point) END AS average_point,
    SUM(r.average_ran_out) AS average_ran_out,
    SUM(r.average_short) AS average_units_short,
    CASE WHEN k.total = 1 THEN NULL ELSE MAX(r.safety_point) END AS safety_point,
    SUM(r.safety_ran_out) AS safety_ran_out,
    SUM(r.safety_short) AS safety_units_short
FROM replayed r
CROSS JOIN kinds k
GROUP BY k.total, CASE WHEN k.total = 1 THEN NULL ELSE r.part END
ORDER BY k.total, part;
