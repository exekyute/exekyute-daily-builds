-- The log at a glance: how many deliveries, how early and how late the
-- extremes ran, and how the ten-minute bins between them divide up. A bin is
-- ten minutes wide and starts at a multiple of ten, so the bin a reading
-- falls in is its minutes divided by ten, rounded down. SQLite divides whole
-- numbers toward zero, which is not the same thing below zero, so the
-- division subtracts nine from a negative reading first.
SELECT
    COUNT(*) AS deliveries,
    MIN(minutes) AS earliest,
    MAX(minutes) AS latest,
    MAX((minutes - 9 * (minutes < 0)) / 10) - MIN((minutes - 9 * (minutes < 0)) / 10) + 1 AS bins,
    COUNT(DISTINCT (minutes - 9 * (minutes < 0)) / 10) AS bins_with_readings,
    MAX((minutes - 9 * (minutes < 0)) / 10) - MIN((minutes - 9 * (minutes < 0)) / 10) + 1
        - COUNT(DISTINCT (minutes - 9 * (minutes < 0)) / 10) AS empty_bins
FROM deliveries;
