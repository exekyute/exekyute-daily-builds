-- The log at a glance: the days it covers, how many parts it tracks, its
-- rows and the units they add up to, and how many rows are a day a part
-- was not used at all. The loader has already made sure every part has one
-- row for every day from the first to the last, so the rows are the parts
-- times the days.
SELECT
    MIN(day) AS first_day,
    MAX(day) AS last_day,
    CAST(julianday(MAX(day)) - julianday(MIN(day)) AS INTEGER) + 1 AS days,
    COUNT(DISTINCT part) AS parts,
    COUNT(*) AS usage_rows,
    SUM(units) AS units_used,
    SUM(units = 0) AS idle_rows
FROM usage;
