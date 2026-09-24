-- The tempting reorder point: order when stock falls to the usage expected
-- over the lead time, which is the average daily usage times the lead time,
-- rounded half up to a whole unit. Then the log is replayed against it, one
-- lead time at a time. Each part's days are cut into back-to-back stretches
-- as long as its lead time, counted from the first day of the log, and each
-- whole stretch is one replenishment cycle: the order goes in with the stock
-- at the reorder point, and the delivery comes at the close of the
-- stretch's last day. A stretch that uses more than the reorder point runs
-- out before the delivery; one that uses exactly that ends at zero without
-- running out. A stretch cut short by the end of the log is left out.
-- When a stretch is as likely to use more than the average as less, this
-- rule runs out in about half the cycles.
WITH
start AS (
    SELECT julianday(MIN(day)) AS first_jd FROM usage
),
per_part AS (
    SELECT p.part, p.lead_days, COUNT(*) AS days, SUM(u.units) AS units
    FROM parts p
    JOIN usage u ON u.part = p.part
    GROUP BY p.part
),
rule AS (
    SELECT part, lead_days, (2 * lead_days * units + days) / (2 * days) AS reorder_point
    FROM per_part
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
        r.lead_days,
        r.reorder_point,
        SUM(t.days = r.lead_days) AS cycles,
        SUM(t.days = r.lead_days AND t.used > r.reorder_point) AS ran_out
    FROM rule r
    JOIN stretches t ON t.part = r.part
    GROUP BY r.part
),
kinds(total) AS (
    VALUES (0), (1)
)
-- One row per part, then a total line from the same replay: kind 1 puts
-- every part in one group.
SELECT
    CASE WHEN k.total = 1 THEN 'all parts' ELSE r.part END AS part,
    CASE WHEN k.total = 1 THEN NULL ELSE MAX(r.lead_days) END AS lead_days,
    CASE WHEN k.total = 1 THEN NULL ELSE MAX(r.reorder_point) END AS reorder_point,
    SUM(r.cycles) AS cycles,
    SUM(r.ran_out) AS ran_out,
    (200 * SUM(r.ran_out) + SUM(r.cycles)) / (2 * SUM(r.cycles)) AS ran_out_pct
FROM replayed r
CROSS JOIN kinds k
GROUP BY k.total, CASE WHEN k.total = 1 THEN NULL ELSE r.part END
ORDER BY k.total, part;
