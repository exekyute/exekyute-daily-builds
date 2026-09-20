-- The histogram with every bin in it. The bins are built first, by a
-- recursive CTE that counts from the lowest bin any reading falls in to the
-- highest, and the counts are joined onto them, so a bin with nothing in it
-- still prints, at zero. The bin is the minutes divided by ten and rounded
-- down: SQLite divides toward zero, so nine is taken off a negative reading
-- first, which sends -1 to the bin at -10 rather than the one at 0. A bin
-- runs from its own multiple of ten up to nine past it, so a reading exactly
-- on a boundary, such as -10 or 20, belongs to the bin that starts there.
-- The bar is one hash for every fiftieth of the fullest bin, and a bin with
-- any reading at all shows one.
WITH RECURSIVE
binned AS (
    SELECT (minutes - 9 * (minutes < 0)) / 10 AS bin FROM deliveries
),
tally AS (
    SELECT bin, COUNT(*) AS deliveries FROM binned GROUP BY bin
),
bounds AS (
    SELECT MIN(bin) AS first_bin, MAX(bin) AS last_bin, SUM(deliveries) AS readings,
           MAX(deliveries) AS fullest
    FROM tally
),
bins(bin) AS (
    SELECT first_bin FROM bounds
    UNION ALL
    SELECT bin + 1 FROM bins WHERE bin < (SELECT last_bin FROM bounds)
),
counted AS (
    SELECT
        b.bin,
        COALESCE(t.deliveries, 0) AS deliveries,
        SUM(COALESCE(t.deliveries, 0)) OVER (ORDER BY b.bin) AS running
    FROM bins b
    LEFT JOIN tally t ON t.bin = b.bin
)
SELECT
    printf('%d to %d', c.bin * 10, c.bin * 10 + 9) AS span,
    c.deliveries,
    c.running,
    printf('%d.%d', (2000 * c.deliveries + o.readings) / (2 * o.readings) / 10,
                    (2000 * c.deliveries + o.readings) / (2 * o.readings) % 10) AS share_pct,
    CASE WHEN c.deliveries = 0 THEN ''
         ELSE substr('##################################################', 1,
                     MAX(1, c.deliveries * 50 / o.fullest)) END AS bar
FROM counted c
CROSS JOIN bounds o
ORDER BY c.bin;
