-- The two histograms side by side, bin by bin, under the heading each one
-- prints for that bin. The naive column is what query 02 shows there, blank
-- where it shows nothing at all, and the last column says what went wrong:
-- a bin the quick query never prints, or a count that is off because
-- dividing toward zero put the readings under a different heading.
WITH RECURSIVE
readings AS (
    SELECT
        (minutes - 9 * (minutes < 0)) / 10 AS bin,
        minutes / 10 AS naive_bin
    FROM deliveries
),
tally AS (
    SELECT bin, COUNT(*) AS deliveries FROM readings GROUP BY bin
),
naive_tally AS (
    SELECT naive_bin AS bin, COUNT(*) AS deliveries FROM readings GROUP BY naive_bin
),
bounds AS (
    -- Both histograms, since a reading early but not on a boundary lands a
    -- bin higher under the quick query, which on an all-early log puts its
    -- top bin above every bin of the true one.
    SELECT MIN(bin) AS first_bin, MAX(bin) AS last_bin
    FROM (SELECT bin FROM tally UNION ALL SELECT bin FROM naive_tally)
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
        COALESCE(n.deliveries, 0) AS naive_deliveries
    FROM bins b
    LEFT JOIN tally t ON t.bin = b.bin
    LEFT JOIN naive_tally n ON n.bin = b.bin
)
SELECT
    printf('%d to %d', bin * 10, bin * 10 + 9) AS span,
    deliveries,
    CASE WHEN naive_deliveries = 0 THEN '' ELSE printf('%d', naive_deliveries) END AS naive,
    CASE
        WHEN naive_deliveries = 0 AND deliveries = 0 THEN 'empty, and the quick query leaves it out'
        WHEN naive_deliveries = 0 THEN 'the quick query leaves this bin out'
        WHEN naive_deliveries = deliveries THEN 'the same in both'
        WHEN naive_deliveries > deliveries THEN printf('%d too many, cut toward zero', naive_deliveries - deliveries)
        ELSE printf('%d missing, cut toward zero', deliveries - naive_deliveries)
    END AS note
FROM counted
ORDER BY bin;
