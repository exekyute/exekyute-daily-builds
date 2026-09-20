-- The same readings at three bin widths. The width is a choice, and it
-- decides what the histogram shows: narrow bins break the middle into
-- spikes that look like noise, and wide bins swallow the quiet stretch out
-- in the tail. The longest run of empty bins is found with a running count
-- of the bins that do have readings, which holds still across a run of
-- empty ones and so groups them. The range of bins comes from the smallest
-- and largest reading rather than from the counts, so the count itself, the
-- dear part, is named once: SQLite before 3.35 works a CTE out again every
-- time it is named.
WITH RECURSIVE
widths(width) AS (
    VALUES (5), (10), (30)
),
tally AS (
    SELECT
        w.width,
        (d.minutes - (w.width - 1) * (d.minutes < 0)) / w.width AS bin,
        COUNT(*) AS deliveries
    FROM widths w
    CROSS JOIN deliveries d
    GROUP BY w.width, (d.minutes - (w.width - 1) * (d.minutes < 0)) / w.width
),
span AS (
    SELECT MIN(minutes) AS lowest, MAX(minutes) AS highest FROM deliveries
),
bounds AS (
    SELECT
        w.width,
        (s.lowest - (w.width - 1) * (s.lowest < 0)) / w.width AS first_bin,
        (s.highest - (w.width - 1) * (s.highest < 0)) / w.width AS last_bin
    FROM widths w
    CROSS JOIN span s
),
spine(width, bin) AS (
    SELECT width, first_bin FROM bounds
    UNION ALL
    SELECT s.width, s.bin + 1
    FROM spine s
    JOIN bounds b ON b.width = s.width
    WHERE s.bin < b.last_bin
),
counted AS (
    SELECT s.width, s.bin, COALESCE(t.deliveries, 0) AS deliveries
    FROM spine s
    LEFT JOIN tally t ON t.width = s.width AND t.bin = s.bin
),
runs AS (
    SELECT
        width,
        bin,
        deliveries,
        SUM(deliveries > 0) OVER (PARTITION BY width ORDER BY bin) AS run_key
    FROM counted
),
marked AS (
    SELECT
        width,
        bin,
        deliveries,
        SUM(deliveries = 0) OVER (PARTITION BY width, run_key) AS empty_run,
        ROW_NUMBER() OVER (PARTITION BY width ORDER BY deliveries DESC, bin) AS place
    FROM runs
)
SELECT
    width AS bin_width,
    COUNT(*) AS bins,
    SUM(deliveries > 0) AS bins_with_readings,
    SUM(deliveries = 0) AS empty_bins,
    MAX(empty_run) AS longest_empty_run,
    MAX(CASE WHEN place = 1 THEN printf('%d to %d', bin * width, bin * width + width - 1) END) AS fullest_bin,
    MAX(deliveries) AS fullest_count
FROM marked
GROUP BY width
ORDER BY width;
