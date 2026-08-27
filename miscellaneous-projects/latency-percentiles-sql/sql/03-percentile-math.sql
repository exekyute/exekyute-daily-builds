-- Interpolated percentiles the way PERCENTILE_CONT defines them, in engines
-- that have it: the percentile p sits at 1-based rank 1 + p * (n - 1). When
-- that lands between two ranks, the value is a linear blend of the two. CAST
-- truncates the position down to the lower rank, the fraction left over is
-- the blend weight, and MIN caps the upper rank at n so an exact landing
-- never reaches past the last row.
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
)
SELECT po.endpoint,
       printf('p%d', CAST(po.p * 100 AS INTEGER)) AS percentile,
       lo.duration_ms AS lower_value,
       hi.duration_ms AS upper_value,
       ROUND(po.pos - CAST(po.pos AS INTEGER), 2) AS blend,
       ROUND(lo.duration_ms
             + (po.pos - CAST(po.pos AS INTEGER)) * (hi.duration_ms - lo.duration_ms), 2) AS value_ms
FROM positions po
JOIN ranked lo ON lo.endpoint = po.endpoint AND lo.rn = CAST(po.pos AS INTEGER)
JOIN ranked hi ON hi.endpoint = po.endpoint AND hi.rn = MIN(CAST(po.pos AS INTEGER) + 1, po.n)
ORDER BY po.endpoint, po.p;
