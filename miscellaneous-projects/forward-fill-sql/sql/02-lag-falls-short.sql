-- The trap, laid open. COALESCE(tenths, LAG(tenths)) is the first thing
-- anyone writes to fill a gap, and LAG reaches exactly one row back. It
-- fills a single missing reading correctly and then gives up: the second
-- row of any run looks back at the first, finds it empty too, and stays
-- blank. Every value it does produce is right, which is what makes it easy
-- to trust, and it simply produces fewer answers than it should.
-- The last_reading column is the honest answer, found with a correlated
-- subquery per row. It walks back through the primary-key index only as
-- far as the nearest real reading, so it costs little while dark runs are
-- short; query 03 reaches the same answer in one pass whose cost does not
-- depend on how the missing rows fall.
WITH ordered AS (
    SELECT r.sensor_id,
           r.reading_at,
           r.tenths,
           LAG(r.tenths) OVER (PARTITION BY r.sensor_id ORDER BY r.reading_at) AS lag_tenths,
           (SELECT p.tenths FROM readings p
            WHERE p.sensor_id = r.sensor_id
              AND p.reading_at < r.reading_at
              AND p.tenths IS NOT NULL
            ORDER BY p.reading_at DESC
            LIMIT 1) AS last_tenths
    FROM readings r
)
SELECT sensor_id,
       reading_at,
       CASE WHEN lag_tenths IS NULL THEN ''
            ELSE printf('%.1f', lag_tenths / 10.0) END AS lag_fill,
       printf('%.1f', last_tenths / 10.0) AS last_reading,
       CASE WHEN lag_tenths IS NULL THEN 'left blank' ELSE 'filled' END AS lag_outcome
FROM ordered
WHERE tenths IS NULL
  AND last_tenths IS NOT NULL
ORDER BY sensor_id, reading_at;
