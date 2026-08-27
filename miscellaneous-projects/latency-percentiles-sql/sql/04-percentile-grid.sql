-- The latency table a status page would show: one row per endpoint with the
-- mean beside the percentiles, so the gap between them is visible in one
-- glance. Search averages 133.5 ms; its p99 is 800.
WITH ranked AS (
    SELECT endpoint,
           duration_ms,
           ROW_NUMBER() OVER (PARTITION BY endpoint ORDER BY duration_ms) AS rn,
           COUNT(*) OVER (PARTITION BY endpoint) AS n
    FROM requests
),
targets(p) AS (
    VALUES (0.50), (0.90), (0.99)
),
positions AS (
    SELECT e.endpoint, e.n, t.p,
           1 + t.p * (e.n - 1) AS pos
    FROM (SELECT DISTINCT endpoint, n FROM ranked) e
    CROSS JOIN targets t
),
long_form AS (
    SELECT po.endpoint, po.n, po.p,
           lo.duration_ms
           + (po.pos - CAST(po.pos AS INTEGER)) * (hi.duration_ms - lo.duration_ms) AS value_ms
    FROM positions po
    JOIN ranked lo ON lo.endpoint = po.endpoint AND lo.rn = CAST(po.pos AS INTEGER)
    JOIN ranked hi ON hi.endpoint = po.endpoint AND hi.rn = MIN(CAST(po.pos AS INTEGER) + 1, po.n)
),
means AS (
    SELECT endpoint, AVG(duration_ms) AS mean_ms
    FROM requests
    GROUP BY endpoint
)
SELECT lf.endpoint,
       lf.n AS requests,
       printf('%.1f', m.mean_ms) AS mean_ms,
       printf('%.1f', MAX(CASE WHEN lf.p = 0.50 THEN lf.value_ms END)) AS p50_ms,
       printf('%.1f', MAX(CASE WHEN lf.p = 0.90 THEN lf.value_ms END)) AS p90_ms,
       printf('%.1f', MAX(CASE WHEN lf.p = 0.99 THEN lf.value_ms END)) AS p99_ms
FROM long_form lf
JOIN means m ON m.endpoint = lf.endpoint
GROUP BY lf.endpoint, lf.n, m.mean_ms
ORDER BY lf.endpoint;
